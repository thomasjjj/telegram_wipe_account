import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest
from telethon import errors, types

from telegram_cleaner.deleter import batches, delete_batch, delete_dialog
from telegram_cleaner.dialogs import classify, discover, in_scope
from telegram_cleaner.models import DialogInventory, DialogKind
from telegram_cleaner.scanner import eligible, scan
from telegram_cleaner.state import load, new_job, save


@pytest.mark.parametrize(
    "entity, expected",
    [
        (types.User(1), DialogKind.SELF),
        (types.User(2, bot=True), DialogKind.BOT),
        (types.User(3), DialogKind.PRIVATE),
        (types.Chat(1, "g", types.ChatPhotoEmpty(), 2, None, 1), DialogKind.GROUP),
        (types.Channel(1, "g", types.ChatPhotoEmpty(), None, megagroup=True), DialogKind.GROUP),
        (types.Channel(2, "c", types.ChatPhotoEmpty(), None, broadcast=True), DialogKind.CHANNEL),
        (object(), DialogKind.UNKNOWN),
    ],
)
def test_classification(entity, expected):
    assert classify(entity, 1) == expected


def test_scopes():
    assert {k for k in DialogKind if in_scope(k, "groups-channels")} == {
        DialogKind.GROUP,
        DialogKind.CHANNEL,
    }
    assert {k for k in DialogKind if in_scope(k, "all")} == set(DialogKind) - {DialogKind.UNKNOWN}


@pytest.mark.parametrize(
    "count, sizes",
    [(0, []), (1, [1]), (99, [99]), (100, [100]), (101, [100, 1]), (250, [100, 100, 50])],
)
def test_batches(count, sizes):
    assert [len(batch) for batch in batches(list(range(count)))] == sizes


def test_eligibility():
    incoming = NS(id=1, sender_id=2, out=False)
    anonymous = NS(id=2, sender_id=-1001, out=True)
    assert eligible(incoming, 1, DialogKind.PRIVATE, "both")
    assert not eligible(incoming, 1, DialogKind.PRIVATE, "own")
    assert not eligible(incoming, 1, DialogKind.BOT, "both")
    assert not eligible(anonymous, 1, DialogKind.CHANNEL, "both")
    assert eligible(incoming, 1, DialogKind.SELF, "both")


def test_state_atomic_and_account(tmp_path, monkeypatch):
    job = new_job(1, "all", True, "both")
    d = DialogInventory(2, "private", DialogKind.PRIVATE, [1, 2, 3], [1], [3])
    job.dialogs["2"] = d
    path = tmp_path / "job.json"
    save(job, path)
    assert load(path, 1) == job
    assert load(path, 1).dialogs["2"].pending == [2, 3]
    with pytest.raises(ValueError, match="different"):
        load(path, 2)
    monkeypatch.setattr("telegram_cleaner.state.os.replace", Mock(side_effect=OSError))
    job.status = "deleting"
    with pytest.raises(OSError):
        save(job, path)
    assert load(path, 1).status == "inventory"
    assert list(tmp_path.glob("*.tmp")) == []


class FakeClient:
    def __init__(self, messages):
        self.messages = list(messages)
        self.searches = []
        self.calls = []

    async def iter_messages(self, peer, **kwargs):
        self.searches.append((peer, kwargs))
        for message in self.messages:
            yield message

    async def delete_messages(self, peer, ids, revoke):
        self.calls.append((peer, ids, revoke))
        self.messages = [m for m in self.messages if m.id not in ids]


async def test_scan_own_and_private_both():
    client = FakeClient([NS(id=1, sender_id=1), NS(id=2, sender_id=2)])
    group = DialogInventory(-1, "group", DialogKind.GROUP)
    assert await scan(client, NS(id=1), -1, group, "both", Mock(), Mock()) == {1}
    assert client.searches[0][1]["from_user"].id == 1
    private = DialogInventory(2, "private", DialogKind.PRIVATE)
    assert await scan(client, NS(id=1), 2, private, "both", Mock(), Mock()) == {1, 2}
    assert "from_user" not in client.searches[-1][1]
    assert not client.calls


