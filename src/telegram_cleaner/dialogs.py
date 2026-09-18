from typing import Any

from telethon import errors, types, utils

from .models import DialogInventory, DialogKind, Job
from .telegram import Report, flood_wait


def classify(entity: Any, me_id: int) -> DialogKind:
    if isinstance(entity, types.User):
        if entity.id == me_id:
            return DialogKind.SELF
        return DialogKind.BOT if entity.bot else DialogKind.PRIVATE
    if isinstance(entity, types.Chat):
        return DialogKind.GROUP
    if isinstance(entity, types.Channel):
        return DialogKind.GROUP if entity.megagroup else DialogKind.CHANNEL
    return DialogKind.UNKNOWN


def in_scope(kind: DialogKind, scope: str) -> bool:
    return kind != DialogKind.UNKNOWN and (
        scope == "all" or kind in {DialogKind.GROUP, DialogKind.CHANNEL}
    )


async def discover(client: Any, me: Any, job: Job, report: Report) -> dict[int, Any]:
    peers: dict[int, Any] = {}
    job.discovery_errors.clear()
    for folder in [0, 1] if job.include_archived else [0]:
        while True:
            try:
                # Keep migrated basic groups: their old history can contain unique messages.
                async for dialog in client.iter_dialogs(folder=folder, ignore_migrated=False):
                    try:
                        peer_id = utils.get_peer_id(dialog.entity)
                    except (TypeError, ValueError):
                        job.discovery_errors.append("Unsupported entity without a stable peer ID")
                        continue
                    if peer_id in peers:
                        continue
                    kind = classify(dialog.entity, me.id)
                    if kind == DialogKind.UNKNOWN:
                        job.discovery_errors.append(f"Unsupported peer {peer_id}")
                    if not in_scope(kind, job.scope):
                        continue
                    peers[peer_id] = dialog.input_entity
                    job.dialogs.setdefault(
                        str(peer_id), DialogInventory(peer_id, dialog.name or str(peer_id), kind)
                    )
                break
            except errors.FloodWaitError as exc:
                await flood_wait(exc, report)
            except errors.UnauthorizedError:
                raise
            except errors.RPCError as exc:
                job.discovery_errors.append(f"Folder {folder}: {type(exc).__name__}")
                break
    if job.scope == "all":
        peers[me.id] = await client.get_input_entity(me)
        job.dialogs.setdefault(
            str(me.id), DialogInventory(me.id, "Saved Messages", DialogKind.SELF)
        )
    job.discovery_complete = not job.discovery_errors
    return peers
