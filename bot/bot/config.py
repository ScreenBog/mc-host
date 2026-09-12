from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "/home/screen/mc-hosting/.env"),
        extra="ignore",
    )

    telegram_bot_token: str = ""
    api_base_url: str = "http://127.0.0.1:8000"
    internal_bot_token: str = "beta-internal"
    public_web_origin: str = "http://192.168.0.7:8000"
    beta_mode: bool = True


settings = Settings()  # type: ignore[call-arg]
