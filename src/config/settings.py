from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
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

    # Prefect Cloud
    prefect_api_key: str = ""
    prefect_api_url: str = ""
    prefect_workspace_id: str = ""

    # Application
    log_level: str = "INFO"
    environment: str = "local"


settings = Settings()
