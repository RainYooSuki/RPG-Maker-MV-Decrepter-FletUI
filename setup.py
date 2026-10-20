"""Manage the project-local environment and development dependencies.

``pyproject.toml`` is the source of truth for package metadata. This file adds
small maintenance commands that are awkward to express through pip alone::

    python setup.py deps          # create .venv and install GUI/test/build deps
    python setup.py check         # report dependencies in the project .venv
    python setup.py install       # install this project into .venv

Dependencies are installed into ``<project>/.venv`` by default. The tool never
falls back to installing packages into the system Python.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"

GUI_PACKAGE = "flet[desktop]>=1.0,<2"
TEST_PACKAGES = ("pytest>=7.0", "ruff>=0.9", "pyyaml>=6.0")
BUILD_PACKAGES = ("pyinstaller>=6.11",)

MIRRORS = {
    "tsinghua": "https://pypi.tuna.tsinghua.edu.cn/simple",
    "aliyun": "https://mirrors.aliyun.com/pypi/simple/",
    "ustc": "https://pypi.mirrors.ustc.edu.cn/simple/",
}
DEFAULT_MIRROR = "tsinghua"


def venv_python() -> Path:
    """Return the interpreter path inside the project-local venv."""
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def in_project_venv() -> bool:
    """Whether this process is the project-local venv interpreter."""
    try:
        return Path(sys.executable).resolve() == venv_python().resolve()
    except OSError:
        return False


def ensure_venv(*, create: bool = True) -> Path | None:
    """Create the project venv if needed and return its interpreter."""
    python = venv_python()
    if python.exists():
        return python
    if not create:
        return None

    print(f"creating project-local virtual environment: {VENV_DIR}")
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            cwd=str(ROOT),
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"could not create {VENV_DIR}: {error}", file=sys.stderr)
        print("install the Python 'venv' module or create .venv manually", file=sys.stderr)
        return None

    if not python.exists():
        print(f"venv was created but {python} is missing", file=sys.stderr)
        return None
    return python


def installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def package_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "missing"


def pip_command(python: Path, packages: list[str], mirror: str | None) -> int:
    command = [str(python), "-m", "pip", "install", "--upgrade", *packages]
    if mirror:
        command += ["-i", MIRRORS[mirror]]
    print("running: " + " ".join(command))
    return subprocess.call(command, cwd=str(ROOT))


def command_deps(arguments: argparse.Namespace) -> int:
    python = Path(sys.executable) if in_project_venv() else ensure_venv()
    if python is None:
        return 1

    packages = [GUI_PACKAGE]
    if not arguments.runtime_only:
        packages.extend(TEST_PACKAGES)
        packages.extend(BUILD_PACKAGES)

    code = pip_command(python, packages, arguments.mirror)
    if code == 0:
        print(f"\ndependencies installed in: {VENV_DIR}")
        print(f"start with: {venv_python()} flet_main.py")
    return code


def command_check(arguments: argparse.Namespace) -> int:
    del arguments
    if not in_project_venv():
        python = ensure_venv(create=False)
        if python is None:
            print(f"project venv is missing: {VENV_DIR}")
            print("create it with: python setup.py deps")
            return 1
        print(f"checking project venv: {python}")
        return subprocess.call([str(python), str(Path(__file__).resolve()), "check"], cwd=str(ROOT))

    print(f"python {sys.version.split()[0]}  ({sys.executable})")
    groups = (
        ("desktop", (("flet", "flet"), ("flet_desktop", "flet-desktop"))),
        (
            "test/build",
            (
                ("pytest", "pytest"),
                ("ruff", "ruff"),
                ("yaml", "PyYAML"),
                ("PyInstaller", "pyinstaller"),
            ),
        ),
    )
    missing: list[str] = []
    for title, modules in groups:
        print(f"\n{title}:")
        for module, label in modules:
            present = installed(module)
            version = package_version(label)
            print(f"  {label:<16} {'found' if present else 'MISSING':<8} {version}")
            if not present:
                missing.append(label)

    print("\nthe package itself:")
    if installed("rpgmv_decrypter"):
        import rpgmv_decrypter

        print(f"  importable from {Path(rpgmv_decrypter.__file__).parent}")
    else:
        print("  run from the project root or use `pip install -e .`")

    print()
    if missing:
        print("install the missing pieces with: python setup.py deps")
        return 1
    print("all desktop, test and build dependencies are present")
    return 0


def command_install(arguments: argparse.Namespace) -> int:
    python = Path(sys.executable) if in_project_venv() else ensure_venv()
    if python is None:
        return 1
    command = [str(python), "-m", "pip", "install", "."]
    if arguments.mirror:
        command += ["-i", MIRRORS[arguments.mirror]]
    print("running: " + " ".join(command))
    return subprocess.call(command, cwd=str(ROOT))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="setup.py",
        description="Manage the project-local venv and RPG Maker MV/MZ Decrypter.",
    )
    subparsers = parser.add_subparsers(dest="command")

    deps = subparsers.add_parser(
        "deps", help="create .venv and install desktop/test/build dependencies"
    )
    deps.add_argument(
        "--mirror",
        nargs="?",
        const=DEFAULT_MIRROR,
        choices=sorted(MIRRORS),
        help=f"use a package mirror (default when given: {DEFAULT_MIRROR})",
    )
    deps.add_argument(
        "--runtime-only",
        action="store_true",
        help="install the Flet desktop shell without test/build tools",
    )
    deps.set_defaults(func=command_deps)

    check = subparsers.add_parser("check", help="report dependencies in the project .venv")
    check.set_defaults(func=command_check)

    install = subparsers.add_parser("install", help="install this package into the project .venv")
    install.add_argument(
        "--mirror",
        nargs="?",
        const=DEFAULT_MIRROR,
        choices=sorted(MIRRORS),
        help="use a package mirror",
    )
    install.set_defaults(func=command_install)
    return parser


def main() -> int:
    parser = build_parser()
    arguments = parser.parse_args()
    if not getattr(arguments, "command", None):
        parser.print_help()
        return 2
    return arguments.func(arguments)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in {"deps", "check", "install"}:
        raise SystemExit(main())

    try:
        from setuptools import setup
    except ImportError:
        print(
            "setuptools is required to install this package.\n"
            "  python -m pip install setuptools\n"
            "or run: python setup.py check",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    setup()
