import json
import os
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .models import DialogInventory, DialogKind, Job


def new_job(account_id: int, scope: str, archived: bool, private_mode: str) -> Job:
    return Job(account_id, scope, archived, private_mode, datetime.now(UTC).isoformat())


def new_path(directory: Path) -> Path:
    return directory / f"cleanup_{datetime.now(UTC):%Y%m%dT%H%M%S}_{uuid4().hex[:8]}.json"


def save(job: Job, path: Path) -> None:
    """Replace the checkpoint only after the new contents have reached disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(asdict(job), stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def load(path: Path, account_id: int) -> Job:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported checkpoint schema")
    if data.get("account_id") != account_id:
        raise ValueError("Checkpoint belongs to a different Telegram account")
    if data.get("scope") not in {"all", "groups-channels"}:
        raise ValueError("Invalid checkpoint scope")
    if data.get("private_mode") not in {"both", "own"}:
        raise ValueError("Invalid private-chat mode")
    if any(type(peer) is not int or peer == 0 for peer in data.get("excluded_peer_ids", [])):
        raise ValueError("Invalid excluded peer ID")
    dialogs = {}
    for key, value in data.pop("dialogs").items():
        value["kind"] = DialogKind(value["kind"])
        dialog = DialogInventory(**value)
        if str(dialog.peer_id) != key:
            raise ValueError("Checkpoint peer mismatch")
        for ids in (dialog.message_ids, dialog.deleted_ids, dialog.failed_ids, dialog.absent_ids):
            if any(type(mid) is not int or mid <= 0 for mid in ids):
                raise ValueError("Invalid checkpoint message ID")
        dialogs[key] = dialog
    return Job(**data, dialogs=dialogs)
