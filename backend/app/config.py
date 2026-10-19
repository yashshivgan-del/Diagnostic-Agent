"""Configuration from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _b(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _f(name: str, default: str) -> float:
    return float(os.getenv(name, default))


def _i(name: str, default: str) -> int:
    return int(os.getenv(name, default))


def normalize_recipe_id(value: str | None) -> str:
    """Accept a bare recipe id or a full webhook URL (".../api/webhook/recipe/<id>")
    and return just the final id segment (query string stripped)."""
    return (value or "").strip().rstrip("/").split("/")[-1].split("?")[0]


@dataclass(frozen=True)
class Settings:
    # Database (backend login: pda_app)
    database_url: str = os.getenv("DATABASE_URL", "postgresql://pda_app:CHANGE_ME_app_password@localhost:5432/pda")

    # Inference: synthetic (no AWS, NOT an ML prediction) | sagemaker (RCF + XGBoost endpoints)
    inference_mode: str = os.getenv("INFERENCE_MODE", "synthetic").lower()
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    rcf_endpoint: str = os.getenv("RCF_ENDPOINT_NAME", "pda-rcf")
    xgb_endpoint: str = os.getenv("XGB_ENDPOINT_NAME", "pda-xgb")
    rcf_scaler_json: str = os.getenv("RCF_SCALER_JSON", "")
    threshold_synthetic: float = _f("ANOMALY_THRESHOLD_SYNTHETIC", "2.5")
    threshold_rcf: float = _f("ANOMALY_THRESHOLD_RCF", "3.0")
    inference_timeout_s: float = _f("INFERENCE_TIMEOUT_S", "8")

    # Simulation
    sim_interval_s: float = _f("SIM_INTERVAL_S", "10")
    run_max_seconds: int = _i("RUN_MAX_SECONDS", "600")          # auto-stop after 10 minutes
    max_active_runs: int = _i("MAX_ACTIVE_RUNS", "60")

    # Trigger rule: confirmed anomaly = CONFIRM_MIN of the last CONFIRM_WINDOW readings anomalous.
    confirm_window: int = _i("CONFIRM_WINDOW", "3")
    confirm_min: int = _i("CONFIRM_MIN", "2")
    rearm_normal_readings: int = _i("REARM_NORMAL_READINGS", "3")  # normal readings before the next trigger
    max_triggers_per_run: int = _i("MAX_TRIGGERS_PER_RUN", "8")
    email_cap_per_run: int = _i("EMAIL_CAP_PER_RUN", "5")

    # Karini (one recipe for everyone). Webhook API per the Karini framework guide.
    karini_enabled: bool = _b("KARINI_ENABLED", "true")
    karini_base_url: str = os.getenv("KARINI_BASE_URL", "https://app.karini.ai").rstrip("/")
    # Accept either the bare recipe id or a full webhook URL pasted by mistake
    # (".../api/webhook/recipe/<id>"): keep only the final path segment.
    karini_recipe_id: str = normalize_recipe_id(os.getenv("KARINI_RECIPE_ID", ""))
    karini_api_token: str = os.getenv("KARINI_API_TOKEN", "")
    karini_max_concurrent: int = _i("KARINI_MAX_CONCURRENT", "10")
    karini_post_timeout_s: float = _f("KARINI_POST_TIMEOUT_S", "15")
    karini_post_retries: int = _i("KARINI_POST_RETRIES", "3")
    karini_poll_interval_s: float = _f("KARINI_POLL_INTERVAL_S", "15")
    karini_execution_timeout_s: int = _i("KARINI_EXECUTION_TIMEOUT_S", "600")
    karini_first_agent: str = os.getenv("KARINI_FIRST_AGENT", "evidence_gatherer")

    @property
    def threshold(self) -> float:
        return self.threshold_synthetic if self.inference_mode == "synthetic" else self.threshold_rcf

    @property
    def karini_configured(self) -> bool:
        """True if the backend has a global default recipe (per-run creds can still override)."""
        return bool(self.karini_enabled and self.karini_recipe_id and self.karini_api_token)

    def karini_creds_for(self, run: dict | None = None) -> dict | None:
        """Effective Karini creds for a run: the run's own values, else the global env default.
        Returns {base_url, recipe_id, api_token} or None when nothing is configured.
        A per-run base_url/recipe_id may be a full webhook URL; it is normalised to id only."""
        if not self.karini_enabled:
            return None
        run = run or {}
        base = (run.get("karini_base_url") or self.karini_base_url or "").strip().rstrip("/")
        recipe = normalize_recipe_id(run.get("karini_recipe_id") or self.karini_recipe_id)
        token = (run.get("karini_api_token") or self.karini_api_token or "").strip()
        if not (base and recipe and token):
            return None
        return {"base_url": base, "recipe_id": recipe, "api_token": token}

    def public(self) -> dict:
        return {
            "inference_mode": self.inference_mode,
            "threshold": self.threshold,
            "sim_interval_s": self.sim_interval_s,
            "run_max_seconds": self.run_max_seconds,
            "confirm_rule": f"{self.confirm_min} of last {self.confirm_window} readings",
            "email_cap_per_run": self.email_cap_per_run,
            "max_triggers_per_run": self.max_triggers_per_run,
            "karini_configured": self.karini_configured,
        }


settings = Settings()
