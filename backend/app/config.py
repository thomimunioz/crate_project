"""Config del backend. Lee variables CRATE_* del entorno / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CRATE_",
        env_file=("../.env", ".env"),
        extra="ignore",
    )

    allowed_origins: str = "http://localhost:5173"
    proxy_allowlist: str = "api.discogs.com,musicbrainz.org,archive.org"
    # Discogs: consumer key + secret → 60 req/min en vez de 25.
    # Viven en el backend a propósito: un VITE_ se inlinea en el bundle público.
    discogs_key: str = ""
    discogs_secret: str = ""
    analyze_seconds: int = 45
    tmp_dir: str = "./tmp"
    app_user_agent: str = "CRATE/0.1 (personal digging tool)"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def allowlist(self) -> list[str]:
        return [h.strip().lower() for h in self.proxy_allowlist.split(",") if h.strip()]


settings = Settings()
