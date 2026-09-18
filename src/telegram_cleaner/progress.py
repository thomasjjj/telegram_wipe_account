"""Content-free progress events and live terminal feedback."""

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    Task,
    TextColumn,
    TimeElapsedColumn,
)
from rich.text import Text


@dataclass(frozen=True)
class ProgressEvent:
    phase: str
    completed: int = 0
    total: int | None = None
    detail: str = ""
    finished: bool = False
    overall: bool = False


ProgressCallback = Callable[[ProgressEvent], None]


def quiet_progress(event: ProgressEvent) -> None:
    pass


class CountsColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        total = "?" if task.total is None else str(int(task.total))
        return Text(f"{int(task.completed)}/{total}")


class EstimateColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        speed = task.speed
        rate = f"{speed:.1f}/s" if speed else "--/s"
        remaining = task.time_remaining
        eta = "unknown" if remaining is None else f"{int(remaining)}s"
        return Text(f"{rate} ETA {eta}")


class DetailedProgress(Progress):
    def get_renderables(self):
        yield from super().get_renderables()
        details = " | ".join(task.fields.get("detail", "") for task in self.tasks)
        if details:
            yield Text(details)
        if any(task.total is None for task in self.tasks):
            yield Text("? = total unknown; message ETA unavailable until the scan finishes.")


class LiveProgress:
    """Two reusable rows; redirected output gets bounded periodic status lines."""

    def __init__(self, console: Console):
        self.console = console
        self.progress = DetailedProgress(
            SpinnerColumn(),
            TextColumn("{task.description}", markup=False),
            BarColumn(bar_width=8),
            CountsColumn(),
            TextColumn("elapsed"),
            TimeElapsedColumn(),
            EstimateColumn(),
            console=console,
            disable=not console.is_terminal,
            refresh_per_second=4,
        )
        self.tasks: dict[bool, int] = {}
        self.last_output = 0.0
        self.started = monotonic()

    def __enter__(self):
        self.progress.start()
        return self

    def __exit__(self, *_):
        self.progress.stop()

    def __call__(self, event: ProgressEvent) -> None:
        task_id = self.tasks.get(event.overall)
        changed = task_id is None or self.progress.tasks[task_id].description != event.phase
        if task_id is None:
            task_id = self.progress.add_task(event.phase, total=event.total, detail=event.detail)
            self.tasks[event.overall] = task_id
        elif (
            changed
            or self.progress.tasks[task_id].stop_time is not None
            or event.total != self.progress.tasks[task_id].total
            or event.completed < self.progress.tasks[task_id].completed
        ):
            self.progress.reset(task_id, total=event.total, description=event.phase)
            # Rich reset retains stop_time and treats total=None as unchanged.
            task = self.progress.tasks[task_id]
            task.stop_time = None
            task.total = event.total
        self.progress.update(task_id, completed=event.completed, detail=event.detail)
        if event.finished:
            self.progress.stop_task(task_id)
        now = monotonic()
        if not self.console.is_terminal and (
            changed or event.finished or now - self.last_output >= 10
        ):
            total = "unknown" if event.total is None else str(event.total)
            self.console.print(
                f"{event.phase}: {event.completed}/{total}; elapsed {now - self.started:.0f}s; "
                f"{EstimateColumn().render(self.progress.tasks[task_id]).plain}; {event.detail}"
            )
            self.last_output = now

    def status(self, message: str) -> None:
        # Report strings contain phase/errors only, never message text or media.
        for task_id in self.tasks.values():
            self.progress.update(task_id, detail=message)
