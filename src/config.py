"""App configuration, loaded from environment variables (and a local .env file)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",  # read .env locally; in Cloud Run values come from the env
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ignore unknown env vars instead of raising
    )

    # GCP
    gcp_project_id: str = ""
    gcp_region: str = "europe-west3"

    # Cloud Storage
    gcs_bucket_name: str = ""

    # BigQuery datasets
    bq_dataset_raw: str = "solana_raw"
    bq_dataset_staging: str = "solana_staging"
    bq_dataset_intermediate: str = "solana_intermediate"
    bq_dataset_marts: str = "solana_marts"

    # GCP authentication
    google_application_credentials: str = ""

    # Application
    log_level: str = "INFO"
    environment: str = "local"


# import this shared instance everywhere: `from src.config import settings`
settings = Settings()
