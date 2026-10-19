"""Anomaly scoring + fault classification for one reading.

  synthetic  local z-score + signature match. DEMO ONLY, not an ML prediction.
  sagemaker  SageMaker built-in Random Cut Forest (anomaly score, standardized input)
             + XGBoost (multi:softprob fault class). Backend calls both endpoints directly.

The backend decides is_anomaly = anomaly_score >= threshold (one rule, here).
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime

from simulator.engine import synthetic_anomaly_score, synthetic_fault_class
from simulator.fault_profiles import CLASSES, FEATURES

from .config import settings

_sm = None


def _client():
    global _sm
    if _sm is None:
        import boto3
        from botocore.config import Config
        _sm = boto3.client("sagemaker-runtime", region_name=settings.aws_region,
                           config=Config(read_timeout=settings.inference_timeout_s,
                                         connect_timeout=5, retries={"max_attempts": 2}))
    return _sm


def parse_xgb_probs(body: str) -> list[float]:
    txt = body.strip()
    try:
        val = json.loads(txt)
        if isinstance(val, dict) and "predictions" in val:
            val = val["predictions"][0].get("score", val["predictions"][0])
        if isinstance(val, list) and val and isinstance(val[0], list):
            val = val[0]
        return [float(x) for x in val]
    except (json.JSONDecodeError, TypeError, ValueError):
        return [float(x) for x in txt.replace("[", "").replace("]", "").replace("\n", ",").split(",") if x.strip()]


def _sagemaker_sync(telemetry: dict) -> dict:
    sm = _client()
    raw = [float(telemetry[f]) for f in FEATURES]
    rcf_vals = raw
    if settings.rcf_scaler_json:
        sc = json.loads(settings.rcf_scaler_json)
        rcf_vals = [(v - m) / s for v, m, s in zip(raw, sc["mean"], sc["std"])]
    r = sm.invoke_endpoint(EndpointName=settings.rcf_endpoint, ContentType="text/csv", Accept="application/json",
                           Body=",".join(str(v) for v in rcf_vals))
    score = float(json.loads(r["Body"].read())["scores"][0]["score"])
    probs, cls = None, None
    if settings.xgb_endpoint:
        x = sm.invoke_endpoint(EndpointName=settings.xgb_endpoint, ContentType="text/csv",
                               Body=",".join(str(v) for v in raw))
        p = parse_xgb_probs(x["Body"].read().decode())
        probs = {CLASSES[i]: round(v, 4) for i, v in enumerate(p[:len(CLASSES)])}
        cls = max(probs, key=probs.get)
    return {"anomaly_score": round(score, 4), "predicted_fault": cls, "fault_probabilities": probs}


async def infer(machine_id: str, ts: datetime, telemetry: dict) -> dict:
    """Returns {status, mode, anomaly_score, threshold, is_anomaly, predicted_fault, fault_probabilities, error, latency_ms}."""
    t0 = time.monotonic()
    mode = settings.inference_mode
    th = settings.threshold
    try:
        if mode == "sagemaker":
            out = await asyncio.wait_for(asyncio.to_thread(_sagemaker_sync, telemetry),
                                         timeout=settings.inference_timeout_s + 5)
        else:
            score = synthetic_anomaly_score(machine_id, ts, telemetry)
            cls, probs = synthetic_fault_class(machine_id, ts, telemetry)
            out = {"anomaly_score": score, "predicted_fault": cls, "fault_probabilities": probs}
        is_anom = out["anomaly_score"] >= th
        if not is_anom and mode == "synthetic":
            out["predicted_fault"] = "normal"
        return {"status": "ok", "mode": mode, "threshold": th, "is_anomaly": is_anom, "error": None,
                "latency_ms": int((time.monotonic() - t0) * 1000), **out}
    except Exception as exc:  # noqa: BLE001 - recorded on the reading, shown on the dashboard
        return {"status": "failed", "mode": mode, "threshold": th, "is_anomaly": None, "anomaly_score": None,
                "predicted_fault": None, "fault_probabilities": None,
                "error": f"{type(exc).__name__}: {exc}"[:500], "latency_ms": int((time.monotonic() - t0) * 1000)}
