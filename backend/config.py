"""Runtime config, loaded from env.

Kept deliberately small — anything that looks like it needs a whole "config service"
probably belongs in a feature flag store (phase 6), not here.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- env / logging ---
    api_env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    api_secret_key: str = Field(default="dev-secret-do-not-use-in-prod")
    api_port: int = 8000

    # --- datastores ---
    postgres_url: str = "postgresql+psycopg://allgreen:changeme@postgres:5432/allgreen"
    redis_url: str = "redis://redis:6379/0"
    kafka_bootstrap_servers: str = "kafka:9092"

    # --- ML ---
    mlflow_tracking_uri: str = "http://mlflow:5000"
    lstm_model_path: str = "/app/ml/lstm/artifacts/model.pt"
    xgboost_model_path: str = "/app/ml/xgboost/artifacts/model.json"

    # --- optional graph DB ---
    graph_db_url: str = "bolt://neo4j:7687"
    graph_db_enabled: bool = False

    # --- feature flags ---
    personalized_lstm_enabled: bool = True
    min_sessions_for_personalized: int = 50

    @property
    def is_prod(self) -> bool:
        return self.api_env == "prod"


@lru_cache
def get_settings() -> Settings:
    # lru_cache so we only read env once per process.
    return Settings()
