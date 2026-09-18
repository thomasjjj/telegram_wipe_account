import argparse
import asyncio
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table
from telethon import errors

from .config import load_settings
from .deleter import delete_dialog
from .dialogs import discover, in_scope
from .logging_utils import configure
from .models import Job
from .progress import LiveProgress, ProgressEvent
from .scanner import scan
from .state import load, new_job, new_path, save
from .telegram import build_client, request

console = Console(markup=False, highlight=False)


def safe_console_output() -> None:
    """Preserve redirected Windows output even for names outside its code page."""
    reconfigure = getattr(console.file, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="backslashreplace")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Inventory and revoke Telegram messages")
    result.add_argument("--scope", choices=["groups-channels", "all"])
    result.add_argument("--dry-run", action="store_true")
    result.add_argument("--include-archived", dest="archived", action="store_true", default=None)
    result.add_argument("--no-archived", dest="archived", action="store_false")
    result.add_argument("--private-mode", choices=["both", "own"], default=None)
    result.add_argument("--resume", type=Path)
    result.add_argument(
        "--batch-size", type=int, choices=range(1, 101), default=100, metavar="1-100"
    )
    result.add_argument("--no-verify", action="store_true")
    result.add_argument("--verbose", action="store_true")
    result.add_argument("--state-dir", type=Path, default=Path("state"))
    return result


def inventory(job: Job) -> None:
    table = Table("Type", "Peer ID", "Dialog", "Found", "Pending", "Failed", "Scan / error")
    for dialog in job.dialogs.values():
        table.add_row(
            dialog.kind.value,
            str(dialog.peer_id),
            dialog.title,
            str(len(dialog.message_ids)),
            str(len(dialog.pending)),
            str(len(dialog.failed_ids)),
            dialog.last_error or ("scanned" if dialog.scan_complete else "incomplete"),
        )
    console.print(table)
    for kind in sorted({d.kind for d in job.dialogs.values()}):
        rows = [d for d in job.dialogs.values() if d.kind == kind]
        console.print(
            f"{kind.value}: {len(rows)} dialogs / {sum(len(d.message_ids) for d in rows)} messages"
        )
    console.print(
        f"Private-chat policy: {job.private_mode}; Saved Messages: "
        f"{'included' if job.scope == 'all' else 'excluded'}; archived: {job.include_archived}"
    )
    for error in job.discovery_errors:
        console.print(f"Discovery incomplete: {error}")


def choose_resume(directory: Path, account_id: int) -> Path | None:
    candidates = []
    for path in sorted(directory.glob("cleanup_*.json"), reverse=True):
        try:
            job = load(path, account_id)
        except (ValueError, KeyError, TypeError, OSError):
            continue
        if job.status != "complete":
            candidates.append(path)
    if not candidates:
        return None
    console.print("Incomplete jobs:")
    for index, path in enumerate(candidates, 1):
        console.print(f"{index}. {path}")
    answer = Prompt.ask(
        "Resume number, N for new, or X to exit",
        choices=["n", "x"] + [str(i) for i in range(1, len(candidates) + 1)],
        default="n",
    )
    if answer == "x":
        raise SystemExit(0)
    return None if answer == "n" else candidates[int(answer) - 1]


