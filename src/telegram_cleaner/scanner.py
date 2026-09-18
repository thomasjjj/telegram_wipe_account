import asyncio
from collections.abc import Callable
from typing import Any

from telethon import errors, types

from .models import DialogInventory, DialogKind
from .progress import ProgressCallback, ProgressEvent, quiet_progress
from .telegram import Report, flood_wait


def eligible(message: Any, me_id: int, kind: DialogKind, private_mode: str) -> bool:
    if isinstance(message, types.MessageEmpty) or not getattr(message, "id", None):
        return False
    if isinstance(getattr(message, "action", None), types.MessageActionHistoryClear):
        return False  # Telegram's history-cleared marker is not a surviving message.
    if kind == DialogKind.SELF:
        return True
    if kind == DialogKind.PRIVATE and private_mode == "both":
        return True
    return getattr(message, "sender_id", None) == me_id


async def scan(
    client: Any,
    me: Any,
    peer: Any,
    dialog: DialogInventory,
    private_mode: str,
    checkpoint: Callable[[], None],
    report: Report,
    progress: ProgressCallback = quiet_progress,
    phase: str = "Scanning messages",
) -> set[int]:
    """Checkpoint IDs while scanning; never persist text or media."""
    full = dialog.kind == DialogKind.SELF or (
        dialog.kind == DialogKind.PRIVATE and private_mode == "both"
    )
    filtered = not full and not dialog.fallback
    found: set[int] = set()
    known = set(dialog.message_ids)
    offset = 0
    retries = 0
    examined = 0
    search_mode = "full history"
    if filtered:
        search_mode = (
            "local sender filter"
            if dialog.kind in {DialogKind.PRIVATE, DialogKind.BOT}
            else "server sender search"
        )
    progress(ProgressEvent(phase, detail=search_mode))
    dialog.scan_complete = False
    dialog.last_error = None
    while True:
        try:
            kwargs = {"offset_id": offset}
            if filtered:
                kwargs["from_user"] = me
            async for message in client.iter_messages(peer, **kwargs):
                examined += 1
                offset = message.id
                if isinstance(getattr(message, "action", None), types.MessageActionHistoryClear):
                    if message.id not in dialog.ignored_ids:
                        dialog.ignored_ids.append(message.id)
                    dialog.failed_ids = [mid for mid in dialog.failed_ids if mid != message.id]
                if eligible(message, me.id, dialog.kind, private_mode):
                    found.add(message.id)
                    if message.id not in known:
                        known.add(message.id)
                        dialog.message_ids.append(message.id)
                        if len(known) % 100 == 0:
                            checkpoint()
                if examined % 100 == 0:
                    progress(ProgressEvent(phase, examined, detail=f"{len(found)} matching IDs"))
            progress(
                ProgressEvent(phase, examined, detail=f"{len(found)} matching IDs", finished=True)
            )
            dialog.scan_complete = True
            dialog.last_error = None
            checkpoint()
            return found
        except errors.FloodWaitError as exc:
            checkpoint()
            await flood_wait(exc, report)
        except errors.UnauthorizedError:
            raise
        except (errors.ServerError, errors.RpcCallFailError, OSError) as exc:
            retries += 1
            dialog.last_error = type(exc).__name__
            checkpoint()
            if retries >= 3:
                raise
            await asyncio.sleep(retries)
        except (errors.BadRequestError, errors.ForbiddenError) as exc:
            if filtered:
                filtered = False
                dialog.fallback = True
                offset = 0
                report(f"Peer {dialog.peer_id}: fallback full-history scan (slower).")
                continue
            dialog.last_error = type(exc).__name__
            checkpoint()
            raise
