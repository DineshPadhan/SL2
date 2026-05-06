from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SkillBridge Attendance API"
    database_url: str = "sqlite:///./skillbridge.db"
    jwt_secret: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    access_token_expiry_hours: int = 24
    monitoring_token_expiry_hours: int = 1
    monitoring_api_key: str = "monitoring-api-key"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
