import asyncio
from collections.abc import Callable
from typing import Any

from telethon import errors, types

from .models import DialogInventory, DialogKind
from .telegram import Report, flood_wait


def eligible(message: Any, me_id: int, kind: DialogKind, private_mode: str) -> bool:
    if isinstance(message, types.MessageEmpty) or not getattr(message, "id", None):
        return False
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
    dialog.scan_complete = False
    dialog.last_error = None
    while True:
        try:
            kwargs = {"offset_id": offset}
            if filtered:
                kwargs["from_user"] = me
            async for message in client.iter_messages(peer, **kwargs):
                offset = message.id
                if eligible(message, me.id, dialog.kind, private_mode):
                    found.add(message.id)
                    if message.id not in known:
                        known.add(message.id)
                        dialog.message_ids.append(message.id)
                        if len(known) % 100 == 0:
                            checkpoint()
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
