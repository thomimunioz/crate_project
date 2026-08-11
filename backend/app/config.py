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
    # AcoustID: identificación por huella acústica. Gratis en https://acoustid.org/new-application
    acoustid_key: str = ""
    # Ruta absoluta a fpcalc (Chromaprint). Vacío = se busca en el PATH.
    fpcalc_path: str = ""
    analyze_seconds: int = 45
    # La huella matchea mucho mejor con ~2 min desde el arranque (es el largo por
    # defecto de chromaprint) que con los 45s que le alcanzan a BPM/key.
    identify_seconds: int = 120
    tmp_dir: str = "./tmp"
    app_user_agent: str = "CRATE/0.1 (personal digging tool)"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def allowlist(self) -> list[str]:
        return [h.strip().lower() for h in self.proxy_allowlist.split(",") if h.strip()]


settings = Settings()
