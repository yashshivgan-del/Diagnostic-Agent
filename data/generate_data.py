#!/usr/bin/env python3
"""Generate all SYNTHETIC data for the workshop.

Outputs
  data/training/rcf_train.csv             normal-only telemetry, no header       -> SageMaker RCF
  data/training/xgb_train.csv             label first, no header                 -> SageMaker XGBoost
  data/training/xgb_validation.csv        label first, no header
  data/training/xgb_dataset_labeled.csv   same rows with header (inspection)
  data/training/eval_labeled.csv          labelled mix for RCF threshold calibration
  data/training/classes.json              class index -> name, feature order
  data/knowledge_base/incidents/*.md      20 past incident reports               -> Karini Knowledge Base
  data/knowledge_base/procedures/*.md     SOPs, event-code reference, safety     -> Karini Knowledge Base
  data/knowledge_base/kb_index.csv
  db/04_seed.sql                          PUMP-01 30-day history (relative to now()) + kb_documents

  python data/generate_data.py            # full size
  python data/generate_data.py --small    # 10x smaller training sets (quick test)

Everything is synthetic and internally consistent: telemetry, logs and incidents share
the fault signatures in simulator/fault_profiles.py.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from simulator.engine import fault_log_candidates, iso, make_log, sample_telemetry  # noqa: E402
from simulator.fault_profiles import (  # noqa: E402
    CLASSES, EVENT_CODES, FAULTS, FEATURES, MACHINES, SIM_MACHINE_ID, UNITS,
)

MACHINE_IDS = list(MACHINES)


# --------------------------------------------------------------------------- training data
def random_ts(rng, start: datetime, days: float) -> datetime:
    return start + timedelta(seconds=float(rng.uniform(0, days * 86400)))


def gen_rcf_train(rng, out: Path, days: int, end: datetime) -> int:
    start = end - timedelta(days=days)
    n = 0
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        for m in MACHINE_IDS:
            ts = start
            while ts < end:
                t = sample_telemetry(rng, m, ts)
                w.writerow([t[f] for f in FEATURES])
                ts += timedelta(minutes=1)
                n += 1
    return n


def labeled_rows(rng, n_normal: int, n_per_fault: int, sev_lo: float, end: datetime):
    rows = []
    start = end - timedelta(days=60)
    for _ in range(n_normal):
        m = MACHINE_IDS[int(rng.integers(0, len(MACHINE_IDS)))]
        ts = random_ts(rng, start, 60)
        rows.append((0, "normal", 0.0, m, ts, sample_telemetry(rng, m, ts)))
    for idx, fault in enumerate(CLASSES[1:], start=1):
        for _ in range(n_per_fault):
            m = MACHINE_IDS[int(rng.integers(0, len(MACHINE_IDS)))]
            ts = random_ts(rng, start, 60)
            sev = float(rng.uniform(sev_lo, 1.0))
            rows.append((idx, fault, round(sev, 3), m, ts, sample_telemetry(rng, m, ts, fault, sev)))
    rng.shuffle(rows)
    return rows


def gen_xgb(rng, outdir: Path, n_normal: int, n_per_fault: int, end: datetime) -> dict:
    rows = labeled_rows(rng, n_normal, n_per_fault, 0.3, end)
    split = int(len(rows) * 0.8)
    with (outdir / "xgb_dataset_labeled.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["label", "fault_type", "severity", "machine_id", "timestamp", *FEATURES])
        for lab, name, sev, m, ts, t in rows:
            w.writerow([lab, name, sev, m, iso(ts), *[t[f] for f in FEATURES]])
    for fname, part in (("xgb_train.csv", rows[:split]), ("xgb_validation.csv", rows[split:])):
        with (outdir / fname).open("w", newline="") as fh:
            w = csv.writer(fh)
            for lab, _n, _s, _m, _ts, t in part:
                w.writerow([lab, *[t[f] for f in FEATURES]])
    return {"train": split, "validation": len(rows) - split}


def gen_eval(rng, out: Path, n_total: int, end: datetime) -> int:
    n_fault_each = max(1, int(n_total * 0.05 / 5))
    rows = labeled_rows(rng, n_total - 5 * n_fault_each, n_fault_each, 0.2, end)
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["is_anomaly", "fault_type", "severity", "machine_id", "timestamp", *FEATURES])
        for lab, name, sev, m, ts, t in rows:
            w.writerow([int(lab != 0), name, sev, m, iso(ts), *[t[f] for f in FEATURES]])
    return len(rows)


# --------------------------------------------------------------------------- incidents (KB)
ROOT_CAUSES = {
    "bearing_wear": [
        ("Drive-end bearing outer-race spalling caused by degraded lubricant",
         "Replaced drive-end bearing (6312-C3), flushed housing, regreased to OEM quantity",
         "Lubrication interval exceeded; grease had oxidised."),
        ("Bearing contamination from water ingress past a failed lip seal",
         "Replaced both bearings and the lip seal, added a bearing isolator",
         "Water ingress follows wash-down of the pump area."),
        ("Lubrication interval missed for approximately 3 months",
         "Replaced drive-end bearing, added the pump to the CMMS lubrication route",
         "Pump was missing from the lubrication route after a CMMS migration."),
    ],
    "cavitation": [
        ("Suction strainer approximately 70% blocked",
         "Cleaned suction strainer, added differential-pressure gauge across strainer",
         "Debris load increases after upstream tank cleaning."),
        ("Suction tank level below minimum while low-level alarm was bypassed",
         "Restored low-level interlock, refilled tank, inspected impeller (light pitting)",
         "Interlock bypasses must be logged and time-limited."),
        ("Suction isolation valve left partially closed after maintenance",
         "Fully opened suction valve, added valve-position check to the return-to-service checklist",
         "Return-to-service checklist did not include suction valve position."),
    ],
    "seal_leak": [
        ("Mechanical seal faces worn after a dry-running event",
         "Replaced mechanical seal cartridge, verified seal flush flow",
         "Dry running for under 2 minutes was enough to damage the faces."),
        ("Seal O-ring chemically degraded by process additive",
         "Replaced seal with FKM O-ring variant",
         "Elastomer compatibility must be checked when water treatment chemicals change."),
        ("Seal flush line blocked by scale",
         "Descaled flush line, replaced seal, added flush-flow indicator",
         "Flush line blockage gives a slow leak that worsens over days."),
    ],
    "motor_overload": [
        ("Discharge valve fully opened, pump running far right of best efficiency point",
         "Throttled discharge valve to design duty point, updated operating procedure",
         "Running right of BEP raises current and bearing temperature together."),
        ("Motor winding insulation degradation causing phase imbalance",
         "Motor replaced; failed motor sent for rewind. Insulation resistance trended monthly",
         "Phase imbalance warnings preceded the overload by about 10 days."),
        ("Foreign object partially jamming the impeller",
         "Removed debris from impeller eye, installed finer suction screen",
         "Debris entered during upstream pipework modification."),
    ],
    "misalignment": [
        ("Coupling replaced without laser alignment verification",
         "Laser-aligned motor and pump to within 0.05 mm offset, re-torqued feet",
         "Alignment check was skipped to return the pump to service quickly."),
        ("Soft foot on motor baseplate after re-installation",
         "Corrected soft foot with shims, re-aligned shaft",
         "Soft foot was not checked during re-installation."),
        ("Thermal growth not compensated in cold alignment",
         "Re-aligned using hot-alignment offsets from OEM data",
         "Boiler-feed duty requires thermal growth offsets."),
    ],
}

# (fault, initial hypothesis if different) - misdiagnosis cases on purpose
INCIDENT_PLAN = [
    ("bearing_wear", None), ("bearing_wear", None), ("bearing_wear", None), ("bearing_wear", None),
    ("bearing_wear", None),
    ("cavitation", None), ("cavitation", None), ("cavitation", "seal_leak"), ("cavitation", None),
    ("seal_leak", None), ("seal_leak", None), ("seal_leak", None), ("seal_leak", None),
    ("motor_overload", None), ("motor_overload", "bearing_wear"), ("motor_overload", None),
    ("misalignment", "bearing_wear"), ("misalignment", "bearing_wear"), ("misalignment", None),
    ("misalignment", None),
]

SOP_FOR = {
    "bearing_wear": "SOP-PUMP-101 Bearing condition troubleshooting",
    "cavitation": "SOP-PUMP-102 Cavitation and suction troubleshooting",
    "seal_leak": "SOP-PUMP-103 Mechanical seal leak troubleshooting",
    "motor_overload": "SOP-PUMP-104 Motor overload and electrical troubleshooting",
    "misalignment": "SOP-PUMP-105 Shaft alignment troubleshooting",
}


def simulate_episode(rng, machine_id: str, fault: str, start: datetime, hours: float, downtime: float):
    """10-minute resolution episode; returns (logs, peak telemetry, codes seen)."""
    logs, codes, peak = [], [], None
    steps = int(hours * 6)
    last = {}
    if "precursor_codes" in FAULTS[fault]:
        pre_ts = start - timedelta(days=float(rng.uniform(1, 4)))
        logs.append(make_log(machine_id, pre_ts, "MNT-610", f"WO-{int(rng.integers(30000, 39999))}",
                             source="historical"))
        codes.append("MNT-610")
    for i in range(steps):
        ts = start + timedelta(minutes=10 * i)
        sev = min(1.0, 0.25 + 0.75 * i / max(1, steps - 1))
        t = sample_telemetry(rng, machine_id, ts, fault, sev)
        peak = t
        for code, val in fault_log_candidates(t, fault, sev, rng):
            if i - last.get(code, -99) >= 3:
                last[code] = i
                logs.append(make_log(machine_id, ts, code, val, source="historical"))
                if code not in codes:
                    codes.append(code)
    end = start + timedelta(hours=hours)
    logs.append(make_log(machine_id, end, "SYS-003", source="historical"))
    if fault == "bearing_wear":
        logs.append(make_log(machine_id, end + timedelta(hours=downtime * 0.7), "MNT-615", source="historical"))
    elif fault == "misalignment":
        logs.append(make_log(machine_id, end + timedelta(hours=downtime * 0.7), "MNT-610",
                             f"WO-{int(rng.integers(30000, 39999))}", source="historical"))
    logs.append(make_log(machine_id, end + timedelta(hours=downtime), "SYS-002", source="historical"))
    return logs, peak, codes


def fmt_tel(t: dict) -> str:
    rows = ["| Sensor | Value | Unit |", "| --- | --- | --- |"]
    rows += [f"| {f} | {t[f]} | {UNITS[f]} |" for f in FEATURES]
    return "\n".join(rows)


def write_incident(path: Path, inc: dict) -> None:
    f = inc["fault"]
    cause, action, lesson = inc["cause"]
    initial = inc["initial"]
    codes = ", ".join(f"`{c}` ({EVENT_CODES[c][1]})" for c in inc["codes"]) or "none recorded"
    misdiag = ""
    if initial and initial != f:
        misdiag = (f"\n**Initial hypothesis:** {FAULTS[initial]['title']}. "
                   f"This was ruled out during inspection; the confirmed cause was "
                   f"{FAULTS[f]['title'].lower()}. Do not rely on vibration alone to distinguish them.\n")
    text = f"""# {inc['id']}: {FAULTS[f]['title']} on {inc['machine']}

