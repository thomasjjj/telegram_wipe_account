from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest
from telethon import types
from test_workflow import ME, Account, arguments

from telegram_cleaner.cli import workflow
from telegram_cleaner.deleter import delete_batch
from telegram_cleaner.dialogs import discover
from telegram_cleaner.exclusions import apply_exclusions, parse_peer
from telegram_cleaner.models import DialogInventory, DialogKind
from telegram_cleaner.state import load, new_job, save


@pytest.mark.parametrize(
    "value", ["https://t.me/c/123456/", "https://t.me/c/123456/12", "-1000000123456"]
)
def test_private_channel_link_mapping(value):
    assert parse_peer(value) == -1000000123456


async def test_excluded_chats_never_scanned_deleted_or_verified_and_resume_keeps_them(
    tmp_path, monkeypatch
):
    prompt = Mock(side_effect=["delete", "DELETE 2", "delete", "DELETE 0"])
    monkeypatch.setattr("telegram_cleaner.cli.Prompt.ask", prompt)
    client = Account()
    args = arguments(tmp_path, "--exclude-chat=2", "--exclude-chat=-4")
    assert await workflow(client, ME, args) == 0
    assert 2 not in client.scanned and -4 not in client.scanned
    assert all(peer not in {2, -4} for peer, _ in client.deleted)
    path = next(tmp_path.glob("*.json"))
    job = load(path, 1)
    assert job.excluded_peer_ids == [-4, 2]
    assert "2" not in job.dialogs and "-4" not in job.dialogs
    # Even an old/merged row cannot override persisted exclusions on resume.
    job.dialogs["2"] = DialogInventory(
        2, "preserve", DialogKind.PRIVATE, [20, 21], scan_complete=True
    )
    save(job, path)
    assert await workflow(client, ME, arguments(tmp_path, "--resume", str(path))) == 0
    assert 2 not in client.scanned and -4 not in client.scanned
    assert [m.id for m in client.history[2]] == [20, 21]
    assert [m.id for m in client.history[-4]] == [40, 41]


async def test_migrated_legacy_chat_inherits_protection():
    chat = types.Chat(
        4, "legacy", types.ChatPhotoEmpty(), 2, None, 1, migrated_to=types.InputChannel(123456, 99)
    )

    async def dialogs(**kwargs):
        yield NS(entity=chat, input_entity=types.InputPeerChat(4), name="legacy")

    job = new_job(1, "groups-channels", False, "both")
    apply_exclusions(job, [-1000000123456])
    job.dialogs["-4"] = DialogInventory(-4, "legacy", DialogKind.GROUP, [50], scan_complete=True)
    assert await discover(NS(iter_dialogs=dialogs), NS(id=1), job, Mock()) == {}
    assert -4 in job.excluded_peer_ids and "-4" not in job.dialogs


async def test_deletion_boundary_refuses_preserved_input_peer():
    client = NS(delete_messages=AsyncMock())
    dialog = DialogInventory(-9, "mismatch", DialogKind.GROUP, [1])
    with pytest.raises(ValueError, match="preserved"):
        await delete_batch(
            client,
            types.InputPeerChannel(123456, 99),
            [1],
            dialog,
            Mock(),
            Mock(),
            frozenset({-1000000123456}),
        )
    client.delete_messages.assert_not_awaited()
