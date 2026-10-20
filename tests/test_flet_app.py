from __future__ import annotations

import json
import time
from pathlib import Path

import flet as ft
import pytest

from flet_app.i18n import Translator, tr
from flet_app.models import clamp_text, file_kind
from flet_app.service import DesktopService
from rpgmv_decrypter import NORMAL_PNG_HEADER, Decrypter, ui_logic

KEY = "0123456789abcdef0123456789abcdef"


def _wait_for(service: DesktopService, event_type: str, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    seen: list[str] = []
    while time.time() < deadline:
        for event in service.drain_events():
            seen.append(event.get("type", "?"))
            if event.get("type") == event_type:
                return event
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting for {event_type}; seen={seen}")


def _make_game(root: Path) -> Path:
    data = root / "www" / "data"
    images = root / "www" / "img" / "pictures"
    data.mkdir(parents=True)
    images.mkdir(parents=True)
    (data / "System.json").write_text(
        json.dumps({"encryptionKey": KEY, "gameTitle": "Test"}),
        encoding="utf-8",
    )
    plain = NORMAL_PNG_HEADER + bytes(range(64))
    (images / "hero.rpgmvp").write_bytes(Decrypter(KEY).encrypt_bytes(plain))
    return root


def test_translation_fallback_and_formatting():
    assert tr("app_title", "zh").startswith("RPG Maker")
    assert "succeeded" in tr("finished_ok", "en", ok=2, skipped=1, failed=0)
    assert tr("missing_key", "zh") == "missing_key"


def test_translator_updates_bound_controls():
    translator = Translator("zh")
    control = ft.Text()
    translator.bind(control, "start_run")
    assert control.value == "开始处理"
    translator.set_language("en")
    assert control.value == "Start"
    translator.set_language("zh")
    assert control.value == "开始处理"


def test_small_model_helpers():
    assert file_kind("hero.rpgmvp") == "image"
    assert file_kind("theme.ogg_") == "audio"
    assert file_kind("System.json") == "text"
    assert clamp_text("a" * 40, 10) == "aaaaaaaaa…"


def test_scan_and_detect_key(tmp_path: Path):
    game = _make_game(tmp_path / "game")
    service = DesktopService()
    try:
        service.scan([game], recursive=True)
        scan_event = _wait_for(service, "scan_finished")
        snapshot = scan_event["snapshot"]
        assert len(snapshot.files) == 2
        assert any(item.name == "hero.rpgmvp" for item in snapshot.files)

        service.detect_key([game], header_len=16)
        key_event = _wait_for(service, "key_detected")
        assert key_event["key"] == KEY
        assert key_event["confirmed"] is True
    finally:
        service.close()


def test_decrypt_job_round_trip(tmp_path: Path):
    game = _make_game(tmp_path / "game")
    output_root = tmp_path / "out"
    service = DesktopService()
    try:
        service.set_output_root(output_root)
        options, error = ui_logic.build_options(recursive=True, header_len="16")
        assert options is not None and not error
        request = ui_logic.BatchRequest(
            mode="decrypt",
            inputs=[game],
            key=KEY,
            options=options,
            package_zip=True,
        )
        assert service.start_job(request)
        event = _wait_for(service, "job_finished", timeout=20)
        result = event["result"]
        assert len(result.result.succeeded) == 1
        assert not result.result.failed
        destination = result.result.succeeded[0].destination
        assert destination is not None and destination.exists()
        assert destination.suffix == ".png"
        assert result.archive is not None and result.archive.exists()
    finally:
        service.close()


def test_cancel_job_reaches_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):

    from rpgmv_decrypter import api

    class SlowRunner:
        def __init__(self, progress: ui_logic.ProgressReport):
            self.progress = progress

        def run(self, request):
            self.progress.start(20)
            for index in range(20):
                if self.progress.cancelled:
                    return ui_logic.RunResult(
                        result=api.RestoreResult(outcomes=(), cancelled=True),
                        run_directory=tmp_path,
                        cancelled=True,
                    )
                self.progress.step(index + 1, 20, f"file-{index}")
                time.sleep(0.03)
            return ui_logic.RunResult(
                result=api.RestoreResult(outcomes=()),
                run_directory=tmp_path,
                nothing_to_do=True,
            )

    monkeypatch.setattr(ui_logic, "BatchRunner", SlowRunner)
    service = DesktopService()
    request = ui_logic.BatchRequest(mode="decrypt", inputs=[tmp_path], key=KEY)
    try:
        assert service.start_job(request)
        _wait_for(service, "progress_start", timeout=5)
        service.cancel_job()
        event = _wait_for(service, "job_finished", timeout=5)
        assert event["result"].cancelled is True
        assert event["result"].result.cancelled is True
    finally:
        service.close()
