from io import BytesIO, StringIO, TextIOWrapper
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest
from rich.console import Console
from telethon import errors

from telegram_cleaner import cli
from telegram_cleaner.deleter import delete_dialog
from telegram_cleaner.models import DialogInventory, DialogKind
from telegram_cleaner.progress import CountsColumn, EstimateColumn, LiveProgress, ProgressEvent
from telegram_cleaner.scanner import scan
from telegram_cleaner.state import new_job
from telegram_cleaner.telegram import flood_wait


def test_unknown_totals_and_redirected_output_are_bounded():
    output = StringIO()
    feedback = LiveProgress(Console(file=output, width=160))
    with feedback:
        for count in range(1000):
            feedback(ProgressEvent("Scanning messages", count))
        feedback(ProgressEvent("Scanning messages", 1000, finished=True))
    rendered = output.getvalue()
    assert "1000/unknown" in rendered and "ETA unknown" in rendered
    assert "elapsed" in rendered
    assert len(rendered.splitlines()) == 2


def test_empty_scan_restarts_clock_for_next_dialog_and_updates_total():
    feedback = LiveProgress(Console(file=StringIO()))
    feedback(ProgressEvent("Scanning messages", finished=True))
    feedback(ProgressEvent("Scanning messages"))
    task = feedback.progress.tasks[0]
    assert task.stop_time is None
    feedback(ProgressEvent("Scanning messages", 3))
    assert task.completed == 3 and task.total is None
    feedback(ProgressEvent("Deleting IDs", total=10))
    feedback(ProgressEvent("Deleting IDs", 5, 10))
    assert task.total == 10 and CountsColumn().render(task).plain == "5/10"
    feedback(ProgressEvent("Verifying messages"))
    assert task.total is None and "unknown" in EstimateColumn().render(task).plain


def test_terminal_progress_fits_default_width_and_shows_pause():
    output = StringIO()
    console = Console(file=output, width=80, force_terminal=True, color_system=None)
    feedback = LiveProgress(console)
    feedback(ProgressEvent("Scoping dialogs", 220, 824, overall=True))
    feedback(ProgressEvent("Scanning messages", 12345))
    feedback.status("Telegram requested a 30-second flood wait; pausing before retry.")
    console.print(feedback.progress)
    rendered = output.getvalue()
    assert "220/824" in rendered and "12345/?" in rendered
    assert "elapsed 0:00:00" in rendered and "--/s ETA unknown" in rendered
    assert "total unknown" in rendered and "30-second flood wait" in rendered
    assert "\u2026" not in rendered  # No clipped columns at normal terminal width.


def test_known_deletion_total_has_rate_and_eta_after_samples():
    feedback = LiveProgress(Console(file=StringIO()))
    clock = [10.0]
    feedback.progress.get_time = lambda: clock[0]
    feedback(ProgressEvent("Deleting IDs", total=100))
    clock[0] = 11.0
    feedback(ProgressEvent("Deleting IDs", 10, 100))
    clock[0] = 12.0
    feedback(ProgressEvent("Deleting IDs", 20, 100))
    assert EstimateColumn().render(feedback.progress.tasks[0]).plain == "10.0/s ETA 8s"


@pytest.mark.parametrize("kind", [DialogKind.PRIVATE, DialogKind.BOT])
async def test_user_peer_sender_filter_label_is_local(kind):
    async def messages(*args, **kwargs):
        if False:
            yield

    events = []
    await scan(
        NS(iter_messages=messages),
        NS(id=1),
        2,
        DialogInventory(2, "private", kind),
        "own",
        Mock(),
        Mock(),
        events.append,
    )
    assert events[0].detail == "local sender filter"


async def test_scan_events_only_include_counts_and_search_mode():
    class MetadataOnly:
        id = 2
        sender_id = 1

        @property
        def message(self):
            raise AssertionError("Must not read content")

    async def messages(*args, **kwargs):
        assert kwargs["from_user"].id == 1
        yield MetadataOnly()

    events = []
    dialog = DialogInventory(-2, "private title", DialogKind.GROUP)
    await scan(
        NS(iter_messages=messages), NS(id=1), -2, dialog, "both", Mock(), Mock(), events.append
    )
    assert events[0].detail == "server sender search"
    assert events[-1].finished and events[-1].completed == 1
    assert all(event.total is None for event in events)
    assert "private title" not in repr(events)


async def test_deletion_and_verification_events_preserve_confirmed_ids():
    async def messages(*args, **kwargs):
        if False:
            yield

    events = []
    client = NS(delete_messages=AsyncMock(), iter_messages=messages)
    dialog = DialogInventory(
        2, "private", DialogKind.PRIVATE, message_ids=[1, 2, 3], scan_complete=True
    )
    await delete_dialog(client, NS(id=1), 2, dialog, "both", 2, True, Mock(), Mock(), events.append)
    deletion = [event for event in events if event.phase == "Deleting IDs"]
    assert [(event.completed, event.total) for event in deletion] == [(0, 3), (2, 3), (3, 3)]
    assert deletion[-1].finished
    assert events[-1].phase == "Verifying messages" and dialog.verified
    assert all(call.kwargs["revoke"] for call in client.delete_messages.call_args_list)


async def test_flood_wait_status_and_resume(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    feedback = LiveProgress(Console(file=StringIO()))
    feedback(ProgressEvent("Scanning messages"))
    reports = []

    def report(message):
        feedback.status(message)
        reports.append(feedback.progress.tasks[0].fields["detail"])

    await flood_wait(errors.FloodWaitError(None, capture=30), report)
    assert "30-second flood wait" in reports[0]
    assert "retrying" in reports[-1]


def test_windows_redirected_unicode_inventory_and_subsequent_error(monkeypatch):
    buffer = BytesIO()
    stream = TextIOWrapper(buffer, encoding="cp1252", errors="strict")
    monkeypatch.setattr(
        cli, "console", Console(file=stream, width=160, markup=False, highlight=False)
    )
    cli.safe_console_output()
    job = new_job(1, "all", True, "both")
    job.dialogs["2"] = DialogInventory(2, "\u4f60\u597d [red]literal[/red]", DialogKind.PRIVATE)
    cli.inventory(job)
    cli.console.print("Stopped: UnicodeEncodeError")
    stream.flush()
    output = buffer.getvalue().decode("cp1252")
    assert "\\u4f60\\u597d" in output
    assert "[red]literal[/red]" in output
    assert "Stopped: UnicodeEncodeError" in output