async def workflow(client: Any, me: Any, args: argparse.Namespace) -> int:
    safe_console_output()
    logger = configure(args.state_dir, args.verbose)
    feedback = LiveProgress(console)

    def report(message: str) -> None:
        feedback.status(message)
        console.print(message)
        logger.info(message)

    console.print(f"Authenticated: {me.first_name or ''} @{me.username or '(none)'} / ID {me.id}")
    path = args.resume or choose_resume(args.state_dir, me.id)
    if path:
        job = load(path, me.id)
        for supplied, saved in (
            (args.scope, job.scope),
            (args.archived, job.include_archived),
            (args.private_mode, job.private_mode),
        ):
            if supplied is not None and supplied != saved:
                raise ValueError("Resume options conflict with the saved job")
        # A previous verification describes that earlier moment, not this run.
        job.status = "inventory"
        for dialog in job.dialogs.values():
            dialog.verified = False
            dialog.delete_complete = False
    else:
        scope = args.scope
        if scope is None:
            choice = Prompt.ask(
                "1: Groups/channels, 2: Everything, 3: Inventory only, 4: Exit",
                choices=["1", "2", "3", "4"],
                default="3",
            )
            if choice == "4":
                return 0
            args.dry_run = args.dry_run or choice == "3"
            scope = "groups-channels" if choice == "1" else "all"
        archived = (
            args.archived
            if args.archived is not None
            else Confirm.ask("Include archived dialogs?", default=True)
        )
        job = new_job(me.id, scope, archived, args.private_mode or "both")
        path = new_path(args.state_dir)

    def checkpoint() -> None:
        save(job, path)

    checkpoint()
    console.print(f"Checkpoint: {path}")
    try:
        with feedback:
            peers = await discover(client, me, job, report, feedback)
            checkpoint()
            for index, dialog in enumerate(job.dialogs.values(), 1):
                feedback(
                    ProgressEvent(
                        "Scoping dialogs",
                        index - 1,
                        len(job.dialogs),
                        detail=f"dialog {index}/{len(job.dialogs)} ({dialog.kind.value})",
                        overall=True,
                    )
                )
                if not in_scope(dialog.kind, job.scope):
                    raise ValueError("Checkpoint contains a dialog outside its scope")
                try:
                    if dialog.peer_id not in peers:
                        peers[dialog.peer_id] = await request(
                            lambda peer_id=dialog.peer_id: client.get_input_entity(peer_id), report
                        )
                    if args.dry_run or not dialog.scan_complete:
                        await scan(
                            client,
                            me,
                            peers[dialog.peer_id],
                            dialog,
                            job.private_mode,
                            checkpoint,
                            report,
                            feedback,
                        )
                except errors.UnauthorizedError:
                    raise
                except (errors.RPCError, OSError, ValueError) as exc:
                    dialog.scan_complete = False
                    dialog.last_error = type(exc).__name__
                    checkpoint()
            feedback(
                ProgressEvent(
                    "Scoping dialogs",
                    len(job.dialogs),
                    len(job.dialogs),
                    finished=True,
                    overall=True,
                )
            )
        inventory(job)
        if args.dry_run:
            console.print(f"Inventory saved: {path}. No deletion requests sent.")
            return (
                0
                if job.discovery_complete and all(d.scan_complete for d in job.dialogs.values())
                else 2
            )
        count = sum(len(d.pending) for d in job.dialogs.values() if d.scan_complete)
        console.print(
            "Deletion is permanent. All requests use revoke=True. Private mode 'both' "
            "includes the other person's messages. Telegram may refuse some deletions."
        )
        action = Prompt.ask(
            "Delete, export inventory, or abort?",
            choices=["delete", "export", "abort"],
            default="abort",
        )
        if action != "delete":
            return 0
        if Prompt.ask(f"Type DELETE {count} to continue", default="") != f"DELETE {count}":
            console.print("Confirmation did not match; no deletion requests sent.")
            return 0
        job.status = "deleting"
        checkpoint()
        with feedback:
            for index, dialog in enumerate(job.dialogs.values(), 1):
                feedback(
                    ProgressEvent(
                        "Cleaning dialogs",
                        index - 1,
                        len(job.dialogs),
                        detail=f"dialog {index}/{len(job.dialogs)} ({dialog.kind.value})",
                        overall=True,
                    )
                )
                if dialog.scan_complete and not dialog.verified:
                    await delete_dialog(
                        client,
                        me,
                        peers[dialog.peer_id],
                        dialog,
                        job.private_mode,
                        args.batch_size,
                        not args.no_verify,
                        checkpoint,
                        report,
                        feedback,
                    )
            feedback(
                ProgressEvent(
                    "Cleaning dialogs",
                    len(job.dialogs),
                    len(job.dialogs),
                    finished=True,
                    overall=True,
                )
            )
        complete = job.discovery_complete and all(d.delete_complete for d in job.dialogs.values())
        verified = complete and all(d.verified for d in job.dialogs.values())
        job.status = "complete" if verified else "incomplete"
        checkpoint()
        inventory(job)
        console.print(
            f"Deletion requests accepted: {sum(len(d.deleted_ids) for d in job.dialogs.values())}; "
            f"verified clean: {sum(d.verified for d in job.dialogs.values())}; "
            f"incomplete/unverified: {sum(not d.verified for d in job.dialogs.values())}"
        )
        console.print(
            f"Dialogs scanned: {sum(d.scan_complete for d in job.dialogs.values())}; "
            f"failed/still visible IDs: {sum(len(d.failed_ids) for d in job.dialogs.values())}; "
            f"already absent: {sum(len(d.absent_ids) for d in job.dialogs.values())}; "
            f"skipped/unscanned dialogs: {sum(not d.scan_complete for d in job.dialogs.values())}"
        )
        if verified:
            console.print("No further matching accessible messages found.")
        else:
            console.print("Cleanup incomplete or unverified. Review the checkpoint and resume.")
        console.print(
            "Channel-authored/anonymous posts, inaccessible chats, copies, scheduled messages, "
            "drafts and server metadata are outside this cleanup. No trace-free guarantee."
        )
        return 0 if complete else 2
    finally:
        checkpoint()


async def run(args: argparse.Namespace) -> int:
    settings = load_settings()
    client = build_client(settings)
    try:
        await client.start(phone=settings.phone or (lambda: Prompt.ask("Telegram phone number")))
        me = await client.get_me()
        if me is None or me.bot:
            raise ValueError("A Telegram user account is required")
        return await workflow(client, me, args)
    finally:
        await client.disconnect()


def main() -> None:
    safe_console_output()
    args = parser().parse_args()
    try:
        code = asyncio.run(run(args))
    except (KeyboardInterrupt, EOFError):
        console.print("Interrupted. Any created job has been checkpointed; resume to continue.")
        code = 130
    except Exception as exc:  # noqa: BLE001 -- redact unexpected errors at the CLI boundary
        # Avoid exception strings/tracebacks containing credentials or message contents.
        console.print(f"Stopped: {type(exc).__name__}. Check configuration and checkpoint status.")
        code = 1
    raise SystemExit(code)
