from dataclasses import dataclass, field
from enum import Enum


class DialogKind(str, Enum):
    GROUP = "group"
    CHANNEL = "channel"
    BOT = "bot"
    PRIVATE = "private"
    SELF = "self"
    UNKNOWN = "unknown"


@dataclass
class DialogInventory:
    peer_id: int
    title: str
    kind: DialogKind
    message_ids: list[int] = field(default_factory=list)
    deleted_ids: list[int] = field(default_factory=list)
    failed_ids: list[int] = field(default_factory=list)
    scan_complete: bool = False
    delete_complete: bool = False
    verified: bool = False
    last_error: str | None = None
    fallback: bool = False

    @property
    def pending(self) -> list[int]:
        done = set(self.deleted_ids)
        return [mid for mid in self.message_ids if mid not in done]


@dataclass
class Job:
    account_id: int
    scope: str
    include_archived: bool
    private_mode: str
    started_at: str
    dialogs: dict[str, DialogInventory] = field(default_factory=dict)
    schema_version: int = 1
    status: str = "inventory"
    discovery_complete: bool = False
    discovery_errors: list[str] = field(default_factory=list)
