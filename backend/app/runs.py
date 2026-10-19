"""Run lifecycle: one asyncio worker per run (Start -> Stop / auto-stop).

Per reading (every SIM_INTERVAL_S):
  1. simulator produces telemetry + logs for PUMP-01 (new event_id)
  2. SageMaker / synthetic inference
  3. trigger decision (confirmed anomaly, re-arm, caps)
  4. ONE transaction: machine_events + machine_logs + model_predictions
     (+ karini_executions row 'queued' when triggered)
  5. the Karini dispatcher picks up queued executions
No shared mutable state between runs: each worker owns its simulator and counters.
"""
from __future__ import annotations

import asyncio
import logging
import random
import secrets
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone

from psycopg.types.json import Jsonb

from simulator.engine import PumpSimulator, utcnow
from simulator.fault_profiles import SIM_MACHINE_ID

from . import db
from .config import settings
from .inference import infer

log = logging.getLogger("pda.runs")


def build_payload(run: dict, reading: dict, inf: dict) -> dict:
    """Webhook body per the Karini guide: input_message + files + metadata (flat ids/values)."""
    probs = inf.get("fault_probabilities") or {}
    ranked = sorted(((k, v) for k, v in probs.items() if k != "normal"), key=lambda kv: -kv[1])
    second = ranked[1] if len(ranked) > 1 else (None, None)
    return {
        "input_message": (f"agent: {settings.karini_first_agent}\n"
                          f"Diagnose anomaly event {reading['event_id']} on {reading['machine_id']} "
                          f"(run {run['run_id']})."),
        "files": [],
        "metadata": {
            "agent": settings.karini_first_agent,
            "trigger": "anomaly",
            "run_id": str(run["run_id"]),
            "event_id": reading["event_id"],
            "machine_id": reading["machine_id"],
            "timestamp": reading["timestamp"],
            "notify_email": run["notify_email"],
            "anomaly_score": inf["anomaly_score"],
            "threshold": inf["threshold"],
            "is_anomaly": True,
            "confirmed": True,
            "predicted_fault": inf.get("predicted_fault"),
            "predicted_fault_probability": probs.get(inf.get("predicted_fault") or "", None),
            "second_fault": second[0],
            "second_fault_probability": second[1],
            "inference_mode": inf["mode"],
            "today": utcnow().date().isoformat(),
        },
    }


