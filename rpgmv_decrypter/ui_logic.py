"""UI-independent helpers for the Flet desktop application and its tests.

Everything here is plain Python with no third-party imports. Validation, input
walking, output-folder rules, progress reporting and batch orchestration live
here so they can be tested without a display.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from . import api
from .api import DecryptOptions, FileOutcome, RestoreResult
from .decrypter import (
    DEFAULT_HEADER_LEN,
    DEFAULT_REMAIN,
    DEFAULT_SIGNATURE,
    DEFAULT_VERSION,
    Decrypter,
)
from .exceptions import DecrypterError
from .filetypes import (
    DECRYPT_EXTENSIONS,
    ENCRYPT_EXTENSIONS,
    RpgMakerVersion,
    split_name,
)

__all__ = [
    "ARCHIVE_FOLDER_NAME",
    "DEFAULT_LANGUAGE",
    "LANGUAGES",
    "OUTPUT_ROOT",
    "PROJECT_ROOT",
    "RESOLVED",
    "BatchRequest",
    "BatchRunner",
    "ProgressReport",
    "RunResult",
    "build_options",
    "format_size",
    "install_root",
    "is_frozen",
    "looks_like_output_root",
    "output_root",
    "parse_header_len",
    "pick_run_directory",
    "reset_choices",
    "resolve_writable_root",
    "rpgmaker_version",
    "validate_key",
    "verify_fake_header_from_choice",
]

#: Repository root (this module lives in ``rpgmv_decrypter/``).
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

#: Languages the interface can be shown in.  ``zh`` is the default.
LANGUAGES: dict[str, str] = {"zh": "中文", "en": "English"}
DEFAULT_LANGUAGE = "zh"

#: Folder name used for the optional ZIP next to a run's results.
ARCHIVE_FOLDER_NAME = api.ARCHIVE_FOLDER_NAME


def is_frozen() -> bool:
    """Whether this process is running from a packaged build."""

    return bool(getattr(sys, "frozen", False))


def program_directory() -> Path:
    """Return the application folder used as the preferred output location.

    ``sys.argv[0]`` points at the launched executable in a PyInstaller build and at
    the source checkout when running from Python.
    """
    if not is_frozen():
        return PROJECT_ROOT

    candidate = Path(sys.argv[0]).resolve()
    if candidate.is_file():
        return candidate.parent
    if candidate.is_dir():
        return candidate
    # No usable argv (embedded, or a host that clears it): fall back to the executable.
    return Path(sys.executable).resolve().parent


def install_root() -> Path:
    """The folder the application runs from.

    In a packaged build that is the folder holding the executable; from a checkout it is
    the repository.  Used as the *preferred* output location, because results next to the
    tool is what people expect from something portable - but only when it is writable.
    """
    return program_directory()


def _writable(directory: Path) -> bool:
    """Whether something can actually be created in ``directory``.

    Probed rather than inferred from permissions: the only reliable answer on Windows
    comes from trying, and a probe file is cheaper than an ACL inspection that can be
    wrong about things like virtualisation.
    """
    probe = directory / f".rpgmv-write-probe-{os.getpid()}"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _per_user_data_dir() -> Path:
    """A folder belonging to the user, for results that cannot live elsewhere."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "RPGMakerDecrypter"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "rpgmaker-decrypter"
    return Path.home() / ".local" / "share" / "rpgmaker-decrypter"


def _env_path(name: str, fallback: Path) -> Path:
    """Read a path from the environment, falling back to a project-relative one."""
    raw = os.environ.get(name)
    path = Path(raw).expanduser() if raw else fallback
    return path if path.is_absolute() else PROJECT_ROOT / path


