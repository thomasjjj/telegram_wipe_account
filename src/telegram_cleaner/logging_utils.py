import logging
from pathlib import Path


def configure(directory: Path, verbose: bool) -> logging.Logger:
    """Only application-generated metadata is logged; never RPC exception contents."""
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("telegram_cleaner")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(directory / "cleaner.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    # Telethon DEBUG output can include protocol details. Do not enable it.
    logging.getLogger("telethon").setLevel(logging.CRITICAL)
    return logger
