"""
Configuration persistence for AnimePahe Web Downloader
"""

import os
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from core.paths import normalize_download_path, PathSafetyError
from core.state_store import init_db, load_settings as load_db_settings, save_settings as save_db_settings

logger = logging.getLogger(__name__)

LEGACY_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.json"


def get_default_download_path() -> str:
    """Get the default download path (user's Downloads folder)"""
    if os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            ) as key:
                return winreg.QueryValueEx(
                    key, "{374DE290-123F-4565-9164-39C4925E467B}"
                )[0]
        except Exception:
            pass

    return str(Path.home() / "Downloads")


@dataclass
class Config:
    download_path: str = ""
    max_workers: int = 4
    default_resolution: int = 0

    def __post_init__(self):
        if not self.download_path:
            self.download_path = get_default_download_path()


def load_config(path: Path = LEGACY_CONFIG_PATH) -> Config:
    """Load config from SQLite, with one-time migration from legacy JSON."""
    init_db()

    data = load_db_settings()
    if not data and path.exists():
        try:
            legacy = json.loads(path.read_text(encoding="utf-8"))
            data = {
                "download_path": legacy.get("download_path", ""),
                "max_workers": legacy.get("max_workers", 4),
                "default_resolution": legacy.get("default_resolution", 0),
            }
            save_db_settings(data)
            logger.info("Migrated legacy config.json into SQLite settings store")
        except Exception as e:
            logger.warning("Failed to migrate legacy config from %s: %s", path, e)

    cfg = Config(
        download_path=str(data.get("download_path", "")),
        max_workers=int(data.get("max_workers", 4)),
        default_resolution=int(data.get("default_resolution", 0)),
    )

    try:
        cfg.download_path = normalize_download_path(cfg.download_path)
    except PathSafetyError as e:
        logger.warning("Invalid persisted download path '%s': %s", cfg.download_path, e)
        cfg.download_path = normalize_download_path(get_default_download_path())

    # Ensure normalized value is always persisted.
    save_config(cfg)
    return cfg


def save_config(config: Config, path: Path = LEGACY_CONFIG_PATH) -> None:
    """Save config to SQLite settings storage."""
    try:
        config.download_path = normalize_download_path(config.download_path)
        save_db_settings(
            {
                "download_path": config.download_path,
                "max_workers": int(config.max_workers),
                "default_resolution": int(config.default_resolution),
            }
        )
        logger.info("Config saved to SQLite state store")
    except PathSafetyError as e:
        logger.error("Invalid download path in config save: %s", e)
    except Exception as e:
        logger.error("Failed to save config: %s", e)