def resolve_writable_root(
    env_name: str, preferred: Path, *, label: str, explicit: Path | None = None
) -> tuple[Path, str]:
    """Pick a folder that can actually be written to, and say why it was picked.

    Order, and the reasoning:

    1. ``explicit`` - a folder the caller already decided on (the interface's "change
       export folder" button, or a test pinning a location).  An explicit choice is the
       answer, not something to second-guess;
    2. ``env_name`` in the environment - the same idea for a scripted run;
    3. ``preferred`` - next to the tool, which is what a portable application should do
       and what the packaged build's own readme promises;
    4. a per-user data folder - because a packaged build is often unzipped somewhere
       read-only, and results that cannot be written at all are worse than results in an
       unexpected place;
    5. the system temporary directory - last resort, so a long job does not fail at the
       final step for want of somewhere to put its output.

    Returns the folder and a short human-readable reason, which the caller logs.  Silently
    relocating a user's output is its own kind of bug, so the choice is always announced.
    """
    if explicit is not None:
        return Path(explicit), f"{label}: chosen by the user"

    override = os.environ.get(env_name)
    if override:
        chosen = Path(override).expanduser()
        if not chosen.is_absolute():
            chosen = PROJECT_ROOT / chosen
        return chosen, f"{label}: from {env_name}"

    if _writable(preferred):
        return preferred, f"{label}: beside the application ({preferred})"

    fallback = _per_user_data_dir() / label
    if _writable(fallback):
        return fallback, (f"{label}: {preferred} is not writable, so results go to {fallback}")

    temporary = Path(tempfile.gettempdir()) / f"rpgmaker-decrypter-{label}"
    temporary.mkdir(parents=True, exist_ok=True)
    return temporary, (
        f"{label}: {preferred} is not writable and neither is {fallback}, so this is going "
        f"to {temporary} - that is a temporary folder and may be cleared by the system, "
        f"so move anything you want to keep"
    )


#: Where results are exported. Override with ``RPGMV_GUI_OUTPUTDIR``.
#: Each run gets ``<OUTPUT_ROOT>/<timestamp>/`` so nothing is ever overwritten.
OUTPUT_ROOT: Path = _env_path("RPGMV_GUI_OUTPUTDIR", PROJECT_ROOT / "output")

#: Captured at import time so a later assignment can be recognised as an explicit
#: user choice rather than being overwritten by the lazy resolver.
_DEFAULT_OUTPUT_ROOT = OUTPUT_ROOT

#: Why each folder ended up where it did, so the interface can tell the user instead of
#: leaving them to guess where their files went.
RESOLVED: dict[str, str] = {}


# ----------------------------------------------------------------------
# paths
# ----------------------------------------------------------------------
def output_root() -> Path:
    """Return (and create on demand) the folder results are exported to.

    A checkout keeps ``<repo>/output``.  A packaged build prefers the folder holding the
    executable - results beside a portable tool is the least surprising place for them -
    but falls back to a per-user folder when that is read-only, which is what happens when
    the build is unzipped into ``Program Files``.

    Every decision is recorded in :data:`RESOLVED` so the interface can say where the
    files actually went.
    """
    env_set = bool(os.environ.get("RPGMV_GUI_OUTPUTDIR"))
    assigned = None if env_set else (OUTPUT_ROOT if OUTPUT_ROOT != _DEFAULT_OUTPUT_ROOT else None)
    if env_set or assigned is not None:
        chosen = Path(assigned) if assigned is not None else OUTPUT_ROOT
        RESOLVED["output"] = (
            "output: chosen by the user"
            if assigned is not None
            else "output: from RPGMV_GUI_OUTPUTDIR"
        )
        chosen.mkdir(parents=True, exist_ok=True)
        return chosen

    chosen, why = _cache_choice(
        "output",
        lambda: resolve_writable_root(
            "RPGMV_GUI_OUTPUTDIR", install_root() / "output", label="output"
        ),
    )
    RESOLVED["output"] = why
    chosen.mkdir(parents=True, exist_ok=True)
    return chosen


def _cache_choice(name: str, factory: Callable[[], tuple[Path, str]]) -> tuple[Path, str]:
    """Resolve once per process, so the writability probe is not repeated every run."""
    cached = _CHOICES.get(name)
    if cached is None:
        cached = factory()
        _CHOICES[name] = cached
    return cached


