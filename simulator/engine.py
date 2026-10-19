"""Single-pump simulator with a random fault schedule (SYNTHETIC data).

One run = one pump (PUMP-01). Readings are produced every SIM_INTERVAL_S seconds
(10 s in the workshop). The schedule is expressed in READINGS so tests can run it
faster with a smaller interval; at 10 s per reading:

  first fault onset ............ reading 5-12   (50-120 s after Start)
  fault active (incl. ramp) .... 8-13 readings  (80-130 s), then maintenance reset
  next fault onset ............. 15-30 readings after the previous onset (2.5-5 min),
                                 never earlier than 4 readings after the reset
  near-miss (35% of long gaps).. 4 readings of mild drift that stays below threshold
  "Inject fault now" ........... starts a fault on the next reading (if none is active)

Guarantee: at most 30 readings (5 minutes) between fault onsets.
Telemetry is driven by fault profiles; logs are emitted from the generated values,
so logs and telemetry agree.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np

from .fault_profiles import (
    CLASSES, EVENT_CODES, FAULTS, FEATURES, LIMITS, MACHINES, NORMAL, SIM_MACHINE_ID,
)

FAULT_TYPES = list(FAULTS)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# --------------------------------------------------------------------------- #
# Telemetry
# --------------------------------------------------------------------------- #
def baseline(machine_id: str, ts: datetime) -> dict[str, float]:
    """Expected normal value per feature for a machine at a time (incl. daily cycle)."""
    offset = MACHINES.get(machine_id, {}).get("offset", {})
    hour = ts.hour + ts.minute / 60.0
    cyc = math.sin(2 * math.pi * hour / 24.0)
    out = {}
    for f in FEATURES:
        mean = NORMAL[f][0] + offset.get(f, 0.0)
        if f == "flow_m3h":
            mean += 1.5 * cyc
        elif f == "motor_current_a":
            mean += 0.4 * cyc
        elif f == "temperature_c":
            mean += 0.8 * cyc
        out[f] = mean
    return out


def sample_telemetry(rng: np.random.Generator, machine_id: str, ts: datetime,
                     fault: str | None = None, severity: float = 0.0) -> dict[str, float]:
    base = baseline(machine_id, ts)
    prof = FAULTS.get(fault) if fault else None
    values = {}
    for f in FEATURES:
        std = NORMAL[f][1]
        mean = base[f]
        if prof:
            mean += prof["delta"].get(f, 0.0) * severity
            std *= 1.0 + (prof["noise_mult"].get(f, 1.0) - 1.0) * severity
        values[f] = round(float(rng.normal(mean, std)), 3)
    values["vibration_mm_s"] = max(values["vibration_mm_s"], 0.1)
    return values


# --------------------------------------------------------------------------- #
# Synthetic scoring (DEMO ONLY - not an ML prediction)
# --------------------------------------------------------------------------- #
def z_vector(machine_id: str, ts: datetime, telemetry: dict) -> np.ndarray:
    base = baseline(machine_id, ts)
    return np.array([(telemetry[f] - base[f]) / NORMAL[f][1] for f in FEATURES])


def synthetic_anomaly_score(machine_id: str, ts: datetime, telemetry: dict) -> float:
    """RMS z-score vs. the normal baseline. ~1.0 when normal, >2.5 when clearly faulty."""
    z = z_vector(machine_id, ts, telemetry)
    return round(float(np.sqrt(np.mean(z ** 2))), 4)


def synthetic_fault_class(machine_id: str, ts: datetime, telemetry: dict) -> tuple[str, dict[str, float]]:
    """Cosine match of the deviation vector against fault signatures (DEMO ONLY)."""
    z = z_vector(machine_id, ts, telemetry)
    sims = {}
    for name, prof in FAULTS.items():
        sig = np.array([prof["delta"].get(f, 0.0) / NORMAL[f][1] for f in FEATURES])
        sims[name] = float(z @ sig / (np.linalg.norm(z) * np.linalg.norm(sig) + 1e-9))
    exps = {k: math.exp(8.0 * v) for k, v in sims.items()}
    total = sum(exps.values())
    probs = {"normal": 0.0, **{k: round(v / total, 4) for k, v in exps.items()}}
    return max(sims, key=sims.get), probs


# --------------------------------------------------------------------------- #
# Logs
# --------------------------------------------------------------------------- #
def make_log(machine_id: str, ts: datetime, code: str, value=None, *, run_id: str | None = None,
             event_id: str | None = None, source: str = "simulator") -> dict:
    level, _name, template = EVENT_CODES[code]
    return {
        "run_id": run_id,
        "event_id": event_id,
        "machine_id": machine_id,
        "ts": ts,
        "log_level": level,
        "event_code": code,
        "message": template.format(v=value if value is not None else "", m=machine_id),
        "source": source,
    }


def fault_log_candidates(telemetry: dict, fault: str | None, severity: float,
                         rng: np.random.Generator) -> list[tuple[str, object]]:
    """(code, value) pairs justified by the current reading."""
    t = telemetry
    out: list[tuple[str, object]] = []
    vib, temp, cur = t["vibration_mm_s"], t["temperature_c"], t["motor_current_a"]
    flow, prs = t["flow_m3h"], t["discharge_pressure_bar"]
    if vib > LIMITS["vibration_alert"]:
        out.append(("VIB-201", round(vib, 2)))
    if vib > 8.0:
        out.append(("VIB-290", round(vib, 2)))
    if temp > LIMITS["temp_alert"]:
        out.append(("TMP-110", round(temp, 1)))
    if temp > 82.0:
        out.append(("TMP-190", round(temp, 1)))
    if cur > LIMITS["current_rated"]:
        out.append(("ELC-410", round(cur, 1)))
    if cur > 58.0:
        out.append(("ELC-490", round(cur, 1)))
    if flow < 112.0:
        out.append(("FLW-320", round(flow, 1)))
    if fault == "cavitation" and severity > 0.3:
        if prs < 5.4:
            out.append(("PRS-305", round(prs, 2)))
        out.append(("VIB-202", round(vib, 2)))
    elif fault == "seal_leak":
        if rng.random() < 0.3 + 0.6 * severity:
            out.append(("SEL-510", None))
        if prs < 5.7:
            out.append(("PRS-306", round(prs, 2)))
        if severity > 0.8:
            out.append(("SEL-590", None))
    elif fault == "motor_overload" and severity > 0.4:
        out.append(("ELC-412", round(float(rng.uniform(4, 9)), 1)))
    elif fault == "misalignment" and vib > 3.8:
        out.append(("VIB-205", round(vib * 0.7, 2)))
    elif fault == "bearing_wear" and severity > 0.5 and rng.random() < 0.3:
        out.append(("LUB-150", int(rng.integers(40, 300))))
    return out


# --------------------------------------------------------------------------- #
# Fault schedule (in readings)
# --------------------------------------------------------------------------- #
class FaultSchedule:
    FIRST_ONSET = (5, 12)          # inclusive range, readings after start
    DURATION = (8, 13)             # readings a fault stays active
    ONSET_GAP = (15, 30)           # readings between consecutive onsets (<= 30 = 5 min)
    MIN_NORMAL_AFTER_RESET = 4
    START_SEVERITY = 0.15
    RAMP = 0.12
    NEAR_MISS_PROB = 0.35
    NEAR_MISS_PROFILE = (0.04, 0.07, 0.08, 0.05)

    def __init__(self, rng: np.random.Generator):
        self.rng = rng
        self.reading = 0
        self.phase = "normal"
        self.fault: str | None = None
        self.severity = 0.0
        self.episode = 0
        self.injected = False
        self.last_fault: str | None = None
        self.last_onset: int | None = None
        self.fault_end = 0
        self.next_onset = self._randint(*self.FIRST_ONSET)
        self.near_miss: dict | None = None
        self._pending_inject = False

    def _randint(self, lo: int, hi: int) -> int:
        return int(self.rng.integers(lo, hi + 1))

    def inject(self) -> bool:
        """Start a fault on the next reading. False if a fault is already active or pending."""
        if self.phase == "fault" or self._pending_inject:
            return False
        self._pending_inject = True
        return True

    def _start_fault(self, injected: bool) -> None:
        choices = [f for f in FAULT_TYPES if f != self.last_fault]
        self.fault = choices[self._randint(0, len(choices) - 1)]
        self.last_fault = self.fault
        self.phase = "fault"
        self.severity = self.START_SEVERITY
        self.episode += 1
        self.injected = injected
        self.last_onset = self.reading
        self.fault_end = self.reading + self._randint(*self.DURATION)
        self.near_miss = None

    def _schedule_next(self) -> None:
        nxt = max(self.last_onset + self._randint(*self.ONSET_GAP), self.reading + self.MIN_NORMAL_AFTER_RESET)
        self.next_onset = nxt
        gap = nxt - self.reading
        if gap >= 10 and self.rng.random() < self.NEAR_MISS_PROB:
            start = self.reading + self._randint(2, gap - 6)
            choices = [f for f in FAULT_TYPES if f != self.last_fault]
            self.near_miss = {"start": start, "fault": choices[self._randint(0, len(choices) - 1)]}

    def step(self) -> dict:
        """Advance one reading and return the ground truth for it."""
        self.reading += 1
        onset = recovered = False
        if self.phase == "fault":
            if self.reading > self.fault_end:
                self.phase, self.fault, self.severity, self.injected = "normal", None, 0.0, False
                recovered = True
                self._schedule_next()
            else:
                self.severity = min(1.0, self.severity + self.RAMP)
        if self.phase == "normal" and not recovered:
            if self._pending_inject or self.reading >= self.next_onset:
                self._start_fault(injected=self._pending_inject)
                self._pending_inject = False
                onset = True
        if self.phase == "fault":
            return {"phase": "fault", "fault": self.fault, "severity": round(self.severity, 3),
                    "episode": self.episode, "onset": onset, "recovered": False, "injected": self.injected}
        nm = self.near_miss
        if nm and nm["start"] <= self.reading < nm["start"] + len(self.NEAR_MISS_PROFILE):
            sev = self.NEAR_MISS_PROFILE[self.reading - nm["start"]]
            return {"phase": "near_miss", "fault": nm["fault"], "severity": sev, "episode": self.episode,
                    "onset": False, "recovered": recovered, "injected": False}
        return {"phase": "normal", "fault": None, "severity": 0.0, "episode": self.episode,
                "onset": False, "recovered": recovered, "injected": False}


# --------------------------------------------------------------------------- #
# Pump simulator (one per run)
# --------------------------------------------------------------------------- #
class PumpSimulator:
    CODE_COOLDOWN = 3       # same fault code at most every 3 readings
    HEARTBEAT_EVERY = 30    # readings

    def __init__(self, seed: int, machine_id: str = SIM_MACHINE_ID):
        self.rng = np.random.default_rng(seed)
        self.machine_id = machine_id
        self.schedule = FaultSchedule(self.rng)
        self.seq = 0
        self.last_code: dict[str, int] = {}

    def inject_fault(self) -> bool:
        return self.schedule.inject()

    def tick(self, run_id: str, now: datetime | None = None) -> dict:
        now = now or utcnow()
        self.seq += 1
        event_id = str(uuid.uuid4())
        truth = self.schedule.step()
        m = self.machine_id
        tel = sample_telemetry(self.rng, m, now, truth["fault"], truth["severity"])
        logs: list[dict] = []

        def log(code, value=None, ts=None, source="simulator"):
            logs.append(make_log(m, ts or now, code, value, run_id=run_id, event_id=event_id, source=source))

        if self.seq == 1:
            log("SYS-002")
        if self.seq % self.HEARTBEAT_EVERY == 1:
            log("SYS-001", self.seq * 10 // 3600)
        if truth["recovered"]:
            log("MNT-620", f"WO-{int(self.rng.integers(50000, 59999))}")
        if truth["onset"] and truth["fault"] == "misalignment":
            # The coupling work order that precedes misalignment, dated two days earlier.
            log("MNT-610", f"WO-{int(self.rng.integers(40000, 49999))}",
                ts=now - timedelta(days=2, hours=int(self.rng.integers(1, 9))), source="simulator_backfill")
        if truth["phase"] == "fault":
            for code, val in fault_log_candidates(tel, truth["fault"], truth["severity"], self.rng):
                if self.seq - self.last_code.get(code, -99) >= self.CODE_COOLDOWN:
                    self.last_code[code] = self.seq
                    log(code, val)
        elif self.rng.random() < 0.01:
            log("LUB-150", int(self.rng.integers(10, 60)))  # red herring on a healthy pump
        if self.seq % 18 == 9:
            log("CTL-030", int(self.rng.choice([118, 120, 122])))
        return {
            "event_id": event_id,
            "seq": self.seq,
            "ts": now,
            "timestamp": iso(now),
            "machine_id": m,
            "telemetry": tel,
            "ground_truth": truth,
            "logs": logs,
        }
