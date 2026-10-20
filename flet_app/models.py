from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rpgmv_decrypter.filetypes import split_name


@dataclass(frozen=True, slots=True)
class SelectedInput:
    """One path explicitly added by the user."""

    path: Path
    is_dir: bool

    @property
    def name(self) -> str:
        return self.path.name or str(self.path)


@dataclass(frozen=True, slots=True)
class ScannedFile:
    """A file discovered under one of the selected inputs."""

    path: Path
    size: int
    extension: str
    kind: str

    @property
    def name(self) -> str:
        return self.path.name


@dataclass(frozen=True, slots=True)
class ScanSnapshot:
    """Result of walking the selected files and folders."""

    roots: tuple[Path, ...]
    files: tuple[ScannedFile, ...]
    warning: str = ""

    @property
    def total_size(self) -> int:
        return sum(item.size for item in self.files)


_IMAGE_EXTENSIONS = frozenset({"png", "rpgmvp", "png_"})
_AUDIO_EXTENSIONS = frozenset({"ogg", "ogg_", "m4a", "m4a_", "rpgmvo", "rpgmvm"})
_TEXT_EXTENSIONS = frozenset({"json", "js", "txt"})


def file_kind(path: str | Path) -> str:
    """Return a small semantic kind used for icons and labels."""

    extension = split_name(path)[1]
    if extension in _IMAGE_EXTENSIONS:
        return "image"
    if extension in _AUDIO_EXTENSIONS:
        return "audio"
    if extension in _TEXT_EXTENSIONS:
        return "text"
    if extension == "zip":
        return "archive"
    return "file"


def normalise_path(path: str | Path) -> Path:
    """Resolve a user supplied path while preserving display-friendly casing."""

    return Path(path).expanduser().resolve()


def clamp_text(value: str, limit: int) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"