_CHOICES: dict[str, tuple[Path, str]] = {}


def reset_choices() -> None:
    """Forget the cached folders.  For tests that change the environment."""
    _CHOICES.clear()
    RESOLVED.clear()


def looks_like_output_root(path: Path) -> bool:
    """True when ``path`` looks like a folder this tool produced.

    Matches both a single timestamped run folder and an export root that holds
    run folders.  Used by the GUI to warn when a user picks an export folder as
    *input* - an easy mistake that would otherwise silently do nothing.
    """
    try:
        if _is_run_name(path.name) or (path.name and path.name.startswith("_zip")):
            return True
        if not path.is_dir():
            return False
        entries = list(path.iterdir())
    except OSError:
        return False
    return any(entry.is_dir() and _is_run_name(entry.name) for entry in entries)


#: ``pick_run_directory`` names a run ``YYYY-MM-DD_HHMMSS`` (17 chars).
RUN_NAME_FORMAT = "%Y-%m-%d_%H%M%S"
RUN_NAME_LENGTH = 17


def _is_run_name(name: str) -> bool:
    """True when ``name`` is one of our ``<timestamp>[_n]`` run folder names."""
    if not name or len(name) < RUN_NAME_LENGTH:
        return False
    try:
        datetime.strptime(name[:RUN_NAME_LENGTH], RUN_NAME_FORMAT)
    except ValueError:
        return False
    return True


def pick_run_directory(now: datetime | None = None, root: Path | None = None) -> Path:
    """Create ``<root>/<timestamp>/`` for one run and return it.

    One folder per second in practice; a same-second repeat appends a counter
    rather than reusing the folder, so two runs never mix results.
    """
    base = root or output_root()
    base.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime(RUN_NAME_FORMAT)
    candidate = base / stamp
    counter = 1
    while candidate.exists():
        candidate = base / f"{stamp}_{counter}"
        counter += 1
    candidate.mkdir(parents=True)
    return candidate


# ----------------------------------------------------------------------
# validation
# ----------------------------------------------------------------------
def parse_header_len(value: Any) -> tuple[int | None, str]:
    """Validate a header-length field.  Returns ``(value, error)``."""
    if value is None or value == "":
        return None, "header length is empty"
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return None, f"header length must be a number, got {value!r}"
    if parsed < 1:
        return None, "header length must be positive"
    return parsed, ""


def rpgmaker_version(value: Any) -> RpgMakerVersion:
    """Map a combo-box value to :class:`RpgMakerVersion`."""
    text = str(value or "").strip().upper()
    return RpgMakerVersion.MZ if text == RpgMakerVersion.MZ.value else RpgMakerVersion.MV


def verify_fake_header_from_choice(value: Any) -> bool:
    """``True`` means *verify*.  Accepts booleans and the words yes/no."""
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"yes", "1", "true", "y", "on"}


def build_options(
    *,
    verify_fake_header: Any = True,
    header_len: Any = DEFAULT_HEADER_LEN,
    signature: Any = DEFAULT_SIGNATURE,
    version: Any = DEFAULT_VERSION,
    remain: Any = DEFAULT_REMAIN,
    rpgmaker: Any = RpgMakerVersion.MV.value,
    version_override: RpgMakerVersion | None = None,
    recursive: bool = True,
) -> tuple[DecryptOptions | None, str]:
    """Validate the advanced fields and build :class:`DecryptOptions`."""
    parsed_len, error = parse_header_len(header_len)
    if error:
        return None, error

    signature_text = str(signature or "").strip()
    version_text = str(version or "").strip()
    remain_text = str(remain or "").strip()
    for label, text in (
        ("signature", signature_text),
        ("version", version_text),
        ("remain", remain_text),
    ):
        if not Decrypter.check_hex_chars(text):
            return None, f"header {label} must be a non-empty hex string"

    return (
        DecryptOptions(
            header_len=parsed_len or DEFAULT_HEADER_LEN,
            signature=signature_text,
            version=version_text,
            remain=remain_text,
            ignore_fake_header=not verify_fake_header_from_choice(verify_fake_header),
            rpgmaker_version=version_override or rpgmaker_version(rpgmaker),
            recursive=recursive,
        ),
        "",
    )


