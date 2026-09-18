from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest
from telethon import errors

from telegram_cleaner.deleter import delete_dialog
from telegram_cleaner.models import DialogInventory, DialogKind
from telegram_cleaner.scanner import scan


async def test_filtered_search_fallback_keeps_sender_check():
    calls = []

    async def messages(peer, **kwargs):
        calls.append(kwargs)
        if "from_user" in kwargs:
            raise errors.SearchQueryEmptyError(None)
        yield NS(id=2, sender_id=99, out=True)
        yield NS(id=1, sender_id=1)

    d = DialogInventory(-10, "group", DialogKind.GROUP)
    result = await scan(NS(iter_messages=messages), NS(id=1), -10, d, "both", Mock(), Mock())
    assert result == {1}
    assert d.fallback and d.scan_complete
    assert len(calls) == 2


async def test_scan_flood_continues_offset(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    calls = []

    async def messages(peer, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            yield NS(id=3, sender_id=1)
            raise errors.FloodWaitError(None, capture=1)
        yield NS(id=2, sender_id=1)

    d = DialogInventory(2, "p", DialogKind.PRIVATE)
    assert await scan(NS(iter_messages=messages), NS(id=1), 2, d, "both", Mock(), Mock()) == {2, 3}
    assert calls[1]["offset_id"] == 3


async def test_verification_stops_after_three_passes():
    async def messages(peer, **kwargs):
        yield NS(id=1, sender_id=1)

    client = NS(iter_messages=messages, delete_messages=AsyncMock())
    d = DialogInventory(2, "p", DialogKind.PRIVATE, [1], scan_complete=True)
    await delete_dialog(client, NS(id=1), 2, d, "both", 100, True, Mock(), Mock())
    assert client.delete_messages.await_count == 3
    assert d.failed_ids == [1]
    assert not d.verified and not d.delete_complete


async def test_transient_scan_is_bounded(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr("asyncio.sleep", sleep)
    calls = []

    async def messages(peer, **kwargs):
        calls.append(kwargs)
        raise errors.ServerError(None, "secret error content")
        yield  # pragma: no cover -- defines an async generator

    d = DialogInventory(2, "p", DialogKind.PRIVATE)
    with pytest.raises(errors.ServerError):
        await scan(NS(iter_messages=messages), NS(id=1), 2, d, "both", Mock(), Mock())
    assert len(calls) == 3
    assert d.last_error == "ServerError"
    assert not d.scan_complete


async def test_failed_verification_does_not_claim_complete():
    async def messages(peer, **kwargs):
        raise errors.ChannelPrivateError(None)
        yield  # pragma: no cover

    client = NS(iter_messages=messages, delete_messages=AsyncMock())
    d = DialogInventory(2, "p", DialogKind.PRIVATE, [1], scan_complete=True)
    await delete_dialog(client, NS(id=1), 2, d, "both", 100, True, Mock(), Mock())
    assert not d.verified and not d.delete_complete and not d.scan_complete
    assert d.last_error == "ChannelPrivateError"


async def test_absent_failed_id_is_not_reported_as_our_deletion():
    async def messages(peer, **kwargs):
        return
        yield  # pragma: no cover

    client = NS(
        iter_messages=messages,
        delete_messages=AsyncMock(side_effect=errors.MessageIdInvalidError(None)),
    )
    d = DialogInventory(2, "p", DialogKind.PRIVATE, [1], scan_complete=True)
    await delete_dialog(client, NS(id=1), 2, d, "both", 100, True, Mock(), Mock())
    assert d.verified and not d.pending and not d.failed_ids
    assert d.deleted_ids == []
    assert d.absent_ids == [1]
