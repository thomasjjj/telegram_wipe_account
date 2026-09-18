from types import SimpleNamespace
from unittest.mock import AsyncMock

from telethon import errors, functions, types

from telegram_cleaner.config import Settings
from telegram_cleaner.telegram import build_client


async def test_client_reissues_request_after_login_dc_migration(tmp_path, monkeypatch):
    client = build_client(Settings(12345, "test-hash", None, str(tmp_path / "session")))
    switch = AsyncMock()
    monkeypatch.setattr(client, "_switch_dc", switch)
    monkeypatch.setattr(client, "is_user_authorized", AsyncMock(return_value=False))
    response = types.User(12345)
    sender = SimpleNamespace(
        send=AsyncMock(
            side_effect=[
                errors.PhoneMigrateError(None, capture=4),
                response,
            ]
        )
    )
    try:
        result = await client._call(sender, functions.updates.GetStateRequest())
        assert result is response
        switch.assert_awaited_once_with(4)
        assert sender.send.await_count == 2
    finally:
        client.session.close()
