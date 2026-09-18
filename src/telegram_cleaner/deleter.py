from collections.abc import Callable, Iterator
from typing import Any

from telethon import errors

from .models import DialogInventory
from .scanner import scan
from .telegram import Report, request


def batches(ids: list[int], size: int = 100) -> Iterator[list[int]]:
    if not 1 <= size <= 100:
        raise ValueError("Batch size must be between 1 and 100")
    for offset in range(0, len(ids), size):
        yield ids[offset : offset + size]


async def delete_batch(
    client: Any,
    peer: Any,
    ids: list[int],
    dialog: DialogInventory,
    checkpoint: Callable[[], None],
    report: Report,
) -> None:
    try:
        await request(lambda: client.delete_messages(peer, ids, revoke=True), report)
    except errors.UnauthorizedError:
        raise
    except (errors.ChatAdminRequiredError, errors.ForbiddenError):
        raise  # Skip the dialog rather than hammering every ID with a permission failure.
    except errors.BadRequestError as exc:
        if len(ids) > 1:
            middle = len(ids) // 2
            await delete_batch(client, peer, ids[:middle], dialog, checkpoint, report)
            await delete_batch(client, peer, ids[middle:], dialog, checkpoint, report)
            return
        dialog.failed_ids = sorted(set(dialog.failed_ids) | set(ids))
        dialog.last_error = type(exc).__name__
    except (TimeoutError, errors.RPCError, OSError) as exc:
        dialog.failed_ids = sorted(set(dialog.failed_ids) | set(ids))
        dialog.last_error = type(exc).__name__
    else:
        dialog.deleted_ids = sorted(set(dialog.deleted_ids) | set(ids))
        dialog.failed_ids = sorted(set(dialog.failed_ids) - set(ids))
    checkpoint()


async def delete_dialog(
    client: Any,
    me: Any,
    peer: Any,
    dialog: DialogInventory,
    private_mode: str,
    size: int,
    verify: bool,
    checkpoint: Callable[[], None],
    report: Report,
) -> None:
    if not dialog.scan_complete:
        return
    dialog.delete_complete = False
    dialog.verified = False
    dialog.last_error = None
    try:
        # Only IDs in the confirmed inventory are eligible for deletion. Newly arrived
        # messages are recorded by verification and require another confirmation.
        approved = set(dialog.message_ids)
        for attempt in range(3 if verify else 1):
            for batch in batches(dialog.pending, size):
                await delete_batch(client, peer, batch, dialog, checkpoint, report)
                report(
                    f"Peer {dialog.peer_id}: {len(dialog.deleted_ids)} deletion requests accepted."
                )
            if not verify:
                dialog.delete_complete = not dialog.pending
                break
            visible = await scan(client, me, peer, dialog, private_mode, checkpoint, report)
            # Absence is not proof that our request removed the message: another
            # participant may have removed it while this job was running.
            dialog.absent_ids = sorted(set(dialog.message_ids) - visible - set(dialog.deleted_ids))
            if not visible:
                dialog.failed_ids.clear()
                dialog.delete_complete = True
                dialog.verified = True
                dialog.last_error = None
                break
            dialog.deleted_ids = sorted(set(dialog.deleted_ids) - visible)
            dialog.failed_ids = sorted(visible)
            if visible - approved:
                dialog.last_error = "New messages found; resume and confirm updated inventory"
                break
            if attempt == 2:
                dialog.last_error = "Matching messages remain after three verification passes"
    except errors.UnauthorizedError:
        raise
    except (TimeoutError, errors.RPCError, OSError, ValueError) as exc:
        dialog.last_error = type(exc).__name__
        dialog.failed_ids = sorted(set(dialog.failed_ids) | set(dialog.pending))
    finally:
        checkpoint()
