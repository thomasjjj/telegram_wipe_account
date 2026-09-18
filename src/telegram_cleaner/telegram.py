import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from telethon import TelegramClient, errors

from .config import Settings

T = TypeVar("T")
Report = Callable[[str], None]


def build_client(settings: Settings) -> TelegramClient:
    return TelegramClient(
        settings.session_name,
        settings.api_id,
        settings.api_hash,
        flood_sleep_threshold=0,
        request_retries=0,
        raise_last_call_error=True,
        receive_updates=False,
    )


async def flood_wait(exc: errors.FloodWaitError, report: Report) -> None:
    seconds = exc.seconds + random.uniform(1, 3)
    report(f"Telegram requested a {exc.seconds}-second flood wait; pausing before retry.")
    await asyncio.sleep(seconds)


async def request(call: Callable[[], Awaitable[T]], report: Report) -> T:
    retries = 0
    while True:
        try:
            return await call()
        except errors.FloodWaitError as exc:
            await flood_wait(exc, report)
        except (TimeoutError, errors.ServerError, errors.RpcCallFailError, OSError):
            retries += 1
            if retries >= 3:
                raise
            await asyncio.sleep(retries)