def validate_key(key: Any, header_len: int) -> tuple[str | None, str]:
    """Validate a key string.  Returns ``(key, error)``."""
    text = str(key or "").strip()
    if not text:
        return None, "no key given - detect it from the game or type it in"
    if not Decrypter.check_hex_chars(text):
        return None, "the key may only contain hex characters (0-9, a-f, A-F)"
    if len(text) % 2 != 0:
        return None, "the key must have an even number of hex characters"
    if len(text) // 2 < header_len:
        return None, (
            f"the key is too short: it needs at least {header_len} bytes "
            f"({header_len * 2} hex characters)"
        )
    return text, ""


# ----------------------------------------------------------------------
# inputs and staging
# ----------------------------------------------------------------------
def _scan_key(path: Path) -> str:
    """A cheap identity key for de-duplication.

    ``Path.resolve()`` touches the filesystem for every path (symlink resolution)
    and cost ~1.2 s per 3000 files - more than the entire decryption of those
    files.  ``abspath``+``normcase`` gives the same de-duplication for a fraction
    of the cost, and never raises on a path that has since disappeared.
    """
    return os.path.normcase(os.path.abspath(path))


def expand_directories(paths: Sequence[Path], *, recursive: bool = True) -> list[Path]:
    """Expand file and directory inputs into the files they contain.

    Uses ``os.scandir`` and normalized string keys because this runs while the
    user waits; ``Path.resolve()`` on every entry is noticeably slower.
    """
    files: list[Path] = []
    seen: set[str] = set()

    for path in paths:
        if path.is_dir():
            root = os.path.abspath(path)
            for found in _walk(root, recursive=recursive):
                key = os.path.normcase(found)
                if key in seen:
                    continue
                seen.add(key)
                files.append(Path(found))
        elif path.is_file():
            key = _scan_key(path)
            if key not in seen:
                seen.add(key)
                files.append(path)
    return files


def _walk(root: str, *, recursive: bool) -> Iterator[str]:
    """Yield file paths under ``root``, skipping our own ``_logs``/``_zip`` folders.

    Implemented with :func:`os.scandir` because it hands back the entry type from
    the directory listing; ``is_file()`` on each entry would ``stat`` again.
    """
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    if _is_internal_dir(entry.name):
                        continue
                    if recursive:
                        stack.append(entry.path)
                    continue
                if entry.is_file(follow_symlinks=False):
                    yield entry.path
            except OSError:
                continue


def _is_internal_dir(part: str) -> bool:
    """Folders this tool creates and should never re-read as input."""
    lowered = part.lower()
    return lowered in {"_logs", "_zip"} or lowered.startswith("_logs")


