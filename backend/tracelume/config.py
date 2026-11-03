from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRACELUME_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/tracelume.db"
    redis_url: str = "redis://localhost:6379/0"
    # "rq" uses Redis + RQ workers; "inline" runs jobs in-process (dev/tests only).
    job_queue: str = "inline"
    # "docker" runs tool images; "local" runs the plugin's local fallback (tests only).
    runner: str = "docker"
    evidence_dir: Path = Path("./data/evidence")
    workspace_dir: Path = Path("./data/workspace")
    import_dir: Path = Path("./data/import")
    backups_dir: Path = Path("./data/backups")
    # Set by the Linux launcher when USB passthrough is available (iPhone acquisition)
    usb_acquisition: bool = False
    plugins_dir: Path = Path(__file__).resolve().parents[2] / "plugins"
    examiner: str = "examiner"
    # Registry prefix for tool images: "ghcr.io/0xs3j4d" -> ghcr.io/0xs3j4d/tracelume/aleapp
    image_registry: str = ""
    # Host names the UI may be reached under (DNS-rebinding protection); "*" disables the check
    allowed_hosts: str = "localhost,127.0.0.1,::1,api,testserver"
    # Docker volume names, used when the worker runs inside compose.
    evidence_volume: str | None = None
    workspace_volume: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
