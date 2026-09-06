from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str
    api_base_url: str = "http://api:8000"
    internal_bot_token: str
    public_web_origin: str = "https://shnenepepe.online"


settings = Settings()  # type: ignore[call-arg]