# ----------------------------------------------------------------------
# progress reporting
# ----------------------------------------------------------------------
class ProgressReport:
    """Progress callbacks consumed by the Flet worker bridge or tests.

    :param on_start: called with the total number of files
    :param on_progress: called with ``(done, total, current_name)``
    :param on_finish: called once when the run ends (successfully or not)
    :param should_stop: polled before every file so a Cancel button works
    """

    def __init__(
        self,
        *,
        on_start: Callable[[int], None] | None = None,
        on_progress: Callable[[int, int, str], None] | None = None,
        on_finish: Callable[[], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        self._on_start = on_start
        self._on_progress = on_progress
        self._on_finish = on_finish
        self._should_stop = should_stop

    def start(self, total: int) -> None:
        if self._on_start:
            self._on_start(total)

    def step(self, done: int, total: int, name: str) -> None:
        if self._on_progress:
            self._on_progress(done, total, name)

    def finish(self) -> None:
        if self._on_finish:
            self._on_finish()

    @property
    def cancelled(self) -> bool:
        return bool(self._should_stop and self._should_stop())


# ----------------------------------------------------------------------
# running a batch
# ----------------------------------------------------------------------
@dataclass
class BatchRequest:
    """Everything needed to run one operation."""

    mode: str  # "decrypt" | "encrypt" | "restore"
    inputs: list[Path]
    key: str | None = None
    options: DecryptOptions = field(default_factory=DecryptOptions)
    package_zip: bool = False
    version_override: RpgMakerVersion | None = None

    @property
    def allowed_extensions(self) -> frozenset[str]:
        return {
            "encrypt": ENCRYPT_EXTENSIONS,
            "decrypt": DECRYPT_EXTENSIONS,
            "restore": frozenset({"rpgmvp", "png_"}),
        }.get(self.mode, DECRYPT_EXTENSIONS)


@dataclass
class RunResult:
    """Everything a UI needs to present one finished run."""

    result: RestoreResult
    run_directory: Path
    archive: Path | None = None
    problems: list[str] = field(default_factory=list)
    skipped_already_done: list[Path] = field(default_factory=list)
    unprocessable: list[Path] = field(default_factory=list)
    #: True when there was simply nothing to do (no usable file / all already
    #: converted).  A UI should say so instead of reporting a failure.
    nothing_to_do: bool = False
    cancelled: bool = False
    error: str | None = None

    @property
    def downloads(self) -> list[Path]:
        return [
            outcome.destination
            for outcome in self.result.succeeded
            if outcome.destination is not None
        ]


class BatchRunner:
    """Run one :class:`BatchRequest` and report progress.

    This class is UI-free: the Flet service invokes it on a worker thread, while
    tests can invoke it synchronously.
    """

    def __init__(self, progress: ProgressReport | None = None) -> None:
        self.progress = progress or ProgressReport()
        #: Set when the batch was stopped early through the progress callback.
        self.cancelled = False
        #: Minimum seconds between two ``step`` reports. The batch API calls the
        #: callback from worker threads; throttling avoids making UI updates more
        #: expensive than the file processing. The first and last steps always report.
        self.progress_interval = 0.05

    # ------------------------------------------------------------------
    def run(self, request: BatchRequest) -> RunResult:
        """Execute ``request``; never raises for an expected failure."""
        prepared = self._prepare(request)
        if isinstance(prepared, RunResult):
            return prepared

        preset, unprocessable, todo = prepared

        if not todo:
            return RunResult(
                result=RestoreResult(outcomes=preset, key=request.key),
                run_directory=Path(),
                skipped_already_done=[outcome.source for outcome in preset],
                unprocessable=unprocessable,
                nothing_to_do=True,
            )

        run_directory = pick_run_directory()

        # Inputs are read in place and results are written only into the fresh run
        # directory, so the source game files are never modified.
        result = RestoreResult(key=request.key)
        result.outcomes.extend(preset)
        problems: list[str] = []

        total = len(todo)
        self.progress.start(total)
        cancelled = False
        try:
            # One call for the whole batch, not one call per file: the library
            # parallelises a batch across worker threads (measured ~2.2x for image
            # folders), and a per-file loop would give every call a single-worker
            # pool and no speedup at all.
            result.outcomes.extend(self._batch(request, todo, run_directory, total))
        except (DecrypterError, ValueError, OSError) as error:
            return RunResult(
                result=result,
                run_directory=run_directory,
                problems=problems,
                unprocessable=unprocessable,
                error=str(error),
            )
        except Exception as error:  # pragma: no cover - guard against a defect
            return RunResult(
                result=result,
                run_directory=run_directory,
                problems=problems,
                unprocessable=unprocessable,
                error=f"{type(error).__name__}: {error}",
            )
        finally:
            self.progress.finish()

        cancelled = result.cancelled or self.cancelled

        archive: Path | None = None
        # A cancelled run produces no archive: the user asked to stop, and packaging
        # a partial result would look like a finished job.
        if request.package_zip and result.succeeded and not cancelled:
            try:
                archive = api.write_zip(
                    result.outcomes,
                    api.archive_path_for(run_directory),
                    archive_name=run_directory.name,
                )
            except OSError as error:
                problems.append(f"could not write the ZIP: {error}")

        return RunResult(
            result=result,
            run_directory=run_directory,
            archive=archive,
            problems=problems,
            skipped_already_done=[outcome.source for outcome in preset],
            unprocessable=unprocessable,
            cancelled=cancelled,
        )

    # ------------------------------------------------------------------
    def _prepare(
        self, request: BatchRequest
    ) -> tuple[list[FileOutcome], list[Path], list[Path]] | RunResult:
        """Split inputs into already-done, unprocessable and pending files.

        The local walker preserves the user's pick order and includes unsupported
        files so the UI can report them. The batch API itself may process the
        pending files in its own stable order.
        """
        allowed = request.allowed_extensions
        files = expand_directories(request.inputs, recursive=request.options.recursive)

        eligible = [path for path in files if split_name(path)[1] in allowed]
        unprocessable = [path for path in files if split_name(path)[1] not in allowed]

        if not eligible:
            return RunResult(
                result=RestoreResult(key=request.key),
                run_directory=Path(),
                unprocessable=unprocessable,
                nothing_to_do=True,
                error="no file with a supported extension was selected",
            )

        already = api.processed_paths(eligible, mode=request.mode, options=request.options)
        preset = [
            FileOutcome(
                source=path,
                skipped=True,
                reason="already converted (its output already exists)",
            )
            for path in eligible
            if path.resolve() in already
        ]
        todo = [path for path in eligible if path.resolve() not in already]
        return preset, unprocessable, todo

    def _batch(
        self,
        request: BatchRequest,
        sources: Sequence[Path],
        run_directory: Path,
        total: int,
    ) -> list[FileOutcome]:
        """Process every selected file in one library call.

        The batch API spreads the work over worker threads. Its progress callback
        updates the UI and cooperatively stops the batch when the user cancels.
        """
        done = 0
        lock = threading.Lock()
        last_report = 0.0

        # ``ProgressReport.cancelled`` is a property, so pass a callable predicate.
        def should_stop() -> bool:
            return self.progress.cancelled

        def report(_done: int, _total: int, source: Path) -> None:
            # Called from the library's worker threads: serialise the counter, then
            # coalesce, so the UI is not handed one signal per file.
            nonlocal done, last_report
            with lock:
                done += 1
                position = done
            if self.progress.cancelled:
                raise api.BatchCancelled()
            now = time.monotonic()
            if position == total or now - last_report >= self.progress_interval:
                last_report = now
                self.progress.step(position, total, source.name)

        call = {
            "decrypt": lambda: api.decrypt_paths(
                sources,
                request.key,
                run_directory,
                options=request.options,
                progress=report,
                cancelled=should_stop,
            ),
            "encrypt": lambda: api.encrypt_paths(
                sources,
                request.key,
                run_directory,
                options=request.options,
                progress=report,
                cancelled=should_stop,
            ),
            "restore": lambda: api.restore_png_paths(
                sources,
                run_directory,
                options=request.options,
                progress=report,
                cancelled=should_stop,
            ),
        }[request.mode]

        outcome = call()
        if outcome.cancelled:
            self.cancelled = True
        return list(outcome.outcomes)


# ----------------------------------------------------------------------
# presentation helpers
# ----------------------------------------------------------------------
def format_size(size: int) -> str:
    """Human readable byte count (``1536`` -> ``1.5 KiB``)."""
    if size < 1024:
        return f"{size} B"
    for unit, divisor in (("KiB", 1024), ("MiB", 1024**2), ("GiB", 1024**3)):
        if size < divisor * 1024:
            return f"{size / divisor:.1f} {unit}"
    return f"{size / 1024**3:.1f} GiB"