async def test_delete_verified_and_resume(tmp_path):
    client = FakeClient([NS(id=2, sender_id=1), NS(id=3, sender_id=1)])
    job = new_job(1, "all", True, "both")
    d = DialogInventory(2, "p", DialogKind.PRIVATE, [1, 2, 3], [1], scan_complete=True)
    job.dialogs["2"] = d
    path = tmp_path / "job.json"
    await delete_dialog(client, NS(id=1), 2, d, "both", 100, True, lambda: save(job, path), Mock())
    assert client.calls == [(2, [2, 3], True)]
    assert d.verified and d.delete_complete
    assert load(path, 1).dialogs["2"].deleted_ids == [1, 2, 3]


async def test_bad_id_split():
    client = NS(delete_messages=AsyncMock())

    async def remove(peer, ids, revoke):
        if 2 in ids:
            raise errors.MessageIdInvalidError(None)

    client.delete_messages.side_effect = remove
    d = DialogInventory(2, "p", DialogKind.PRIVATE, [1, 2, 3])
    await delete_batch(client, 2, [1, 2, 3], d, Mock(), Mock())
    assert d.deleted_ids == [1, 3]
    assert d.failed_ids == [2]
    assert all(call.kwargs["revoke"] for call in client.delete_messages.call_args_list)


async def test_flood_and_transient(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr("asyncio.sleep", sleep)
    client = NS(
        delete_messages=AsyncMock(
            side_effect=[
                errors.FloodWaitError(None, capture=37),
                errors.ServerError(None, "transient"),
                None,
            ]
        )
    )
    d = DialogInventory(2, "p", DialogKind.PRIVATE, [1])
    await delete_batch(client, 2, [1], d, Mock(), Mock())
    assert d.deleted_ids == [1]
    assert 38 <= sleep.call_args_list[0].args[0] <= 40


async def test_permission_and_unauthorized():
    client = NS(delete_messages=AsyncMock(side_effect=errors.ChatAdminRequiredError(None)))
    d = DialogInventory(2, "p", DialogKind.PRIVATE, [1, 2], scan_complete=True)
    await delete_dialog(client, NS(id=1), 2, d, "both", 1, True, Mock(), Mock())
    assert d.failed_ids == [1, 2]
    assert not d.delete_complete
    assert client.delete_messages.await_count == 1
    client.delete_messages.side_effect = errors.AuthKeyUnregisteredError(None)
    with pytest.raises(errors.UnauthorizedError):
        await delete_dialog(client, NS(id=1), 2, d, "both", 1, True, Mock(), Mock())


async def test_interrupt_checkpoint(tmp_path):
    client = NS(delete_messages=AsyncMock(side_effect=[None, KeyboardInterrupt]))
    job = new_job(1, "all", True, "both")
    d = DialogInventory(2, "p", DialogKind.PRIVATE, [1, 2], scan_complete=True)
    job.dialogs["2"] = d
    path = tmp_path / "job.json"
    with pytest.raises(KeyboardInterrupt):
        await delete_dialog(
            client, NS(id=1), 2, d, "both", 1, True, lambda: save(job, path), Mock()
        )
    assert load(path, 1).dialogs["2"].pending == [2]
    assert json.loads(path.read_text())["dialogs"]["2"]["deleted_ids"] == [1]


async def test_verification_new_messages_need_confirmation():
    client = FakeClient([NS(id=1, sender_id=1), NS(id=2, sender_id=2)])
    d = DialogInventory(2, "p", DialogKind.PRIVATE, [1], scan_complete=True)
    await delete_dialog(client, NS(id=1), 2, d, "both", 100, True, Mock(), Mock())
    assert client.calls == [(2, [1], True)]
    assert d.pending == [2]
    assert not d.verified
    assert "confirm" in d.last_error


async def test_archives_and_dedup():
    folders = []

    async def dialogs(**kwargs):
        folders.append(kwargs["folder"])
        yield NS(entity=types.User(2), input_entity=types.InputPeerUser(2, 3), name="p")

    client = NS(
        iter_dialogs=dialogs, get_input_entity=AsyncMock(return_value=types.InputPeerSelf())
    )
    job = new_job(1, "all", True, "both")
    peers = await discover(client, NS(id=1), job, Mock())
    assert folders == [0, 1]
    assert set(peers) == {1, 2}
    assert len(job.dialogs) == 2