class RunWorker:
    def __init__(self, run: dict, manager: "RunManager"):
        self.run = run
        self.run_id = str(run["run_id"])
        self.manager = manager
        self.sim = PumpSimulator(seed=int(run["seed"]), machine_id=run["machine_id"])
        self.flags: deque[bool] = deque(maxlen=settings.confirm_window)
        self.armed = True
        self.normal_streak = 0
        self.trigger_count = 0
        self.stop_requested: str | None = None
        self.task: asyncio.Task | None = None

    # ---------------------------------------------------------------- control
    def start(self) -> None:
        self.task = asyncio.create_task(self._loop(), name=f"run-{self.run_id}")

    def request_stop(self, reason: str = "stopped") -> None:
        self.stop_requested = reason

    def inject(self) -> bool:
        return self.sim.inject_fault()

    # ---------------------------------------------------------------- loop
    async def _loop(self) -> None:
        deadline = self.run["auto_stop_at"]
        try:
            while True:
                if self.stop_requested:
                    await self._finish(self.stop_requested, "stopped by user")
                    return
                if datetime.now(timezone.utc) >= deadline:
                    await self._finish("auto_stopped", f"auto-stop after {settings.run_max_seconds} s")
                    return
                t0 = asyncio.get_running_loop().time()
                try:
                    await self._tick()
                except Exception:  # noqa: BLE001 - a failed tick must not kill the run
                    log.exception("tick failed for run %s", self.run_id)
                elapsed = asyncio.get_running_loop().time() - t0
                await self._sleep(max(0.2, settings.sim_interval_s - elapsed))
        except asyncio.CancelledError:
            await self._finish("interrupted", "backend shutdown")
            raise
        finally:
            self.manager.workers.pop(self.run_id, None)

    async def _sleep(self, seconds: float) -> None:
        end = asyncio.get_running_loop().time() + seconds
        while not self.stop_requested and asyncio.get_running_loop().time() < end:
            await asyncio.sleep(min(0.25, end - asyncio.get_running_loop().time()))

    async def _finish(self, status: str, reason: str) -> None:
        await db.execute(
            "UPDATE pda.runs SET status = %s, stop_reason = %s, stopped_at = now(), updated_at = now() "
            "WHERE run_id = %s AND status = 'running'", (status, reason, self.run_id))

    # ---------------------------------------------------------------- one reading
    def _decide(self, inf: dict) -> tuple[str, bool]:
        if inf["status"] != "ok":
            return "inference_failed", False
        anomalous = bool(inf["is_anomaly"])
        self.flags.append(anomalous)
        if not anomalous:
            self.normal_streak += 1
            if self.normal_streak >= settings.rearm_normal_readings:
                self.armed = True
            return "normal", False
        self.normal_streak = 0
        confirmed = sum(self.flags) >= settings.confirm_min
        if not confirmed:
            return "anomaly_unconfirmed", False
        if not self.armed:
            return "suppressed_not_rearmed", True
        if self.trigger_count >= settings.max_triggers_per_run:
            return "suppressed_trigger_cap", True
        if not settings.karini_enabled:
            return "karini_disabled", True
        self.armed = False
        self.trigger_count += 1
        return "triggered", True

    async def _tick(self) -> None:
        reading = self.sim.tick(self.run_id)
        inf = await infer(reading["machine_id"], reading["ts"], reading["telemetry"])
        decision, confirmed = self._decide(inf)
        payload = build_payload(self.run, reading, inf) if decision == "triggered" else None
        async with db.pool.connection() as c:
            async with c.transaction():
                await c.execute(
                    "INSERT INTO pda.machine_events (event_id, run_id, seq, ts, machine_id, telemetry, ground_truth) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (reading["event_id"], self.run_id, reading["seq"], reading["ts"], reading["machine_id"],
                     Jsonb(reading["telemetry"]), Jsonb(reading["ground_truth"])))
                if reading["logs"]:
                    async with c.cursor() as cur:
                        await cur.executemany(
                            "INSERT INTO pda.machine_logs (run_id, event_id, machine_id, ts, log_level, event_code, message, source) "
                            "VALUES (%(run_id)s, %(event_id)s, %(machine_id)s, %(ts)s, %(log_level)s, %(event_code)s, %(message)s, %(source)s)",
                            reading["logs"])
                if payload is not None:
                    await c.execute(
                        "INSERT INTO pda.karini_executions (event_id, run_id, status, payload) VALUES (%s, %s, 'queued', %s) "
                        "ON CONFLICT (event_id) DO NOTHING",
                        (reading["event_id"], self.run_id, Jsonb(payload)))
                    await c.execute("UPDATE pda.runs SET trigger_count = trigger_count + 1, updated_at = now() "
                                    "WHERE run_id = %s", (self.run_id,))
                # Inserted last: its NOTIFY tells the dashboard the whole reading is ready.
                await c.execute(
                    "INSERT INTO pda.model_predictions (event_id, run_id, inference_mode, inference_status, anomaly_score, "
                    "threshold, is_anomaly, confirmed, predicted_fault, fault_probabilities, trigger_decision, error, latency_ms) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (reading["event_id"], self.run_id, inf["mode"], inf["status"], inf["anomaly_score"], inf["threshold"],
                     inf["is_anomaly"], confirmed, inf["predicted_fault"],
                     Jsonb(inf["fault_probabilities"]) if inf["fault_probabilities"] is not None else None,
                     decision, inf["error"], inf["latency_ms"]))
        if payload is not None:
            self.manager.wake_dispatcher()


class RunManager:
    def __init__(self):
        self.workers: dict[str, RunWorker] = {}
        self._dispatch_event: asyncio.Event | None = None

    def bind_dispatcher(self, ev: asyncio.Event) -> None:
        self._dispatch_event = ev

    def wake_dispatcher(self) -> None:
        if self._dispatch_event is not None:
            self._dispatch_event.set()

    async def recover_after_restart(self) -> None:
        """Runs left 'running' by a previous process can no longer produce readings."""
        await db.execute("UPDATE pda.runs SET status = 'interrupted', stop_reason = 'backend restarted', "
                         "stopped_at = now(), updated_at = now() WHERE status = 'running'")

    async def create_run(self, email: str, label: str | None, karini: dict | None = None) -> dict:
        if len(self.workers) >= settings.max_active_runs:
            raise RuntimeError("too many active runs, try again in a few minutes")
        karini = karini or {}
        run_id = str(uuid.uuid4())
        seed = random.SystemRandom().randrange(1, 2**31)
        run = await db.fetch_one(
            "INSERT INTO pda.runs (run_id, access_token, notify_email, label, machine_id, seed, inference_mode, threshold, "
            "email_cap, karini_base_url, karini_recipe_id, karini_api_token, auto_stop_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now() + make_interval(secs => %s)) RETURNING *",
            (run_id, secrets.token_urlsafe(24), email, label, SIM_MACHINE_ID, seed, settings.inference_mode,
             settings.threshold, settings.email_cap_per_run,
             karini.get("base_url") or None, karini.get("recipe_id") or None, karini.get("api_token") or None,
             settings.run_max_seconds))
        worker = RunWorker(run, self)
        self.workers[run_id] = worker
        worker.start()
        return run

    def stop(self, run_id: str) -> bool:
        w = self.workers.get(run_id)
        if not w:
            return False
        w.request_stop("stopped")
        return True

    def inject(self, run_id: str) -> str:
        w = self.workers.get(run_id)
        if not w:
            return "not_running"
        return "injected" if w.inject() else "fault_already_active"

    async def shutdown(self) -> None:
        tasks = [w.task for w in self.workers.values() if w.task]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
