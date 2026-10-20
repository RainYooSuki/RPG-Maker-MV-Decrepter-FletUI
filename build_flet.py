"""Build the standalone Windows Flet application and its release ZIP.

Usage:
    python build_flet.py

The script uses the Flet CLI to run PyInstaller in one-folder mode, verifies the
result with the executable's headless ``--self-test`` mode, removes intermediate
build files, and writes a versioned ZIP beside the application folder.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_ROOT = ROOT / "dist-flet"
APP_NAME = "RPGMakerDecrypterFlet"
PACKAGE_DIR = DIST_ROOT / APP_NAME
BUILD_DIR = ROOT / "build"
ICON = ROOT / "flet_app" / "assets" / ("logo.ico" if os.name == "nt" else "logo-128.png")
RUNTIME_ARTIFACTS = (".runtime", "output")


def project_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise RuntimeError("could not read the version from pyproject.toml")
    return match.group(1)


def isolated_environment() -> dict[str, str]:
    home = ROOT / ".home"
    tmp = ROOT / ".tmp"
    cache = ROOT / ".pip-cache"
    for path in (home, tmp, cache, home / "AppData" / "Local", home / "AppData" / "Roaming"):
        path.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "LOCALAPPDATA": str(home / "AppData" / "Local"),
            "APPDATA": str(home / "AppData" / "Roaming"),
            "TMP": str(tmp),
            "TEMP": str(tmp),
            "PIP_CACHE_DIR": str(cache),
            "PYTHONUTF8": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return env


def flet_cli() -> str:
    executable_name = "flet.exe" if os.name == "nt" else "flet"
    candidate = Path(sys.executable).with_name(executable_name)
    if candidate.is_file():
        return str(candidate)
    found = shutil.which("flet")
    if found:
        return found
    raise RuntimeError("Flet CLI not found; run `python setup.py deps` first")


def remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def run_checked(command: list[str], *, env: dict[str, str], timeout: int | None = None) -> None:
    subprocess.run(command, cwd=ROOT, env=env, check=True, timeout=timeout)


def build(env: dict[str, str]) -> None:
    remove_path(DIST_ROOT)
    remove_path(BUILD_DIR)
    for spec in ROOT.glob("*.spec"):
        spec.unlink(missing_ok=True)

    separator = os.pathsep
    command = [
        flet_cli(),
        "pack",
        str(ROOT / "flet_main.py"),
        "-y",
        "--name",
        APP_NAME,
        "--distpath",
        str(DIST_ROOT),
        "--icon",
        str(ICON),
        "--add-data",
        f"flet_app{os.sep}assets{separator}flet_app{os.sep}assets",
        "--add-data",
        f"rpgmv_decrypter{os.sep}assets{separator}rpgmv_decrypter{os.sep}assets",
    ]
    if os.name == "nt":
        command.insert(3, "-D")
    run_checked(command, env=env)

    exe = PACKAGE_DIR / (f"{APP_NAME}.exe" if os.name == "nt" else APP_NAME)
    if not exe.is_file():
        raise RuntimeError(f"build did not produce {exe}")
    run_checked([str(exe), "--self-test"], env=env, timeout=120)

    remove_path(BUILD_DIR)
    for spec in ROOT.glob("*.spec"):
        spec.unlink(missing_ok=True)
    for name in RUNTIME_ARTIFACTS:
        remove_path(PACKAGE_DIR / name)

    for name in ("LICENSE", "README.md"):
        source = ROOT / name
        if source.is_file():
            shutil.copy2(source, PACKAGE_DIR / name)

    readme = "\n".join(
        (
            "RPG Maker MV/MZ Decrypter - Flet desktop build",
            "",
            f"Run {exe.name}.",
            "Keep this whole folder together; the executable needs the adjacent _internal folder.",
            "The application keeps its portable Flet cache and temporary files in .runtime.",
            "",
        )
    )
    (PACKAGE_DIR / "READ_ME_FIRST.txt").write_text(readme, encoding="utf-8")


def make_zip(version: str) -> Path:
    archive = DIST_ROOT / f"RPGMakerDecrypter-{version}-windows-x64.zip"
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(PACKAGE_DIR.rglob("*")):
            if path.is_file():
                arcname = Path(APP_NAME) / path.relative_to(PACKAGE_DIR)
                bundle.write(path, arcname=str(arcname))
    required = f"{APP_NAME}/{APP_NAME}.exe"
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        if required not in names:
            raise RuntimeError(f"{archive} is missing {required}")
    return archive


def main() -> int:
    env = isolated_environment()
    version = project_version()
    try:
        build(env)
        archive = make_zip(version)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"build failed: {error}", file=sys.stderr)
        return 1
    print()
    print(f"Application: {PACKAGE_DIR}")
    print(f"Archive:     {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
