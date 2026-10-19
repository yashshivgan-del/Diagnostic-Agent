#!/usr/bin/env python3
"""Train + deploy SageMaker built-in Random Cut Forest, then calibrate the threshold.

  python ml/train_rcf.py --role arn:aws:iam::<acct>:role/<SageMakerExecutionRole>

Steps
 1. Standardize data/training/rcf_train.csv (normal-only) -> ml/artifacts/rcf_scaler.json
 2. Train RCF (unsupervised) and deploy endpoint `pda-rcf`
 3. Score data/training/eval_labeled.csv, pick threshold = mean + k*std of NORMAL scores,
    report precision/recall -> ml/artifacts/rcf_calibration.json

An RCF score is an anomaly score, not a failure probability.
COST: the endpoint bills per hour until deleted (ml/cleanup.py).
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import sagemaker
from sagemaker import RandomCutForest
from sagemaker.deserializers import JSONDeserializer
from sagemaker.serializers import CSVSerializer

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "ml" / "artifacts"
FEATURES = ["temperature_c", "vibration_mm_s", "discharge_pressure_bar", "flow_m3h", "motor_current_a", "rpm"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", help="SageMaker execution role ARN (default: notebook role)")
    ap.add_argument("--endpoint", default="pda-rcf")
    ap.add_argument("--instance", default="ml.m5.large")
    ap.add_argument("--k", type=float, default=3.0, help="threshold = mean + k*std of normal scores")
    ap.add_argument("--skip-train", action="store_true", help="only calibrate an existing endpoint")
    a = ap.parse_args()
    ART.mkdir(parents=True, exist_ok=True)

    sess = sagemaker.Session()
    role = a.role or sagemaker.get_execution_role()
    bucket = sess.default_bucket()

    train = np.loadtxt(ROOT / "data/training/rcf_train.csv", delimiter=",").astype("float32")
    mean, std = train.mean(axis=0), train.std(axis=0)
    (ART / "rcf_scaler.json").write_text(json.dumps({"features": FEATURES, "mean": mean.round(6).tolist(),
                                                      "std": std.round(6).tolist()}))
    train_z = ((train - mean) / std).astype("float32")

    if not a.skip_train:
        rcf = RandomCutForest(role=role, instance_count=1, instance_type=a.instance,
                              num_samples_per_tree=512, num_trees=100,
                              data_location=f"s3://{bucket}/pda/rcf/input",
                              output_path=f"s3://{bucket}/pda/rcf/output", sagemaker_session=sess)
        rcf.fit(rcf.record_set(train_z))
        predictor = rcf.deploy(initial_instance_count=1, instance_type=a.instance, endpoint_name=a.endpoint,
                               serializer=CSVSerializer(), deserializer=JSONDeserializer())
    else:
        predictor = sagemaker.Predictor(a.endpoint, sagemaker_session=sess, serializer=CSVSerializer(),
                                        deserializer=JSONDeserializer())

    ev = pd.read_csv(ROOT / "data/training/eval_labeled.csv")
    X = ((ev[FEATURES].to_numpy("float32") - mean) / std)
    scores = []
    for i in range(0, len(X), 500):
        scores += [s["score"] for s in predictor.predict(X[i:i + 500])["scores"]]
    ev["score"] = scores
    normal = ev.loc[ev.is_anomaly == 0, "score"]
    th = float(normal.mean() + a.k * normal.std())

    def pr(t):
        p = ev.score >= t
        tp = int((p & (ev.is_anomaly == 1)).sum())
        return {"threshold": round(t, 4), "precision": round(tp / max(int(p.sum()), 1), 4),
                "recall": round(tp / max(int(ev.is_anomaly.sum()), 1), 4), "flagged": int(p.sum())}

    out = {"endpoint": a.endpoint, "chosen": pr(th),
           "alternatives": [pr(float(normal.quantile(q))) for q in (0.99, 0.995, 0.999)],
           "normal_score_mean": float(normal.mean()), "normal_score_std": float(normal.std()),
           "recall_by_fault": ev[ev.is_anomaly == 1].assign(hit=lambda d: d.score >= th)
           .groupby("fault_type").hit.mean().round(3).to_dict()}
    (ART / "rcf_calibration.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    print(f"\nSet ANOMALY_THRESHOLD_RCF={th:.4f} (backend) / AnomalyThreshold (SAM)")
    print(f"Set RCF_SCALER_JSON='{(ART / 'rcf_scaler.json').read_text()}'")


if __name__ == "__main__":
    main()
