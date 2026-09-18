import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv, set_key
from rich.prompt import Confirm, Prompt


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    phone: str | None
    session_name: str


def load_settings(path: Path = Path(".env")) -> Settings:
    load_dotenv(path)
    raw_id = os.getenv("TELEGRAM_API_ID", "").strip()
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()
    prompted = not raw_id or not api_hash
    while True:
        if not raw_id:
            raw_id = Prompt.ask("Telegram API ID")
        try:
            api_id = int(raw_id)
            if api_id <= 0:
                raise ValueError
            break
        except ValueError:
            raw_id = ""
            prompted = True
    while not api_hash:
        api_hash = Prompt.ask("Telegram API hash", password=True).strip()
    if prompted and Confirm.ask("Save API credentials to .env?", default=False):
        path.touch(mode=0o600, exist_ok=True)
        set_key(str(path), "TELEGRAM_API_ID", str(api_id))
        set_key(str(path), "TELEGRAM_API_HASH", api_hash)
    return Settings(
        api_id,
        api_hash,
        os.getenv("TELEGRAM_PHONE") or None,
        os.getenv("TELEGRAM_SESSION") or "telegram_cleaner",
    )
