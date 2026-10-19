#!/usr/bin/env python3
"""Train locally (no AWS) to sanity-check the synthetic data before paying for SageMaker.

  pip install xgboost scikit-learn pandas
  python ml/local_model_check.py

- XGBoost (same hyperparameters as ml/train_xgboost.py) -> validation accuracy + confusion matrix
- IsolationForest as a local stand-in for RCF (both are tree-based isolation methods; scores
  are NOT comparable to RCF scores, so do not reuse this threshold for the RCF endpoint)
"""
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import IsolationForest

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["normal", "bearing_wear", "cavitation", "seal_leak", "motor_overload", "misalignment"]
FEATURES = ["temperature_c", "vibration_mm_s", "discharge_pressure_bar", "flow_m3h", "motor_current_a", "rpm"]

tr = pd.read_csv(ROOT / "data/training/xgb_train.csv", header=None)
va = pd.read_csv(ROOT / "data/training/xgb_validation.csv", header=None)
clf = xgb.XGBClassifier(objective="multi:softprob", n_estimators=300, max_depth=6, learning_rate=0.15,
                        subsample=0.8, colsample_bytree=0.9, eval_metric="mlogloss", early_stopping_rounds=20)
clf.fit(tr.iloc[:, 1:], tr[0], eval_set=[(va.iloc[:, 1:], va[0])], verbose=False)
pred = clf.predict(va.iloc[:, 1:])
print(f"XGBoost validation accuracy: {(pred == va[0]).mean():.4f}")
print(pd.crosstab(va[0].map(dict(enumerate(CLASSES))).rename("true"),
                  pd.Series(pred).map(dict(enumerate(CLASSES))).rename("pred")))

rcf_train = np.loadtxt(ROOT / "data/training/rcf_train.csv", delimiter=",")
mu, sd = rcf_train.mean(0), rcf_train.std(0)
iso = IsolationForest(n_estimators=200, random_state=0).fit((rcf_train - mu) / sd)
ev = pd.read_csv(ROOT / "data/training/eval_labeled.csv")
s = -iso.score_samples((ev[FEATURES].to_numpy() - mu) / sd)
th = np.quantile(s[ev.is_anomaly == 0], 0.995)
flag = s >= th
tp = (flag & (ev.is_anomaly == 1)).sum()
print(f"\nIsolationForest (RCF stand-in) at 99.5th pct of normal: precision {tp / flag.sum():.3f}, "
      f"recall {tp / ev.is_anomaly.sum():.3f}")
print(ev[ev.is_anomaly == 1].assign(hit=flag[ev.is_anomaly == 1]).groupby("fault_type").hit.mean().round(3))
