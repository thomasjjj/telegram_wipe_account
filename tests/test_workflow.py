from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest
from telethon import types

from telegram_cleaner.cli import parser, workflow
from telegram_cleaner.config import load_settings
from telegram_cleaner.models import DialogKind
from telegram_cleaner.state import load


class Account:
    def __init__(self):
        self.history = {
            1: [NS(id=10, sender_id=8)],  # Saved forwarded message
            2: [NS(id=20, sender_id=1), NS(id=21, sender_id=2)],
            3: [NS(id=30, sender_id=1), NS(id=31, sender_id=3)],
            -4: [NS(id=40, sender_id=1), NS(id=41, sender_id=4)],
        }
        self.scanned = []
        self.deleted = []

    async def iter_dialogs(self, **kwargs):
        for entity, peer in [
            (types.User(2), 2),
            (types.User(3, bot=True), 3),
            (types.Chat(4, "g", types.ChatPhotoEmpty(), 2, None, 1), -4),
        ]:
            yield NS(entity=entity, input_entity=peer, name=str(peer))

    async def get_input_entity(self, entity):
        return entity.id if hasattr(entity, "id") else entity

    async def iter_messages(self, peer, **kwargs):
        self.scanned.append(peer)
        for message in self.history[peer]:
            yield message

    async def delete_messages(self, peer, ids, revoke):
        assert revoke is True
        self.deleted.append((peer, list(ids)))
        self.history[peer] = [m for m in self.history[peer] if m.id not in ids]


def arguments(tmp_path, *extra):
    return parser().parse_args(
        ["--scope", "all", "--include-archived", "--state-dir", str(tmp_path), *extra]
    )


ME = NS(id=1, first_name="Test", username="test")


async def test_dry_run_end_to_end(tmp_path, monkeypatch):
    prompt = Mock(side_effect=AssertionError("Dry run must not confirm deletion"))
    monkeypatch.setattr("telegram_cleaner.cli.Prompt.ask", prompt)
    client = Account()
    assert await workflow(client, ME, arguments(tmp_path, "--dry-run")) == 0
    assert client.deleted == []
    job = load(next(tmp_path.glob("*.json")), 1)
    assert job.dialogs["2"].message_ids == [20, 21]
    assert job.dialogs["3"].message_ids == [30]
    assert job.dialogs["-4"].message_ids == [40]
    assert job.dialogs["1"].kind == DialogKind.SELF


async def test_groups_scope_never_scans_private(tmp_path, monkeypatch):
    monkeypatch.setattr("telegram_cleaner.cli.Prompt.ask", Mock(side_effect=AssertionError))
    client = Account()
    assert (
        await workflow(client, ME, arguments(tmp_path, "--scope", "groups-channels", "--dry-run"))
        == 0
    )
    assert set(client.scanned) == {-4}
    assert not client.deleted


@pytest.mark.parametrize("answer", ["y", "DELETE 999", ""])
async def test_wrong_confirmation_never_deletes(tmp_path, monkeypatch, answer):
    monkeypatch.setattr("telegram_cleaner.cli.Prompt.ask", Mock(side_effect=["delete", answer]))
    client = Account()
    assert await workflow(client, ME, arguments(tmp_path)) == 0
    assert not client.deleted


async def test_confirmed_private_both_and_other_people_preserved_in_groups(tmp_path, monkeypatch):
    monkeypatch.setattr("telegram_cleaner.cli.Prompt.ask", Mock(side_effect=["delete", "DELETE 5"]))
    client = Account()
    assert await workflow(client, ME, arguments(tmp_path)) == 0
    assert client.history[2] == []
    assert [m.id for m in client.history[3]] == [31]
    assert [m.id for m in client.history[-4]] == [41]
    assert load(next(tmp_path.glob("*.json")), 1).status == "complete"


async def test_resume_account_mismatch_before_scan(tmp_path):
    from telegram_cleaner.state import new_job, save

    path = tmp_path / "job.json"
    save(new_job(99, "all", True, "both"), path)
    client = Account()
    with pytest.raises(ValueError, match="different"):
        await workflow(client, ME, arguments(tmp_path, "--resume", str(path)))
    assert not client.scanned and not client.deleted


def test_env_credentials_no_prompt(tmp_path, monkeypatch):
    for key in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_PHONE", "TELEGRAM_SESSION"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env"
    path.write_text("TELEGRAM_API_ID=42\nTELEGRAM_API_HASH=test-secret\n")
    monkeypatch.setattr("telegram_cleaner.config.Prompt.ask", Mock(side_effect=AssertionError))
    settings = load_settings(path)
    assert settings.api_id == 42
    assert settings.api_hash == "test-secret"


def test_missing_credentials_default_not_saved(tmp_path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_API_HASH", raising=False)
    monkeypatch.setattr(
        "telegram_cleaner.config.Prompt.ask", Mock(side_effect=["bad", "42", "secret"])
    )
    confirm = Mock(return_value=False)
    monkeypatch.setattr("telegram_cleaner.config.Confirm.ask", confirm)
    path = tmp_path / ".env"
    assert load_settings(path).api_id == 42
    assert confirm.call_args.kwargs["default"] is False
    assert not path.exists()


async def test_authentication_disconnect_on_error(monkeypatch):
    from telegram_cleaner.cli import run

    settings = NS(phone="test-phone")
    client = NS(start=AsyncMock(side_effect=ValueError), disconnect=AsyncMock())
    monkeypatch.setattr("telegram_cleaner.cli.load_settings", lambda: settings)
    monkeypatch.setattr("telegram_cleaner.cli.build_client", lambda _: client)
    with pytest.raises(ValueError):
        await run(parser().parse_args([]))
    client.disconnect.assert_awaited_once()
