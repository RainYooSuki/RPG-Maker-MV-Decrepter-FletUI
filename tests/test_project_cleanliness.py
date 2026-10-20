from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LEGACY_FILES = (
    "build_exe.py",
    "launcher.py",
    "rpgmv_decrypter/gui.py",
    "rpgmv_decrypter/gui_theme.py",
    "rpgmv_decrypter/switch.py",
    "rpgmv_decrypter/browse.py",
    "rpgmv_decrypter/motion.py",
    "rpgmv_decrypter/i18n.py",
)


def _project_text_files() -> list[Path]:
    files = []
    for directory in (".github", "docs", "flet_app", "rpgmv_decrypter", "tests"):
        files.extend((ROOT / directory).rglob("*"))
    files.extend(ROOT.glob("*.py"))
    files.extend(ROOT.glob("*.toml"))
    files.extend(ROOT.glob("*.md"))
    files.extend(ROOT.glob("*.cmd"))
    return [
        path
        for path in files
        if path.is_file()
        and not any(part in {".venv", ".home", ".tmp", "dist-flet", "build"} for part in path.parts)
        and path.suffix.lower() in {".py", ".toml", ".md", ".yml", ".yaml", ".cmd"}
    ]


def test_legacy_desktop_modules_are_removed():
    for relative in LEGACY_FILES:
        assert not (ROOT / relative).exists(), f"legacy file still exists: {relative}"


def test_no_pyside_or_nuitka_references():
    forbidden = ("py" + "side", "nuit" + "ka")
    hits = []
    for path in _project_text_files():
        if path == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            if token in text:
                hits.append(f"{path.relative_to(ROOT)}: {token}")
    assert not hits, "legacy toolkit references:\n" + "\n".join(hits)


def test_project_metadata_targets_flet():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'gui = ["flet[desktop]>=1.0,<2"]' in pyproject
    assert 'rpgmv-decrypter-gui = "flet_app.main:run"' in pyproject
    assert 'packages = ["rpgmv_decrypter", "flet_app"]' in pyproject


def test_workflow_runs_tests_and_flet_build():
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(workflow)
    assert set(parsed["jobs"]) == {"test", "build", "release"}
    assert "python setup.py deps" in workflow
    assert ".venv\\Scripts\\python.exe setup.py check" in workflow
    assert "-m pytest -q" in workflow
    assert "-m ruff check" in workflow
    assert "actions/upload-artifact@" in workflow
    assert "softprops/action-gh-release@" in workflow
    assert "python.exe build_flet.py" in workflow
    assert "--self-test" in workflow
    assert "build_exe.py" not in workflow


def test_setup_bootstraps_project_venv():
    setup_py = (ROOT / "setup.py").read_text(encoding="utf-8")
    assert 'VENV_DIR = ROOT / ".venv"' in setup_py
    assert '"-m", "venv"' in setup_py
    assert "in_project_venv" in setup_py
    assert "pip_command(python, packages" in setup_py
