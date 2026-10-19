#!/usr/bin/env python3
"""Delete the demo SageMaker endpoints (they bill per hour while running).

  python ml/cleanup.py            # deletes pda-rcf and pda-xgb
"""
import boto3

sm = boto3.client("sagemaker")
for name in ("pda-rcf", "pda-xgb"):
    try:
        cfg = sm.describe_endpoint(EndpointName=name)["EndpointConfigName"]
        sm.delete_endpoint(EndpointName=name)
        sm.delete_endpoint_config(EndpointConfigName=cfg)
        print(f"deleted {name}")
    except sm.exceptions.ClientError as exc:
        print(f"{name}: {exc.response['Error']['Message']}")
