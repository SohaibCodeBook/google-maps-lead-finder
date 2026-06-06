from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Google Maps Scraper"
    debug: bool = False
    default_max_results: int = 20
    min_delay_seconds: float = 1.0
    max_delay_seconds: float = 3.0
    page_timeout_ms: int = 30_000
    navigation_timeout_ms: int = 60_000
    headless: bool = True
    google_maps_url: str = "https://www.google.com/maps"


settings = Settings()