| Field | Value |
| --- | --- |
| Incident ID | {inc['id']} |
| Machine | {inc['machine']} ({MACHINES[inc['machine']]['site']}, {MACHINES[inc['machine']]['line']}) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | {inc['detected']} |
| Resolved | {inc['resolved']} |
| Confirmed fault category | {f} |
| Unplanned downtime | {inc['downtime']} h |
| Related procedure | {SOP_FOR[f]} |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

{fmt_tel(inc['peak'])}

Log event codes observed: {codes}.
{misdiag}
## Root cause
{cause}.

## Corrective action
{action}.

## Lessons learned
{lesson}

## Keywords
{f.replace('_', ' ')}, {', '.join(inc['codes'])}, {inc['machine']}, centrifugal pump
"""
    path.write_text(text)




def gen_incidents(rng, kb_dir: Path, end: datetime) -> list[dict]:
    """20 incident reports across the fleet, all older than 35 days (outside the seed log window)."""
    inc_dir = kb_dir / "incidents"
    if inc_dir.exists():
        shutil.rmtree(inc_dir)
    inc_dir.mkdir(parents=True)
    incidents = []
    for fault, initial in INCIDENT_PLAN:
        machine = MACHINE_IDS[int(rng.integers(0, len(MACHINE_IDS)))]
        det = end - timedelta(days=float(rng.uniform(35, 360)))
        hours = float(rng.uniform(3, 10))
        downtime = round(float(rng.uniform(2, 18)), 1)
        _logs, peak, codes = simulate_episode(rng, machine, fault, det, hours, downtime)
        incidents.append({
            "fault": fault, "initial": initial, "machine": machine,
            "cause": ROOT_CAUSES[fault][int(rng.integers(0, 3))],
            "detected": iso(det), "resolved": iso(det + timedelta(hours=hours + downtime)),
            "downtime": downtime, "peak": peak, "codes": codes,
        })
    incidents.sort(key=lambda i: i["detected"])
    with (kb_dir / "kb_index.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["doc_id", "file", "machine_id", "detected", "confirmed_fault", "initial_hypothesis"])
        for i, inc in enumerate(incidents, start=1):
            inc["id"] = f"INC-{inc['detected'][:4]}-{i:03d}"
            inc["file"] = f"{inc['id']}_{inc['machine']}_{inc['fault']}.md"
            write_incident(inc_dir / inc["file"], inc)
            w.writerow([inc["id"], f"incidents/{inc['file']}", inc["machine"], inc["detected"], inc["fault"],
                        inc["initial"] or inc["fault"]])
    return incidents


def copy_procedures(kb_dir: Path) -> list[Path]:
    dst = kb_dir / "procedures"
    dst.mkdir(parents=True, exist_ok=True)
    out = []
    for f in sorted((HERE / "procedures_src").glob("*.md")):
        shutil.copy(f, dst / f.name)
        out.append(dst / f.name)
    return out


# --------------------------------------------------------------------------- seed SQL
def sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def dollar(s: str, tag: str = "kb") -> str:
    assert f"${tag}$" not in s
    return f"${tag}${s}${tag}$"


def seed_history(rng, days: int = 30) -> list[tuple[int, str, str, str]]:
    """(seconds_ago, level, code, message) for PUMP-01. Timestamps become now() - interval at load time."""
    m = SIM_MACHINE_ID
    rows: list[tuple[int, str, str, str]] = []

    def add(sec_ago: float, code: str, value=None):
        level, _n, tpl = EVENT_CODES[code]
        rows.append((int(sec_ago), level, code, tpl.format(v=value if value is not None else "", m=m)))

    day = 86400
    for d in range(days):
        base = (days - d) * day
        for hh in (6, 14, 22):
            add(base - hh * 3600 - rng.uniform(0, 600), "OPS-020")
        for _ in range(int(rng.poisson(1.5))):
            add(base - rng.uniform(0, day), "CTL-030", int(rng.choice([115, 118, 120, 122, 125])))
        for hh in (0, 6, 12, 18):
            add(base - hh * 3600, "SYS-001", int((days - d) * 24 + hh))
    for w in range(0, days, 7):
        add((days - w) * day - rng.uniform(0, 6 * day), "MNT-601")
    # Bearing regrease 18 days ago, lubrication reminders, and a short temperature episode
    # 12 days ago that cleared without a fault (gives "recurring warnings" something to show).
    add(18 * day + 3600, "MNT-615")
    for d in (25, 9, 3):
        add(d * day + rng.uniform(0, day / 2), "LUB-150", int(rng.integers(12, 60)))
    for k in range(3):
        add(12 * day - k * 1800, "TMP-110", round(float(rng.uniform(72.2, 73.5)), 1))
    add(12 * day - 4 * 1800, "MNT-601")
    rows.sort(key=lambda r: -r[0])
    return rows


def write_seed_sql(out: Path, rng, incidents: list[dict], procedures: list[Path], kb_dir: Path) -> dict:
    hist = seed_history(rng)
    lines = [
        "-- =============================================================================",
        "-- Predictive Diagnostic Assistant (workshop) - 04 seed data (GENERATED by data/generate_data.py)",
        "-- PUMP-01 30-day shared history (run_id NULL, timestamps relative to now() at load time)",
        "-- and pda.kb_documents (copy of the Knowledge Base, used only by the database search fallback).",
        "-- Re-running replaces the seed rows; run rows are untouched.",
        "-- =============================================================================",
        "DELETE FROM pda.machine_logs WHERE run_id IS NULL AND source = 'seed';",
        "INSERT INTO pda.machine_logs (run_id, event_id, machine_id, ts, log_level, event_code, message, source) VALUES",
    ]
    vals = [f"(NULL, NULL, {sql_str(SIM_MACHINE_ID)}, now() - interval '{sec} seconds', {sql_str(lvl)}, "
            f"{sql_str(code)}, {sql_str(msg)}, 'seed')" for sec, lvl, code, msg in hist]
    lines.append(",\n".join(vals) + ";")
    lines.append("INSERT INTO pda.kb_documents (doc_id, title, doc_type, content) VALUES")
    docs = []
    for inc in incidents:
        text = (kb_dir / "incidents" / inc["file"]).read_text()
        title = text.splitlines()[0].lstrip("# ").strip()
        docs.append(f"({sql_str(inc['id'])}, {sql_str(title)}, 'incident', {dollar(text)})")
    for p in procedures:
        text = p.read_text()
        doc_id = p.stem.split("_")[0]
        title = text.splitlines()[0].lstrip("# ").strip()
        dtype = "reference" if doc_id.startswith(("REF", "SAFE")) else "procedure"
        docs.append(f"({sql_str(doc_id)}, {sql_str(title)}, {sql_str(dtype)}, {dollar(text)})")
    lines.append(",\n".join(docs))
    lines.append("ON CONFLICT (doc_id) DO UPDATE SET title = EXCLUDED.title, doc_type = EXCLUDED.doc_type, content = EXCLUDED.content;")
    out.write_text("\n".join(lines) + "\n")
    return {"seed_logs": len(hist), "kb_documents": len(docs)}


# --------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--small", action="store_true")
    ap.add_argument("--end-date", default="2026-10-14", help="reference date for incident report dates")
    a = ap.parse_args()
    end = datetime.strptime(a.end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    rng = np.random.default_rng(a.seed)
    k = 10 if a.small else 1
    tr, kb = HERE / "training", HERE / "knowledge_base"
    tr.mkdir(parents=True, exist_ok=True)
    kb.mkdir(parents=True, exist_ok=True)
    stats = {
        "rcf_train_rows": gen_rcf_train(rng, tr / "rcf_train.csv", max(1, 7 // k), end),
        "xgb": gen_xgb(rng, tr, 24000 // k, 4000 // k, end),
        "eval_rows": gen_eval(rng, tr / "eval_labeled.csv", 5000 // k, end),
    }
    (tr / "classes.json").write_text(json.dumps({"classes": CLASSES, "features": FEATURES, "units": UNITS}, indent=2))
    incidents = gen_incidents(rng, kb, end)
    procedures = copy_procedures(kb)
    stats.update(write_seed_sql(ROOT / "db" / "04_seed.sql", rng, incidents, procedures, kb))
    stats["incidents"] = len(incidents)
    stats["procedures"] = len(procedures)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
