"""Desktop entry point for the Flet application.

Source checkout:
    run_flet.cmd
    python flet_main.py

Packaged build:
    dist-flet\\RPGMakerDecrypterFlet\\RPGMakerDecrypterFlet.exe

Before Flet is imported, this module redirects HOME/APPDATA/TEMP to an
application-local runtime folder. That keeps the source checkout self-contained
and makes the packaged build portable. If the executable directory is read-only,
the normal operating-system user locations are left unchanged as a fallback.

``--self-test`` runs a headless encryption round-trip and checks bundled assets.
The build workflow uses it to verify the packaged executable without opening a
window.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def _portable_environment() -> None:
    frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        app_root = Path(sys.executable).resolve().parent
        runtime = app_root / ".runtime"
    else:
        app_root = Path(__file__).resolve().parent
        runtime = app_root / ".home"

    home = runtime
    tmp = runtime / "tmp"
    cache = runtime / "pip-cache"
    try:
        for path in (
            home,
            tmp,
            cache,
            home / ".flet",
            home / "AppData" / "Local",
            home / "AppData" / "Roaming",
            home / "Desktop",
            home / "Documents",
            home / "Downloads",
        ):
            path.mkdir(parents=True, exist_ok=True)
        probe = tmp / f".write-probe-{os.getpid()}"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError:
        # A read-only installation still needs to launch. Let the operating
        # system provide its normal user folders in that case.
        return

    os.environ["HOME"] = str(home)
    os.environ["USERPROFILE"] = str(home)
    os.environ["LOCALAPPDATA"] = str(home / "AppData" / "Local")
    os.environ["APPDATA"] = str(home / "AppData" / "Roaming")
    os.environ["TMP"] = str(tmp)
    os.environ["TEMP"] = str(tmp)
    os.environ["PIP_CACHE_DIR"] = str(cache)
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    if not frozen and str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))


def _asset_roots() -> tuple[Path, ...]:
    frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        exe_dir = Path(sys.executable).resolve().parent
        return (
            exe_dir / "_internal" / "flet_app" / "assets",
            Path(getattr(sys, "_MEIPASS", exe_dir)) / "flet_app" / "assets",
        )
    return (Path(__file__).resolve().parent / "flet_app" / "assets",)


def _self_test() -> int:
    try:
        from rpgmv_decrypter import NORMAL_PNG_HEADER, Decrypter

        key = "0123456789abcdef0123456789abcdef"
        payload = NORMAL_PNG_HEADER + bytes(range(64))
        encrypted = Decrypter(key).encrypt_bytes(payload)
        assert Decrypter(key).decrypt_bytes(encrypted) == payload
        assert Decrypter(None).restore_png_header_bytes(encrypted) == payload
        assert Decrypter.get_key_from_png(encrypted) == key

        asset_root = next((path for path in _asset_roots() if path.is_dir()), None)
        assert asset_root is not None, "Flet asset directory is missing"
        for name in ("logo-64.png", "logo.ico", "noise.png"):
            assert (asset_root / name).is_file(), f"missing bundled asset: {name}"
    except Exception:
        traceback.print_exc()
        return 1
    print("self-test: ok")
    return 0


_portable_environment()

if "--self-test" in sys.argv:
    raise SystemExit(_self_test())

from flet_app.main import run  # noqa: E402

if __name__ == "__main__":
    run()
