from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from logging.handlers import RotatingFileHandler
from time import monotonic
from typing import Any, Callable, TextIO
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import utils.constants as constants

try:
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeRemainingColumn,
    )
    from rich.table import Table
except ImportError:  # pragma: no cover - fallback for partially upgraded installs
    Console = None
    Progress = None
    Table = None


EventCallback = Callable[[dict[str, Any]], None]
_SENSITIVE_QUERY_KEY = re.compile(
    r"(?:token|auth|authorization|secret|signature|password|passwd|expires?|(?:^|[_-])key(?:$|[_-]))",
    re.IGNORECASE,
)
_URL_IN_TEXT = re.compile(r"(?:https?|rtmp|rtsp)://[^\s，。；）)\]}]+", re.IGNORECASE)
_LEADING_DECORATIONS = (
    "⚡️", "⚡", "⚙️", "⚙", "🚧", "✅", "⚠️", "⚠", "🕒", "🥳", "🔍",
    "⛔", "🆗", "📊", "🆙", "🌐", "🚀", "❌", "🫥", "⬆️", "⬆", "📢",
)


def redact_url(value: str | None) -> str | None:
"""
[PT-BR]     if not value or not isinstance(value, str):

[PT-BR]         return value

[PT-BR]     try:

[PT-BR]         parts = urlsplit(value)

[PT-BR]         if not parts.scheme or not parts.netloc:

[PT-BR]             return value

[PT-BR]         hostname = parts.hostname or ""

[PT-BR]         if ":" in hostname and not hostname.startswith("["):

[PT-BR]             hostname = f"[{hostname}]"

[PT-BR]         port = f":{parts.port}" if parts.port else ""

[PT-BR]         netloc = f"{hostname}{port}"

[PT-BR]         query = urlencode(

[PT-BR]             [

[PT-BR]                 (key, "***" if _SENSITIVE_QUERY_KEY.search(key) else item_value)

[PT-BR]                 for key, item_value in parse_qsl(parts.query, keep_blank_values=True)

[PT-BR]             ],

[PT-BR]             doseq=True,

[PT-BR]         )

[PT-BR]         return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))

[PT-BR]     except (TypeError, ValueError):

[PT-BR]         return value





[PT-BR] def sanitize_fields(value: Any, key: str = "") -> Any:

[PT-BR]     if isinstance(value, dict):

[PT-BR]         return {str(k): sanitize_fields(v, str(k)) for k, v in value.items()}

[PT-BR]     if isinstance(value, (list, tuple, set)):

[PT-BR]         return [sanitize_fields(item, key) for item in value]

[PT-BR]     if isinstance(value, str) and ("url" in key.lower() or value.startswith(("http://", "https://", "rtmp://", "rtsp://"))):

[PT-BR]         return redact_url(value)

[PT-BR]     return value





[PT-BR] def redact_urls_in_text(value: str) -> str:

[PT-BR]     return _URL_IN_TEXT.sub(lambda match: redact_url(match.group(0)) or "", value)





[PT-BR] def normalize_message(value: str) -> str:

[PT-BR]     message = redact_urls_in_text(value).strip()

[PT-BR]     changed = True

[PT-BR]     while changed:

[PT-BR]         changed = False

[PT-BR]         for decoration in _LEADING_DECORATIONS:

[PT-BR]             if message.startswith(decoration):

[PT-BR]                 message = message[len(decoration):].lstrip()

[PT-BR]                 changed = True

[PT-BR]                 break

[PT-BR]     return message





[PT-BR] @dataclass(slots=True)

[PT-BR] class ReportEvent:

[PT-BR]     event: str

[PT-BR]     message: str

[PT-BR]     level: str = "INFO"

[PT-BR]     run_id: str | int | None = None

[PT-BR]     phase: str | None = None

[PT-BR]     timestamp: str = field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))

[PT-BR]     data: dict[str, Any] = field(default_factory=dict)



[PT-BR]     def payload(self) -> dict[str, Any]:

[PT-BR]         result = asdict(self)

[PT-BR]         result["data"] = sanitize_fields(result["data"])

[PT-BR]         return result





[PT-BR] class _RuntimeFileSink:

[PT-BR]     def __init__(self, text_path: str, jsonl_path: str):

[PT-BR]         os.makedirs(os.path.dirname(text_path) or ".", exist_ok=True)

[PT-BR]         self._lock = threading.RLock()

[PT-BR]         self._jsonl_path = jsonl_path

[PT-BR]         os.makedirs(os.path.dirname(jsonl_path) or ".", exist_ok=True)

[PT-BR]         self._logger = logging.getLogger(f"iptv.runtime.{id(self)}")

[PT-BR]         self._logger.setLevel(logging.INFO)

[PT-BR]         self._logger.propagate = False

[PT-BR]         handler = RotatingFileHandler(

[PT-BR]             text_path,

[PT-BR]             maxBytes=5 * 1024 * 1024,

[PT-BR]             backupCount=2,

[PT-BR]             encoding="utf-8",

[PT-BR]             delay=True,

[PT-BR]         )

[PT-BR]         handler.setFormatter(logging.Formatter("%(message)s"))

[PT-BR]         self._logger.handlers.clear()

[PT-BR]         self._logger.addHandler(handler)

[PT-BR]         self._json_logger = logging.getLogger(f"iptv.runtime.json.{id(self)}")

[PT-BR]         self._json_logger.setLevel(logging.INFO)

[PT-BR]         self._json_logger.propagate = False

[PT-BR]         json_handler = RotatingFileHandler(

[PT-BR]             jsonl_path,

[PT-BR]             maxBytes=10 * 1024 * 1024,

[PT-BR]             backupCount=2,

[PT-BR]             encoding="utf-8",

[PT-BR]             delay=True,

[PT-BR]         )

[PT-BR]         json_handler.setFormatter(logging.Formatter("%(message)s"))

[PT-BR]         self._json_logger.handlers.clear()

[PT-BR]         self._json_logger.addHandler(json_handler)



[PT-BR]     def emit(self, event: ReportEvent):

[PT-BR]         payload = event.payload()

[PT-BR]         context = []

[PT-BR]         if event.run_id is not None:

[PT-BR]             context.append(f"run={event.run_id}")

[PT-BR]         if event.phase:

[PT-BR]             context.append(f"phase={event.phase}")

[PT-BR]         context.append(f"event={event.event}")

[PT-BR]         suffix = f" [{' '.join(context)}]" if context else ""

[PT-BR]         line = f"{event.timestamp} {event.level:<7}{suffix} {event.message}"

[PT-BR]         with self._lock:

[PT-BR]             self._logger.log(getattr(logging, event.level, logging.INFO), line)

[PT-BR]             self._json_logger.info(json.dumps(payload, ensure_ascii=False, default=str))



[PT-BR]     def close(self):

[PT-BR]         with self._lock:

[PT-BR]             for logger in (self._logger, self._json_logger):

[PT-BR]                 for handler in logger.handlers[:]:

[PT-BR]                     handler.flush()

[PT-BR]                     handler.close()

[PT-BR]                     logger.removeHandler(handler)





[PT-BR] class Reporter:
"""

    def __init__(
        self,
        run_id: str | int | None = None,
        *,
        event_callback: EventCallback | None = None,
        stream: TextIO | None = None,
        enable_console: bool = True,
        enable_runtime_file: bool = True,
    ):
        self.run_id = run_id
        self.event_callback = event_callback
        self.stream = stream or sys.stdout
        self.enable_console = enable_console
        self._lock = threading.RLock()
        self._progress = None
        self._tasks: dict[str, int] = {}
        self._plain_progress: dict[str, dict[str, Any]] = {}
        self._rich_console = None
        self._interactive = bool(
            enable_console
            and hasattr(self.stream, "isatty")
            and self.stream.isatty()
            and os.getenv("TERM", "").lower() not in {"dumb", "unknown"}
            and not os.getenv("GITHUB_ACTIONS")
            and not os.getenv("IPTV_API_PLAIN_OUTPUT")
        )
        if self._interactive and Console is not None:
            self._rich_console = Console(file=self.stream, color_system="auto", markup=False)
        self._file_sink = None
        if enable_runtime_file:
            try:
                self._file_sink = _RuntimeFileSink(constants.log_path, constants.runtime_jsonl_path)
            except OSError:
                self._file_sink = None

    def bind_run(self, run_id: str | int | None):
        self.run_id = run_id

    def emit(self, level: str, event: str, message: str, *, phase: str | None = None, **data):
        report_event = ReportEvent(
            event=event,
            message=normalize_message(str(message)),
            level=level.upper(),
            run_id=self.run_id,
            phase=phase,
            data=data,
        )
        with self._lock:
            if self._file_sink:
                try:
                    self._file_sink.emit(report_event)
                except (OSError, ValueError):
                    pass
            if self.event_callback:
                try:
                    self.event_callback(report_event.payload())
                except Exception:
                    pass
            if self.enable_console:
                self._render_console(report_event)

    def info(self, event: str, message: str, *, phase: str | None = None, **data):
        self.emit("INFO", event, message, phase=phase, **data)

    def warning(self, event: str, message: str, *, phase: str | None = None, **data):
        self.emit("WARNING", event, message, phase=phase, **data)

    def error(self, event: str, message: str, *, phase: str | None = None, **data):
        self.emit("ERROR", event, message, phase=phase, **data)

    def _render_console(self, event: ReportEvent):
        prefix = {
            "INFO": "•",
            "WARNING": "!",
            "ERROR": "×",
            "CRITICAL": "×",
        }.get(event.level, "•")
        style = {
            "INFO": "cyan",
            "WARNING": "yellow",
            "ERROR": "bold red",
            "CRITICAL": "bold red",
        }.get(event.level)
        if self._rich_console:
            self._rich_console.print(f"{prefix} {event.message}", style=style)
        else:
            print(f"{prefix} {event.message}", file=self.stream, flush=True)

    def _ensure_progress(self):
        if self._progress is not None or not self._rich_console or Progress is None:
            return
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("{task.description}", style="cyan"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            TextColumn("{task.completed:.0f}/{task.total:.0f}"),
            TimeRemainingColumn(),
            TextColumn("{task.fields[status]}", style="dim"),
            console=self._rich_console,
            refresh_per_second=5,
            transient=False,
            redirect_stdout=False,
            redirect_stderr=False,
        )
        self._progress.start()

    def start_progress(self, key: str, description: str, total: int, *, phase: str | None = None):
        total = max(0, int(total))
        with self._lock:
            if self._rich_console:
                self._ensure_progress()
                self._tasks[key] = self._progress.add_task(description, total=total, status="", phase=phase)
                self.info(
                    "progress.started",
                    f"{description}  0/{total}",
                    phase=phase,
                    progress_key=key,
                    current=0,
                    total=total,
                )
            else:
                self._plain_progress[key] = {
                    "description": description,
                    "total": total,
                    "completed": 0,
                    "last_percent": -10,
                    "last_emit": monotonic(),
                    "phase": phase,
                }
                self.info(
                    "progress.started",
                    f"{description}  0/{total}",
                    phase=phase,
                    progress_key=key,
                    current=0,
                    total=total,
                )

    def update_progress(
        self,
        key: str,
        *,
        advance: int = 0,
        completed: int | None = None,
        status: str = "",
        **metrics,
    ):
        with self._lock:
            if key in self._tasks and self._progress:
                task_id = self._tasks[key]
                kwargs: dict[str, Any] = {"status": status}
                if completed is not None:
                    kwargs["completed"] = completed
                elif advance:
                    kwargs["advance"] = advance
                self._progress.update(task_id, **kwargs)
                return
            state = self._plain_progress.get(key)
            if not state:
                return
            if completed is not None:
                state["completed"] = min(max(0, int(completed)), state["total"])
            else:
                state["completed"] = min(state["total"], state["completed"] + max(0, int(advance)))
            percent = int(state["completed"] / state["total"] * 100) if state["total"] else 100
            now = monotonic()
            if percent < 100 and percent - state["last_percent"] < 10 and now - state["last_emit"] < 30:
                return
            state["last_percent"] = percent
            state["last_emit"] = now
            metric_text = f"  {status}" if status else ""
            self.info(
                "progress.updated",
                f"{state['description']}  {state['completed']}/{state['total']} ({percent}%){metric_text}",
                phase=state["phase"],
                progress_key=key,
                current=state["completed"],
                total=state["total"],
                **metrics,
            )

    def finish_progress(
        self,
        key: str,
        *,
        status: str = "",
        message: str | None = None,
        remove: bool = False,
        **metrics,
    ):
        with self._lock:
            if key in self._tasks and self._progress:
                task_id = self._tasks.pop(key)
                task = next(task for task in self._progress.tasks if task.id == task_id)
                self._progress.update(task_id, completed=task.total, status=status)
                final_message = message or f"{task.description}  {task.total:.0f}/{task.total:.0f}"
                if status and not message:
                    final_message += f"  {status}"
                self.info(
                    "progress.finished",
                    final_message,
                    phase=task.fields.get("phase"),
                    progress_key=key,
                    current=task.total,
                    total=task.total,
                    status=status,
                    **metrics,
                )
                if remove:
                    self._progress.remove_task(task_id)
            state = self._plain_progress.pop(key, None)
            if state:
                final_message = message or f"{state['description']}  {state['total']}/{state['total']}"
                if status and not message:
                    final_message += f"  {status}"
                self.info(
                    "progress.finished",
                    final_message,
                    phase=state["phase"],
                    progress_key=key,
                    current=state["total"],
                    total=state["total"],
                    status=status,
                    **metrics,
                )

    def summary(
        self,
        title: str,
        metrics: list[tuple[str, Any]],
        *,
        outputs: list[tuple[str, str]] | None = None,
        phase: str = "complete",
    ):
        data = {
            "metrics": {key: value for key, value in metrics},
            "outputs": {key: value for key, value in (outputs or [])},
        }
        self.info("run.summary", title, phase=phase, **data)
        if not self.enable_console:
            return
        if not self._rich_console or Table is None:
            for label, value in metrics:
                print(f"  {label:<12} {value}", file=self.stream)
            for label, value in outputs or []:
                print(f"  {label:<12} {value}", file=self.stream)
            self.stream.flush()
            return
        table = Table(show_header=False, box=None, padding=(0, 2), title=None)
        table.add_column(style="dim")
        table.add_column(style="bold")
        for label, value in metrics:
            table.add_row(str(label), str(value))
        if outputs:
            table.add_section()
            for label, value in outputs:
                table.add_row(str(label), str(value), style="cyan")
        self._rich_console.print(table)

    def stop_progress(self):
        with self._lock:
            if self._progress is not None:
                self._progress.stop()
                self._progress = None
            self._tasks.clear()
            self._plain_progress.clear()

    def close(self):
        with self._lock:
            self.stop_progress()
            if self._file_sink:
                self._file_sink.close()
                self._file_sink = None


def format_metric(value: Any, fallback: str = "—") -> str:
    return fallback if value is None or value == "" else str(value)
