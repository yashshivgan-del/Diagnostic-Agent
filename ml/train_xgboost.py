#!/usr/bin/env python3
"""Train + deploy SageMaker built-in XGBoost fault classifier (6 classes).

  python ml/train_xgboost.py --role arn:aws:iam::<acct>:role/<SageMakerExecutionRole>

Input: data/training/xgb_train.csv and xgb_validation.csv (label first, no header).
Labels: 0 normal, 1 bearing_wear, 2 cavitation, 3 seal_leak, 4 motor_overload, 5 misalignment.
Output endpoint `pda-xgb` returns 6 class probabilities (multi:softprob).
COST: the endpoint bills per hour until deleted (ml/cleanup.py).
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import sagemaker
from sagemaker.estimator import Estimator
from sagemaker.inputs import TrainingInput
from sagemaker.serializers import CSVSerializer

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "ml" / "artifacts"
CLASSES = ["normal", "bearing_wear", "cavitation", "seal_leak", "motor_overload", "misalignment"]


def parse(body) -> np.ndarray:
    txt = body.decode() if isinstance(body, bytes) else str(body)
    try:
        val = json.loads(txt)
        return np.array(val, dtype=float).reshape(-1, len(CLASSES))
    except ValueError:
        rows = [r for r in txt.replace("[", "").replace("]", "\n").splitlines() if r.strip(" ,")]
        return np.array([[float(x) for x in r.strip(" ,").split(",")] for r in rows]).reshape(-1, len(CLASSES))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role")
    ap.add_argument("--endpoint", default="pda-xgb")
    ap.add_argument("--instance", default="ml.m5.large")
    a = ap.parse_args()
    ART.mkdir(parents=True, exist_ok=True)

    sess = sagemaker.Session()
    role = a.role or sagemaker.get_execution_role()
    bucket, prefix = sess.default_bucket(), "pda/xgb"
    s3_train = sess.upload_data(str(ROOT / "data/training/xgb_train.csv"), bucket, f"{prefix}/train")
    s3_val = sess.upload_data(str(ROOT / "data/training/xgb_validation.csv"), bucket, f"{prefix}/validation")

    image = sagemaker.image_uris.retrieve("xgboost", sess.boto_region_name, "1.7-1")
    est = Estimator(image, role, instance_count=1, instance_type=a.instance,
                    output_path=f"s3://{bucket}/{prefix}/output", sagemaker_session=sess)
    est.set_hyperparameters(objective="multi:softprob", num_class=len(CLASSES), num_round=300, max_depth=6,
                            eta=0.15, subsample=0.8, colsample_bytree=0.9, eval_metric="mlogloss",
                            early_stopping_rounds=20)
    est.fit({"train": TrainingInput(s3_train, content_type="text/csv"),
             "validation": TrainingInput(s3_val, content_type="text/csv")})
    pred = est.deploy(initial_instance_count=1, instance_type=a.instance, endpoint_name=a.endpoint,
                      serializer=CSVSerializer())

    val = pd.read_csv(ROOT / "data/training/xgb_validation.csv", header=None)
    X, y = val.iloc[:, 1:].to_numpy(), val[0].to_numpy()
    probs = np.vstack([parse(pred.predict(X[i:i + 500])) for i in range(0, len(X), 500)])
    yhat = probs.argmax(axis=1)
    cm = pd.crosstab(pd.Series(y, name="true").map(dict(enumerate(CLASSES))),
                     pd.Series(yhat, name="pred").map(dict(enumerate(CLASSES))))
    out = {"endpoint": a.endpoint, "accuracy": round(float((yhat == y).mean()), 4),
           "confusion_matrix": cm.to_dict()}
    (ART / "xgb_eval.json").write_text(json.dumps(out, indent=2))
    print(cm)
    print(json.dumps({"accuracy": out["accuracy"]}))


if __name__ == "__main__":
    main()
