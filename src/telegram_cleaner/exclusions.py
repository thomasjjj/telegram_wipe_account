"""Stable, persistent peer exclusions for chats that must be preserved."""

import argparse
import re

from .models import Job


def parse_peer(value: str) -> int:
    match = re.fullmatch(r"https?://t\.me/c/([1-9][0-9]*)(?:/[1-9][0-9]*)?/?", value.strip())
    if match:
        return -(1_000_000_000_000 + int(match.group(1)))
    try:
        peer_id = int(value)
        if peer_id == 0:
            raise ValueError
        return peer_id
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Use a marked peer ID or a https://t.me/c/... link"
        ) from exc


def apply_exclusions(job: Job, additional: list[int]) -> None:
    """Resume may add protections, but never silently remove saved exclusions."""
    job.excluded_peer_ids = sorted(set(job.excluded_peer_ids) | set(additional))
    for peer_id in job.excluded_peer_ids:
        job.dialogs.pop(str(peer_id), None)
