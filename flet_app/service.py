"""Threaded application service shared by the Flet view and tests.

The service deliberately knows nothing about Flet.  It accepts plain paths and
options, emits serialisable-ish event dictionaries through a queue, and reuses
the existing UI-independent BatchRunner from ``rpgmv_decrypter.ui_logic``.
"""

from __future__ import annotations

import os
import threading
import time
import traceback
from collections.abc import Sequence
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from rpgmv_decrypter import ui_logic
from rpgmv_decrypter.filetypes import split_name
from rpgmv_decrypter.key_detect import detect_key

from .models import ScannedFile, ScanSnapshot, file_kind, normalise_path

Event = dict[str, Any]


class DesktopService:
    """Owns background scans, key detection and one active batch job."""

    def __init__(self, events: Queue[Event] | None = None) -> None:
        self.events: Queue[Event] = events or Queue()
        self._scan_generation = 0
        self._key_generation = 0
        self._job_lock = threading.Lock()
        self._running = False
        self._cancel_event = threading.Event()
        self._job_thread: threading.Thread | None = None
        self._closed = False
        self._output_root: Path | None = None

    # ------------------------------------------------------------------
    # housekeeping
    # ------------------------------------------------------------------
    @property
    def running(self) -> bool:
        return self._running

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_event.is_set()

    def drain_events(self) -> list[Event]:
        items: list[Event] = []
        while True:
            try:
                items.append(self.events.get_nowait())
            except Empty:
                break
        return items

    def close(self) -> None:
        self._closed = True
        self._cancel_event.set()
        self._scan_generation += 1
        self._key_generation += 1

    def set_output_root(self, path: str | os.PathLike[str] | None) -> None:
        """Choose the parent folder in which timestamped run folders are created."""

        if path is None:
            self._output_root = None
            return
        chosen = normalise_path(path)
        chosen.mkdir(parents=True, exist_ok=True)
        self._output_root = chosen
        ui_logic.OUTPUT_ROOT = chosen
        ui_logic.reset_choices()

    def output_root(self) -> Path:
        if self._output_root is not None:
            return self._output_root
        return ui_logic.output_root()

    # ------------------------------------------------------------------
    # scanning
    # ------------------------------------------------------------------
    def scan(self, paths: Sequence[str | os.PathLike[str]], *, recursive: bool) -> int:
        """Start walking the selected inputs and return a scan generation id."""

        self._scan_generation += 1
        generation = self._scan_generation
        roots = tuple(dict.fromkeys(normalise_path(path) for path in paths))
        thread = threading.Thread(
            target=self._scan_worker,
            args=(generation, roots, bool(recursive)),
            name=f"flet-scan-{generation}",
            daemon=True,
        )
        thread.start()
        return generation

    def _scan_worker(self, generation: int, roots: tuple[Path, ...], recursive: bool) -> None:
        if not roots:
            self.events.put(
                {
                    "type": "scan_finished",
                    "generation": generation,
                    "snapshot": ScanSnapshot(roots=(), files=()),
                }
            )
            return

        self.events.put(
            {
                "type": "scan_started",
                "generation": generation,
                "roots": roots,
            }
        )
        started = time.monotonic()
        try:
            expanded = ui_logic.expand_directories(roots, recursive=recursive)
            files: list[ScannedFile] = []
            for path in expanded:
                if generation != self._scan_generation or self._closed:
                    return
                try:
                    size = path.stat().st_size
                except OSError:
                    size = 0
                files.append(
                    ScannedFile(
                        path=path,
                        size=size,
                        extension=split_name(path)[1],
                        kind=file_kind(path),
                    )
                )
            warning = ""
            for root in roots:
                try:
                    if root.is_dir() and ui_logic.looks_like_output_root(root):
                        warning = str(root)
                        break
                except OSError:
                    continue
            if generation != self._scan_generation or self._closed:
                return
            self.events.put(
                {
                    "type": "scan_finished",
                    "generation": generation,
                    "snapshot": ScanSnapshot(roots=roots, files=tuple(files), warning=warning),
                    "elapsed": time.monotonic() - started,
                }
            )
        except Exception as error:  # pragma: no cover - OS/path edge cases
            if generation != self._scan_generation or self._closed:
                return
            self.events.put(
                {
                    "type": "scan_failed",
                    "generation": generation,
                    "error": f"{type(error).__name__}: {error}",
                    "roots": roots,
                }
            )

    # ------------------------------------------------------------------
    # key detection
    # ------------------------------------------------------------------
    def detect_key(
        self,
        paths: Sequence[str | os.PathLike[str]],
        *,
        header_len: int = 16,
    ) -> int:
        self._key_generation += 1
        generation = self._key_generation
        roots = tuple(dict.fromkeys(normalise_path(path) for path in paths))
        thread = threading.Thread(
            target=self._key_worker,
            args=(generation, roots, int(header_len)),
            name=f"flet-key-{generation}",
            daemon=True,
        )
        thread.start()
        return generation

    def _key_worker(self, generation: int, roots: tuple[Path, ...], header_len: int) -> None:
        self.events.put({"type": "key_detection_started", "generation": generation})
        errors: list[str] = []
        attempted: list[str] = []
        for root in roots:
            if generation != self._key_generation or self._closed:
                return
            attempted.append(str(root))
            try:
                result = detect_key(root, header_len=header_len)
            except Exception as error:
                errors.append(f"{root.name}: {type(error).__name__}: {error}")
                continue
            if result.found and result.key:
                self.events.put(
                    {
                        "type": "key_detected",
                        "generation": generation,
                        "key": result.key,
                        "strategy": result.strategy or "",
                        "source": str(result.source or root),
                        "confirmed": bool(result.confirmed),
                        "detail": result.detail,
                    }
                )
                return
            if result.detail:
                errors.append(result.detail)
        if generation != self._key_generation or self._closed:
            return
        self.events.put(
            {
                "type": "key_not_found",
                "generation": generation,
                "attempted": attempted,
                "errors": errors,
            }
        )

    # ------------------------------------------------------------------
    # batch processing
    # ------------------------------------------------------------------
    def start_job(
        self,
        request: ui_logic.BatchRequest,
        *,
        output_root: str | os.PathLike[str] | None = None,
    ) -> bool:
        with self._job_lock:
            if self._running:
                self.events.put(
                    {
                        "type": "job_rejected",
                        "error": "a batch is already running",
                    }
                )
                return False
            if output_root is not None:
                self.set_output_root(output_root)
            self._cancel_event = threading.Event()
            self._running = True
            thread = threading.Thread(
                target=self._job_worker,
                args=(request, self._cancel_event),
                name="flet-batch",
                daemon=True,
            )
            self._job_thread = thread
            thread.start()
            return True

    def cancel_job(self) -> None:
        self._cancel_event.set()
        if self._running:
            self.events.put({"type": "cancel_requested"})

    def _job_worker(self, request: ui_logic.BatchRequest, cancel_event: threading.Event) -> None:
        self.events.put({"type": "job_started"})

        def put_progress(kind: str, *args: Any) -> None:
            if self._closed:
                return
            if kind == "start":
                self.events.put({"type": "progress_start", "total": int(args[0])})
            elif kind == "step":
                done, total, name = args
                self.events.put(
                    {
                        "type": "progress",
                        "done": int(done),
                        "total": int(total),
                        "name": str(name),
                    }
                )
            elif kind == "finish":
                self.events.put({"type": "progress_finish"})

        report = ui_logic.ProgressReport(
            on_start=lambda total: put_progress("start", total),
            on_progress=lambda done, total, name: put_progress("step", done, total, name),
            on_finish=lambda: put_progress("finish"),
            should_stop=cancel_event.is_set,
        )
        try:
            result = ui_logic.BatchRunner(report).run(request)
            event = {"type": "job_finished", "result": result}
        except Exception as error:  # pragma: no cover - defensive boundary
            event = {
                "type": "job_failed",
                "error": f"{type(error).__name__}: {error}",
                "traceback": traceback.format_exc(),
            }
        finally:
            with self._job_lock:
                self._running = False
                self._job_thread = None
        if not self._closed:
            self.events.put(event)


__all__ = ["DesktopService", "Event"]
