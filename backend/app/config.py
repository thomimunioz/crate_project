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
    # Runtime JS para yt-dlp ("node", "deno" o "node:C:\ruta\node.exe"). Vacío = autodetectar
    # (deno primero, node después). Ver app/ytdl.py.
    js_runtime: str = ""
    # ffmpeg (archivo o carpeta bin). Vacío = el del PATH. Recorta la ventana a WAV.
    ffmpeg_path: str = ""
    # cookies.txt (formato Netscape, exportado del navegador) para yt-dlp. Es la salida al
    # bot-check de YouTube ("Sign in to confirm you're not a bot") cuando la IP quedó
    # marcada. Vacío = sin cookies.
    ytdlp_cookies: str = ""
    # Cuánto tiempo /health sigue diciendo "YouTube bloqueó esta IP" después del último
    # bot-check (segundos). Es un cooldown para no invitar a insistir, no una verdad:
    # una descarga que ande lo levanta antes.
    youtube_block_cooldown_sec: int = 900
    # Ventana de BPM/key: cuántos segundos. Dónde arranca lo decide el request o, si no
    # manda start_sec, dsp.smart_start() (60 s, o el 20% en tracks cortos).
    analyze_seconds: int = 45
    # Tope para cada recorte con ffmpeg (segundos de reloj, no de audio).
    ffmpeg_timeout_sec: int = 120
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
