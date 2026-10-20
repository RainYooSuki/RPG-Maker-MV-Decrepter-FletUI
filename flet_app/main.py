"""Flet 1.0 desktop shell for RPG Maker MV/MZ Decrypter.

This is the Flet preview UI.  It intentionally keeps all processing in the
existing ``rpgmv_decrypter`` package and only owns presentation, user input and
background-task orchestration here.
"""

from __future__ import annotations

import asyncio
import os
import sys
import traceback
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import flet as ft

from rpgmv_decrypter import ui_logic
from rpgmv_decrypter.decrypter import (
    DEFAULT_HEADER_LEN,
    DEFAULT_REMAIN,
    DEFAULT_SIGNATURE,
    DEFAULT_VERSION,
)
from rpgmv_decrypter.filetypes import (
    DECRYPT_EXTENSIONS,
    ENCRYPT_EXTENSIONS,
    RpgMakerVersion,
)

from . import theme as th
from .i18n import LANGUAGES, Translator
from .models import ScannedFile, ScanSnapshot, SelectedInput, clamp_text, normalise_path
from .service import DesktopService

APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent


MODE_DECRYPT = "decrypt"
MODE_ENCRYPT = "encrypt"
MODE_RESTORE = "restore"

MODE_LABEL_KEYS = {
    MODE_DECRYPT: "run_decrypt",
    MODE_ENCRYPT: "mode_encrypt",
    MODE_RESTORE: "run_restore",
}
MODE_ICONS = {
    MODE_DECRYPT: ft.Icons.LOCK_OPEN_ROUNDED,
    MODE_ENCRYPT: ft.Icons.ENHANCED_ENCRYPTION_ROUNDED,
    MODE_RESTORE: ft.Icons.IMAGE_ROUNDED,
}

FILE_ICONS = {
    "image": ft.Icons.IMAGE_ROUNDED,
    "audio": ft.Icons.AUDIO_FILE_ROUNDED,
    "text": ft.Icons.DESCRIPTION_ROUNDED,
    "archive": ft.Icons.ARCHIVE_ROUNDED,
    "file": ft.Icons.INSERT_DRIVE_FILE_ROUNDED,
}
FILE_COLOURS = {
    "image": th.MINT,
    "audio": th.BLUE,
    "text": th.VIOLET,
    "archive": th.WARNING,
    "file": th.TEXT_MUTED,
}

FILE_ROWS_LIMIT = 160
PREVIEW_LIMIT_BYTES = 16 * 1024 * 1024

SELECTABLE_EXTENSIONS = sorted(
    {
        *DECRYPT_EXTENSIONS,
        *ENCRYPT_EXTENSIONS,
        "json",
        "js",
        "txt",
    }
)
KEY_SOURCE_EXTENSIONS = ["json", "js", "txt", "rpgmvp", "png_"]


@dataclass(frozen=True, slots=True)
class StatusMessage:
    key: str | None
    values: dict[str, Any]
    raw: str = ""
    detail: str = ""
    tone: str = "neutral"


class GlassDecrypterApp:
    """The whole desktop window, in one controlled Flet page."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.t = Translator("zh")
        self.service = DesktopService()
        self.selected_inputs: dict[str, SelectedInput] = {}
        self.scan_generation = 0
        self.scan_snapshot = ScanSnapshot(roots=(), files=())
        self.scanning = False
        self.running = False
        self.cancel_requested = False
        self.mode = MODE_DECRYPT
        self.rpgmaker = "MV"
        self.last_result: ui_logic.RunResult | None = None
        self.filter_query = ""
        self.advanced_open = False
        self.logs: deque[str] = deque(maxlen=500)
        self._shutdown = False
        self._status = StatusMessage("idle", {})
        self._last_log_bucket = -1
        self._log_button: ft.IconButton | None = None
        self.maximize_button: ft.IconButton | None = None
        self._window_maximized = False
        self._preview_dialog_control: ft.Control | None = None
        self._file_picker = ft.FilePicker()

        try:
            self.output_root = self.service.output_root()
        except OSError:
            self.output_root = PROJECT_DIR / "output"

        self._configure_window()
        self._build()
        self._refresh_all()
        self.page.on_close = self._on_close
        self.page.run_task(self._pump_events)
        self.page.update()

    # ------------------------------------------------------------------
    # window / foundation
    # ------------------------------------------------------------------
    def _apply_locale(self, language: str) -> None:
        """Pin Flutter's locale so CJK glyph selection stays Simplified Chinese."""

        current = ft.Locale(
            language_code="zh" if language == "zh" else "en",
            country_code="CN" if language == "zh" else "US",
        )
        self.page.locale_configuration = ft.LocaleConfiguration(
            supported_locales=[
                ft.Locale(language_code="zh", country_code="CN"),
                ft.Locale(language_code="en", country_code="US"),
            ],
            current_locale=current,
        )

    def _configure_window(self) -> None:
        self.page.title = "RPG Maker MV/MZ Decrypter"
        self.page.window.width = 1240
        self.page.window.height = 820
        self.page.window.min_width = 1040
        self.page.window.min_height = 720
        self.page.window.bgcolor = th.BG_DEEP
        self.page.window.title_bar_hidden = True
        self.page.window.title_bar_buttons_hidden = True
        self.page.window.shadow = True
        self.page.window.on_event = self._on_window_event
        self.page.theme_mode = ft.ThemeMode.DARK
        theme = ft.Theme(
            use_material3=True,
            font_family=th.FONT_UI,
            color_scheme_seed=th.ACCENT,
            visual_density=ft.VisualDensity.COMPACT,
            scaffold_bgcolor=th.BG_DEEP,
            canvas_color=th.BG_DEEP,
        )
        self.page.theme = theme
        self.page.dark_theme = theme
        self._apply_locale("zh")
        if self.page.views:
            view = self.page.views[0]
            view.padding = 0
            view.spacing = 0
            view.bgcolor = th.BG_DEEP
            view.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
            view.vertical_alignment = ft.MainAxisAlignment.START

    # ------------------------------------------------------------------
    # title bar
    # ------------------------------------------------------------------
    def _build_titlebar(self) -> ft.Control:
        logo = ft.Container(
            width=38,
            height=38,
            border_radius=13,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[th.accent(0.34), th.white(0.08)],
            ),
            border=ft.Border.all(1, th.white(0.16)),
            shadow=th.glow_shadow(blur=22, opacity=0.18),
            alignment=ft.Alignment.CENTER,
            content=ft.Image(
                src="logo-64.png",
                width=24,
                height=24,
                fit=ft.BoxFit.CONTAIN,
            ),
        )
        title = self.t.bind(
            ft.Text(
                "",
                size=15,
                weight=ft.FontWeight.W_700,
                italic=False,
                font_family=th.FONT_UI,
                color=th.TEXT_PRIMARY,
            ),
            "app_title",
        )
        subtitle = self.t.bind(
            ft.Text(
                "",
                size=10,
                color=th.TEXT_MUTED,
                weight=ft.FontWeight.W_500,
                italic=False,
                font_family=th.FONT_UI,
            ),
            "app_subtitle",
        )
        brand = ft.Column(
            [title, subtitle],
            spacing=2,
            alignment=ft.MainAxisAlignment.CENTER,
        )
        # Keep text and controls outside WindowDragArea.  Only the blank middle
        # strip starts the native drag; this avoids the odd text transform some
        # Flutter/Flet versions apply to drag-area children.
        drag_area = ft.WindowDragArea(
            content=ft.Container(expand=True, height=64),
            expand=True,
            height=64,
            maximizable=True,
            on_double_tap=self._on_drag_double_tap,
        )

        language = self._build_language_switch()
        self._log_button = th.icon_button(
            ft.Icons.TERMINAL_ROUNDED,
            tooltip=self.t("show_log"),
            on_click=self._open_log,
            size=17,
        )
        self.maximize_button = th.icon_button(
            ft.Icons.CROP_SQUARE_ROUNDED,
            tooltip=self.t("maximize"),
            on_click=self._maximize_window,
            size=15,
        )
        window_controls = ft.Row(
            [
                th.icon_button(
                    ft.Icons.REMOVE_ROUNDED,
                    tooltip=self.t("minimize"),
                    on_click=self._minimize_window,
                    size=18,
                ),
                self.maximize_button,
                th.icon_button(
                    ft.Icons.CLOSE_ROUNDED,
                    tooltip=self.t("close_window"),
                    on_click=self._close_window,
                    size=18,
                    color=th.TEXT_MUTED,
                ),
            ],
            spacing=2,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.Container(
            height=68,
            padding=ft.Padding.only(left=22, right=10, top=2),
            bgcolor=ft.Colors.with_opacity(0.72, "#07101A"),
            border=ft.Border.only(bottom=ft.BorderSide(1, th.white(0.055))),
            content=ft.Row(
                [
                    logo,
                    brand,
                    drag_area,
                    language,
                    ft.Container(width=1, height=22, bgcolor=th.white(0.09)),
                    self._log_button,
                    window_controls,
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _build_language_switch(self) -> ft.Control:
        self.language_buttons: dict[str, tuple[ft.Container, ft.Text]] = {}
        controls: list[ft.Control] = []
        for code, key in (("zh", "lang_zh"), ("en", "lang_en")):
            text = self.t.bind(
                ft.Text("", size=10, weight=ft.FontWeight.W_700, color=th.TEXT_MUTED),
                key,
            )
            button = ft.Container(
                content=text,
                width=30,
                height=24,
                border_radius=8,
                alignment=ft.Alignment.CENTER,
                on_click=lambda e, c=code: self._set_language(c),
            )
            self.language_buttons[code] = (button, text)
            controls.append(button)
        return ft.Container(
            content=ft.Row(controls, spacing=2),
            padding=3,
            border_radius=11,
            bgcolor=th.white(0.035),
            border=ft.Border.all(1, th.white(0.07)),
        )

    def _refresh_window_controls(self) -> None:
        if self.maximize_button is None:
            return
        maximized = bool(self._window_maximized)
        self.maximize_button.icon = (
            ft.Icons.FILTER_NONE_ROUNDED if maximized else ft.Icons.CROP_SQUARE_ROUNDED
        )
        self.maximize_button.tooltip = self.t("restore_window" if maximized else "maximize")

    def _on_window_event(self, e: ft.WindowEvent) -> None:
        event_type = e.type
        if event_type == ft.WindowEventType.MAXIMIZE:
            self._window_maximized = True
        elif event_type in {
            ft.WindowEventType.UNMAXIMIZE,
            ft.WindowEventType.RESTORE,
        }:
            self._window_maximized = False
        elif event_type in {ft.WindowEventType.RESIZED, ft.WindowEventType.RESIZE}:
            self._window_maximized = bool(self.page.window.maximized)
        else:
            return
        self._refresh_window_controls()
        try:
            self.page.update()
        except Exception:
            pass

    def _on_drag_double_tap(self, e: ft.WindowEvent) -> None:
        if e.type == ft.WindowEventType.MAXIMIZE:
            self._window_maximized = True
        elif e.type == ft.WindowEventType.UNMAXIMIZE:
            self._window_maximized = False
        self._refresh_window_controls()
        self.page.update()

    async def _minimize_window(self, e: Any = None) -> None:
        self.page.window.minimized = True
        self.page.update()

    async def _maximize_window(self, e: Any = None) -> None:
        maximized = not bool(self.page.window.maximized)
        self.page.window.maximized = maximized
        self._window_maximized = maximized
        self._refresh_window_controls()
        self.page.update()

    async def _close_window(self, e: Any = None) -> None:
        self.service.close()
        self._shutdown = True
        await self.page.window.close()

    def _on_close(self, e: Any = None) -> None:
        self._shutdown = True
        self.service.close()

    # ------------------------------------------------------------------
    # main layout
    # ------------------------------------------------------------------
    def _build(self) -> None:
        titlebar = self._build_titlebar()
        source_panel = self._build_source_panel()
        settings_panel = self._build_settings_panel()
        command_bar = self._build_command_bar()

        body = ft.Column(
            [
                titlebar,
                ft.Container(
                    expand=True,
                    padding=ft.Padding.only(left=18, right=18, top=14, bottom=14),
                    content=ft.Column(
                        [
                            ft.Row(
                                [source_panel, settings_panel],
                                spacing=14,
                                expand=True,
                                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                            ),
                            ft.Container(height=12),
                            command_bar,
                        ],
                        spacing=0,
                        expand=True,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    ),
                ),
            ],
            spacing=0,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        root = ft.Stack(
            [
                th.aurora_background(),
                ft.Container(content=body, expand=True),
            ],
            expand=True,
        )
        self.page.add(root)

    # ------------------------------------------------------------------
    # source panel
    # ------------------------------------------------------------------
    def _build_source_panel(self) -> ft.Control:
        marker = th.section_marker(ft.Icons.FOLDER_OPEN_ROUNDED, "")
        self.t.bind(marker.controls[1], "input_section")

        self.add_files_button = th.quiet_button(
            self.t("add_files"),
            icon=ft.Icons.ADD_ROUNDED,
            on_click=self._pick_files,
        )
        self.add_folder_button = th.quiet_button(
            self.t("add_folder"),
            icon=ft.Icons.CREATE_NEW_FOLDER_ROUNDED,
            on_click=self._pick_folder,
        )
        self.t.bind(self.add_files_button, "add_files", attr="content")
        self.t.bind(self.add_folder_button, "add_folder", attr="content")

        intake_icon = ft.Container(
            width=44,
            height=44,
            border_radius=14,
            alignment=ft.Alignment.CENTER,
            bgcolor=th.accent(0.12),
            border=ft.Border.all(1, th.accent(0.20)),
            content=ft.Icon(ft.Icons.UPLOAD_FILE_ROUNDED, size=21, color=th.ACCENT),
        )
        intake_title = self.t.bind(
            ft.Text("", size=14, weight=ft.FontWeight.W_600, color=th.TEXT_PRIMARY),
            "add_sources_title",
        )
        intake_hint = self.t.bind(
            ft.Text("", size=11, color=th.TEXT_MUTED, max_lines=2),
            "input_helper",
        )
        intake = th.surface(
            ft.Row(
                [
                    intake_icon,
                    ft.Column([intake_title, intake_hint], spacing=2, expand=True),
                    ft.Row(
                        [self.add_files_button, self.add_folder_button],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=14,
            fill=0.042,
            border=0.08,
            radius=th.RADIUS_LG,
        )

        self.roots_row = ft.Row(
            controls=[],
            spacing=6,
            run_spacing=6,
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.summary_text = ft.Text(
            "", size=12, color=th.TEXT_SECONDARY, weight=ft.FontWeight.W_600
        )
        self.usable_text = ft.Text("", size=11, color=th.TEXT_MUTED)
        self.filter_field = th.field(
            hint=self.t("search_files"),
            width=210,
            height=34,
            text_size=11,
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            on_change=self._on_filter_change,
        )
        self.t.bind(self.filter_field, "search_files", attr="hint_text")
        self.clear_inputs_button = th.icon_button(
            ft.Icons.DELETE_SWEEP_ROUNDED,
            tooltip=self.t("clear_all"),
            on_click=self._clear_inputs,
            size=17,
            disabled=True,
        )
        summary_row = ft.Row(
            [
                ft.Column(
                    [self.summary_text, self.usable_text],
                    spacing=1,
                    expand=True,
                ),
                self.filter_field,
                self.clear_inputs_button,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.file_list = ft.ListView(
            controls=[],
            expand=True,
            spacing=4,
            padding=0,
            auto_scroll=False,
        )
        self.file_note = ft.Text("", size=10, color=th.TEXT_FAINT, max_lines=2)
        self.scan_warning = ft.Text("", size=10, color=th.WARNING, max_lines=2, visible=False)

        content = ft.Column(
            [
                marker,
                ft.Container(height=1),
                intake,
                self.roots_row,
                summary_row,
                th.divider_line(opacity=0.065),
                self.file_list,
                self.file_note,
                self.scan_warning,
            ],
            spacing=9,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.source_panel = th.glass_panel(content, expand=7, padding=18)
        return self.source_panel

    # ------------------------------------------------------------------
    # settings panel
    # ------------------------------------------------------------------
    def _build_settings_panel(self) -> ft.Control:
        marker = th.section_marker(ft.Icons.TUNE_ROUNDED, "")
        self.t.bind(marker.controls[1], "mode_section")

        self.mode_tabs: dict[str, tuple[ft.Container, ft.Icon, ft.Text]] = {}
        mode_controls: list[ft.Control] = []
        for mode in (MODE_DECRYPT, MODE_ENCRYPT, MODE_RESTORE):
            label = self.t.bind(
                ft.Text(
                    self.t(MODE_LABEL_KEYS[mode]),
                    size=11,
                    weight=ft.FontWeight.W_600,
                    color=th.TEXT_SECONDARY,
                ),
                MODE_LABEL_KEYS[mode],
            )
            icon = ft.Icon(MODE_ICONS[mode], size=17, color=th.TEXT_MUTED)
            box = ft.Container(
                content=ft.Column(
                    [icon, label],
                    spacing=4,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                height=58,
                expand=True,
                border_radius=14,
                border=ft.Border.all(1, th.white(0.06)),
                bgcolor=th.white(0.025),
                alignment=ft.Alignment.CENTER,
                on_click=lambda e, m=mode: self._set_mode(m),
            )
            self.mode_tabs[mode] = (box, icon, label)
            mode_controls.append(box)
        mode_row = ft.Row(mode_controls, spacing=6)
        self.mode_hint = ft.Text("", size=11, color=th.TEXT_MUTED, max_lines=2)

        self.version_label = self.t.bind(
            ft.Text("", size=11, color=th.TEXT_MUTED),
            "target_rpgmaker",
        )
        self.version_buttons: dict[str, ft.Container] = {}
        version_controls: list[ft.Control] = []
        for value, key in (("MV", "rpgmaker_mv"), ("MZ", "rpgmaker_mz")):
            label = self.t.bind(
                ft.Text(self.t(key), size=9, color=th.TEXT_MUTED, weight=ft.FontWeight.W_600),
                key,
            )
            box = ft.Container(
                content=label,
                height=30,
                padding=ft.Padding.symmetric(horizontal=9),
                border_radius=9,
                border=ft.Border.all(1, th.white(0.06)),
                bgcolor=th.white(0.025),
                alignment=ft.Alignment.CENTER,
                on_click=lambda e, v=value: self._set_rpgmaker(v),
            )
            self.version_buttons[value] = box
            version_controls.append(box)
        self.version_section = ft.Column(
            [
                self.version_label,
                ft.Row(version_controls, spacing=5),
            ],
            spacing=6,
            visible=False,
        )

        # key -----------------------------------------------------------------
        key_marker = th.section_marker(ft.Icons.KEY_ROUNDED, "")
        self.t.bind(key_marker.controls[1], "key_section")
        self.key_optional = th.tiny_pill(self.t("key_optional"), color=th.BLUE)
        key_header = ft.Row(
            [key_marker, ft.Container(expand=True), self.key_optional],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.key_field = th.field(
            hint=self.t("key_placeholder"),
            text_size=11,
            height=42,
            on_change=self._on_key_change,
            on_submit=lambda e: self._start_job(),
        )
        self.t.bind(self.key_field, "key_placeholder", attr="hint_text")
        self.detect_key_button = th.quiet_button(
            self.t("detect_from_selection"),
            icon=ft.Icons.AUTO_AWESOME_ROUNDED,
            on_click=self._detect_key_from_selection,
        )
        self.t.bind(self.detect_key_button, "detect_from_selection", attr="content")
        self.pick_key_button = th.icon_button(
            ft.Icons.FOLDER_OPEN_ROUNDED,
            tooltip=self.t("browse_key_file"),
            on_click=self._pick_key_source,
            size=16,
        )
        self.key_feedback = ft.Text(self.t("key_hint"), size=10, color=th.TEXT_FAINT, max_lines=3)
        key_controls = ft.Column(
            [
                key_header,
                self.key_field,
                ft.Row(
                    [self.detect_key_button, self.pick_key_button],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.key_feedback,
            ],
            spacing=7,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        # output --------------------------------------------------------------
        out_marker = th.section_marker(ft.Icons.OUTPUT_ROUNDED, "")
        self.t.bind(out_marker.controls[1], "output_section")
        self.output_path_text = ft.Text(
            str(self.output_root),
            size=11,
            color=th.TEXT_SECONDARY,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            weight=ft.FontWeight.W_500,
            tooltip=str(self.output_root),
        )
        self.output_hint = self.t.bind(
            ft.Text("", size=10, color=th.TEXT_FAINT, max_lines=2),
            "output_hint",
        )
        self.change_output_button = th.icon_button(
            ft.Icons.EDIT_ROUNDED,
            tooltip=self.t("change_output"),
            on_click=self._choose_output,
            size=16,
        )
        self.open_output_button = th.icon_button(
            ft.Icons.OPEN_IN_NEW_ROUNDED,
            tooltip=self.t("open_output_root"),
            on_click=self._open_output_root,
            size=16,
        )
        output_surface = th.surface(
            ft.Row(
                [
                    ft.Container(
                        width=34,
                        height=34,
                        border_radius=10,
                        alignment=ft.Alignment.CENTER,
                        bgcolor=th.white(0.05),
                        content=ft.Icon(ft.Icons.FOLDER_ROUNDED, size=17, color=th.BLUE),
                    ),
                    ft.Column(
                        [self.output_path_text, self.output_hint],
                        spacing=2,
                        expand=True,
                    ),
                    self.change_output_button,
                    self.open_output_button,
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=11,
            fill=0.035,
            border=0.07,
        )
        output_controls = ft.Column([out_marker, output_surface], spacing=7)

        # advanced ------------------------------------------------------------
        self.advanced_label = ft.Text("", size=11, color=th.TEXT_MUTED, weight=ft.FontWeight.W_600)
        self.advanced_chevron = ft.Icon(ft.Icons.EXPAND_MORE_ROUNDED, size=17, color=th.TEXT_MUTED)
        self.advanced_toggle = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.TUNE_ROUNDED, size=16, color=th.TEXT_MUTED),
                    self.advanced_label,
                    ft.Container(expand=True),
                    self.advanced_chevron,
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=4, vertical=5),
            border_radius=10,
            on_click=self._toggle_advanced,
        )
        self.advanced_panel = self._build_advanced_panel(visible=False)

        privacy = self.t.bind(
            ft.Text(
                "",
                size=9,
                color=th.TEXT_FAINT,
                text_align=ft.TextAlign.CENTER,
            ),
            "privacy_note",
        )

        self.settings_scroll = ft.Column(
            [
                marker,
                mode_row,
                self.mode_hint,
                self.version_section,
                th.divider_line(opacity=0.06),
                key_controls,
                th.divider_line(opacity=0.06),
                output_controls,
                th.divider_line(opacity=0.06),
                self.advanced_toggle,
                self.advanced_panel,
                ft.Container(expand=True),
                privacy,
            ],
            spacing=11,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        content = self.settings_scroll
        self.settings_panel = th.glass_panel(content, expand=4, padding=18)
        return self.settings_panel

    def _build_advanced_panel(self, *, visible: bool = False) -> ft.Control:
        self.verify_switch = ft.Switch(
            value=True,
            active_color=th.ACCENT,
            active_track_color=th.accent(0.28),
            on_change=self._noop,
        )
        self.recursive_switch = ft.Switch(
            value=True,
            active_color=th.ACCENT,
            active_track_color=th.accent(0.28),
            on_change=self._on_recursive_change,
        )
        self.zip_switch = ft.Switch(
            value=False,
            active_color=th.ACCENT,
            active_track_color=th.accent(0.28),
            on_change=self._noop,
        )
        verify_row = self._switch_row("verify_header", "verify_header_hint", self.verify_switch)
        recursive_row = self._switch_row("recursive", None, self.recursive_switch)
        zip_row = self._switch_row("package_zip", "package_zip_hint", self.zip_switch)

        def labelled_field(key: str, control: ft.Control) -> ft.Control:
            label = self.t.bind(ft.Text("", size=9, color=th.TEXT_FAINT), key)
            return ft.Column([label, control], spacing=4)

        self.header_len_field = th.field(
            value=str(DEFAULT_HEADER_LEN),
            text_size=11,
            height=36,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.signature_field = th.field(
            value=DEFAULT_SIGNATURE,
            text_size=11,
            height=36,
        )
        self.version_field = th.field(
            value=DEFAULT_VERSION,
            text_size=11,
            height=36,
        )
        self.remain_field = th.field(
            value=DEFAULT_REMAIN,
            text_size=11,
            height=36,
        )
        self.advanced_note = self.t.bind(
            ft.Text("", size=9, color=th.TEXT_FAINT, max_lines=3),
            "advanced_hint",
        )
        return ft.Container(
            visible=visible,
            padding=ft.Padding.only(top=2),
            content=ft.Column(
                [
                    verify_row,
                    recursive_row,
                    zip_row,
                    ft.Row(
                        [
                            labelled_field("header_len", self.header_len_field),
                            ft.Container(expand=True),
                        ],
                        spacing=6,
                    ),
                    labelled_field("signature", self.signature_field),
                    ft.Row(
                        [
                            labelled_field("version_field", self.version_field),
                            labelled_field("remain", self.remain_field),
                        ],
                        spacing=6,
                    ),
                    self.advanced_note,
                ],
                spacing=9,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    def _switch_row(self, title_key: str, hint_key: str | None, switch: ft.Switch) -> ft.Control:
        title = self.t.bind(
            ft.Text("", size=10, color=th.TEXT_SECONDARY, weight=ft.FontWeight.W_500),
            title_key,
        )
        controls: list[ft.Control] = [title]
        if hint_key:
            controls.append(
                self.t.bind(ft.Text("", size=8, color=th.TEXT_FAINT, max_lines=2), hint_key)
            )
        return ft.Row(
            [
                ft.Column(controls, spacing=1, expand=True),
                switch,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _noop(self, e: Any = None) -> None:
        return None

    # ------------------------------------------------------------------
    # command bar
    # ------------------------------------------------------------------
    def _build_command_bar(self) -> ft.Control:
        self.status_icon = ft.Icon(ft.Icons.BOLT_ROUNDED, size=18, color=th.ACCENT)
        self.status_icon_bg = ft.Container(
            width=38,
            height=38,
            border_radius=13,
            alignment=ft.Alignment.CENTER,
            bgcolor=th.accent(0.10),
            border=ft.Border.all(1, th.accent(0.18)),
            content=self.status_icon,
        )
        self.status_title = ft.Text("", size=13, color=th.TEXT_PRIMARY, weight=ft.FontWeight.W_600)
        self.status_detail = ft.Text(
            "", size=10, color=th.TEXT_MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS
        )
        status_column = ft.Column(
            [self.status_title, self.status_detail],
            spacing=2,
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
        )

        self.cancel_button = th.quiet_button(
            self.t("cancel_run"),
            icon=ft.Icons.STOP_CIRCLE_ROUNDED,
            on_click=self._cancel_job,
            width=112,
        )
        self.t.bind(self.cancel_button, "cancel_run", attr="content")
        self.cancel_button.visible = False
        self.report_button = th.quiet_button(
            self.t("view_report"),
            icon=ft.Icons.LIST_ALT_ROUNDED,
            on_click=self._show_report,
            width=116,
        )
        self.t.bind(self.report_button, "view_report", attr="content")
        self.report_button.visible = False
        self.open_results_button = th.quiet_button(
            self.t("open_results"),
            icon=ft.Icons.OPEN_IN_NEW_ROUNDED,
            on_click=self._open_results,
            width=144,
        )
        self.t.bind(self.open_results_button, "open_results", attr="content")
        self.open_results_button.visible = False
        self.start_button = th.primary_button(
            self.t("start_run"),
            icon=ft.Icons.PLAY_ARROW_ROUNDED,
            on_click=self._start_job,
            width=148,
        )
        self.t.bind(self.start_button, "start_run", attr="content")
        action_row = ft.Row(
            [
                self.cancel_button,
                self.report_button,
                self.open_results_button,
                self.start_button,
            ],
            spacing=7,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.progress_bar = ft.ProgressBar(
            value=0,
            bar_height=4,
            color=th.ACCENT,
            bgcolor=th.white(0.07),
            border_radius=8,
            expand=True,
        )
        self.progress_pct = ft.Text(
            "0%", size=9, color=th.TEXT_MUTED, width=34, text_align=ft.TextAlign.RIGHT
        )

        content = ft.Column(
            [
                ft.Row(
                    [self.status_icon_bg, status_column, action_row],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [self.progress_bar, self.progress_pct],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=7,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.command_bar = th.glass_panel(
            content,
            radius=th.RADIUS_LG,
            padding=13,
            tint=0.075,
            edge=0.17,
        )
        return self.command_bar

    # ------------------------------------------------------------------
    # i18n / visual refreshers
    # ------------------------------------------------------------------
    def _set_language(self, language: str) -> None:
        if language not in LANGUAGES:
            return
        self.t.set_language(language)
        self._apply_locale(language)
        self._refresh_language_buttons()
        self._refresh_tooltips()
        self._refresh_mode_ui()
        self._refresh_roots()
        self._refresh_file_list()
        self._refresh_selection_summary()
        self._refresh_advanced_toggle()
        self._refresh_status_from_state()
        self.page.update()

    def _refresh_language_buttons(self) -> None:
        for code, (button, text) in self.language_buttons.items():
            selected = code == self.t.language
            button.bgcolor = th.accent(0.16) if selected else None
            button.border = ft.Border.all(1, th.accent(0.24) if selected else th.white(0.0))
            text.color = th.ACCENT_SOFT if selected else th.TEXT_MUTED

    def _refresh_tooltips(self) -> None:
        self._refresh_window_controls()
        self.clear_inputs_button.tooltip = self.t("clear_all")
        self.pick_key_button.tooltip = self.t("browse_key_file")
        self.change_output_button.tooltip = self.t("change_output")
        self.open_output_button.tooltip = self.t("open_output_root")
        if self._log_button is not None:
            self._log_button.tooltip = self.t("show_log")

    def _refresh_mode_ui(self) -> None:
        for mode, (box, icon, label) in self.mode_tabs.items():
            selected = mode == self.mode
            box.bgcolor = th.accent(0.15) if selected else th.white(0.025)
            box.border = ft.Border.all(
                1,
                th.accent(0.38) if selected else th.white(0.06),
            )
            box.shadow = th.glow_shadow(blur=18, opacity=0.20) if selected else None
            icon.color = th.ACCENT if selected else th.TEXT_MUTED
            label.color = th.TEXT_PRIMARY if selected else th.TEXT_SECONDARY
            box.ignore_interactions = self.running
        hint_key = {
            MODE_DECRYPT: "mode_hint_decrypt",
            MODE_ENCRYPT: "mode_hint_encrypt",
            MODE_RESTORE: "mode_hint_restore",
        }[self.mode]
        self.mode_hint.value = self.t(hint_key)
        self.version_section.visible = self.mode == MODE_ENCRYPT
        for value, box in self.version_buttons.items():
            selected = value == self.rpgmaker
            box.bgcolor = th.accent(0.13) if selected else th.white(0.025)
            box.border = ft.Border.all(1, th.accent(0.25) if selected else th.white(0.06))
            if isinstance(box.content, ft.Text):
                box.content.color = th.TEXT_PRIMARY if selected else th.TEXT_MUTED
        restore = self.mode == MODE_RESTORE
        self.key_optional.visible = restore
        self.key_field.disabled = restore or self.running
        self.detect_key_button.disabled = restore or self.running
        self.pick_key_button.disabled = restore or self.running
        if restore:
            self.key_feedback.value = self.t("key_optional")
            self.key_feedback.color = th.BLUE
        elif self.key_feedback.color == th.BLUE:
            self.key_feedback.value = self.t("key_hint")
            self.key_feedback.color = th.TEXT_FAINT

    def _refresh_advanced_toggle(self) -> None:
        self.advanced_label.value = self.t(
            "advanced_hide" if self.advanced_open else "advanced_show"
        )
        self.advanced_chevron.icon = (
            ft.Icons.EXPAND_LESS_ROUNDED if self.advanced_open else ft.Icons.EXPAND_MORE_ROUNDED
        )

    def _refresh_roots(self) -> None:
        controls: list[ft.Control] = []
        for key, item in self.selected_inputs.items():
            icon = ft.Icons.FOLDER_ROUNDED if item.is_dir else ft.Icons.INSERT_DRIVE_FILE_ROUNDED
            label = clamp_text(item.name, 30)
            chip = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(icon, size=12, color=th.ACCENT if item.is_dir else th.BLUE),
                        ft.Text(label, size=9, color=th.TEXT_SECONDARY, max_lines=1),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE_ROUNDED,
                            icon_size=11,
                            icon_color=th.TEXT_FAINT,
                            tooltip=self.t("remove"),
                            on_click=lambda e, k=key: self._remove_input(k),
                            style=ft.ButtonStyle(padding=3, shape=th.rounded(8)),
                        ),
                    ],
                    spacing=5,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.only(left=9, right=3, top=3, bottom=3),
                border_radius=10,
                bgcolor=th.white(0.045),
                border=ft.Border.all(1, th.white(0.07)),
                tooltip=str(item.path),
            )
            controls.append(chip)
        self.roots_row.controls = controls
        self.roots_row.visible = bool(controls)
        self.clear_inputs_button.disabled = self.running or not bool(controls)
        self.add_files_button.disabled = self.running
        self.add_folder_button.disabled = self.running

    def _refresh_file_list(self) -> None:
        needle = self.filter_query.casefold().strip()
        files = list(self.scan_snapshot.files)
        if needle:
            files = [
                item
                for item in files
                if needle in item.name.casefold() or needle in str(item.path).casefold()
            ]
        files.sort(key=lambda item: (str(item.path.parent).casefold(), item.name.casefold()))
        self.filter_field.visible = bool(self.scan_snapshot.files) or self.scanning
        self.file_list.controls.clear()

        if self.scanning and not self.scan_snapshot.files:
            self.file_list.controls.append(
                self._empty_list_state("status_scanning", "files_found", scanning=True)
            )
            self.file_note.value = ""
            return
        if not self.selected_inputs:
            self.file_list.controls.append(
                self._empty_list_state("no_files_title", "no_files_hint")
            )
            self.file_note.value = ""
            return
        if not self.scan_snapshot.files:
            self.file_list.controls.append(
                self._empty_list_state("nothing_to_do", "nothing_to_process_hint")
            )
            self.file_note.value = ""
            return

        shown = files[:FILE_ROWS_LIMIT]
        usable = sum(1 for item in files if self._is_usable(item))
        for item in shown:
            self.file_list.controls.append(self._file_row(item))
        if not shown:
            self.file_list.controls.append(self._empty_list_state("no_files_title", "search_files"))
        if len(files) > len(shown):
            self.file_note.value = self.t("files_showing", shown=len(shown), total=len(files))
        elif needle:
            self.file_note.value = self.t("files_found", count=len(files))
        else:
            self.file_note.value = ""
        if usable == 0 and files:
            self.file_note.value = self.t("status_no_usable")

    def _empty_list_state(
        self, title_key: str, hint_key: str, *, scanning: bool = False
    ) -> ft.Control:
        icon = (
            ft.ProgressRing(width=22, height=22, stroke_width=2, color=th.ACCENT)
            if scanning
            else ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, size=34, color=th.white(0.16))
        )
        return ft.Container(
            height=210,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                [
                    icon,
                    ft.Text(
                        self.t(title_key),
                        size=13,
                        color=th.TEXT_SECONDARY,
                        weight=ft.FontWeight.W_600,
                    ),
                    ft.Text(
                        self.t(hint_key),
                        size=11,
                        color=th.TEXT_FAINT,
                        text_align=ft.TextAlign.CENTER,
                        max_lines=2,
                    ),
                ],
                spacing=7,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        )

    def _file_row(self, item: ScannedFile) -> ft.Control:
        usable = self._is_usable(item)
        colour = FILE_COLOURS.get(item.kind, th.TEXT_MUTED)
        ext = item.extension.upper() if item.extension else "FILE"
        icon = ft.Container(
            width=30,
            height=30,
            border_radius=9,
            alignment=ft.Alignment.CENTER,
            bgcolor=ft.Colors.with_opacity(0.10 if usable else 0.045, colour),
            content=ft.Icon(
                FILE_ICONS.get(item.kind, ft.Icons.INSERT_DRIVE_FILE_ROUNDED),
                size=15,
                color=colour if usable else th.TEXT_FAINT,
            ),
        )
        name = ft.Text(
            item.name,
            size=12,
            color=th.TEXT_PRIMARY if usable else th.TEXT_MUTED,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            weight=ft.FontWeight.W_500,
        )
        parent = ft.Text(
            str(item.path.parent),
            size=9,
            color=th.TEXT_FAINT,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        return ft.Container(
            content=ft.Row(
                [
                    icon,
                    ft.Column([name, parent], spacing=1, expand=True),
                    th.tiny_pill(ext, color=colour if usable else th.TEXT_FAINT),
                    ft.Text(
                        ui_logic.format_size(item.size),
                        size=10,
                        color=th.TEXT_FAINT,
                        width=54,
                        text_align=ft.TextAlign.RIGHT,
                    ),
                ],
                spacing=9,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=9, vertical=6),
            border_radius=11,
            bgcolor=th.white(0.024) if usable else th.white(0.012),
            border=ft.Border.all(1, th.white(0.045) if usable else th.white(0.02)),
            opacity=1.0 if usable else 0.64,
            tooltip=None if usable else self.t("not_supported"),
        )

    def _refresh_selection_summary(self) -> None:
        files = self.scan_snapshot.files
        total = len(files)
        usable = sum(1 for item in files if self._is_usable(item))
        if self.scanning:
            self.summary_text.value = self.t("status_scanning")
            self.usable_text.value = self.t("files_found", count=total)
        elif not self.selected_inputs:
            self.summary_text.value = self.t("no_files_title")
            self.usable_text.value = self.t("no_files_hint")
        elif total:
            self.summary_text.value = self.t("files_found", count=total)
            self.usable_text.value = self.t("files_usable", count=usable)
        else:
            self.summary_text.value = self.t("nothing_to_do")
            self.usable_text.value = ""
        self.scan_warning.visible = bool(self.scan_snapshot.warning)
        if self.scan_snapshot.warning:
            self.scan_warning.value = self.t(
                "output_is_input_warning", path=self.scan_snapshot.warning
            )

    # ------------------------------------------------------------------
    # actions: input and settings
    # ------------------------------------------------------------------
    def _picker_initial_directory(self) -> str:
        """Return an existing folder for native file dialogs.

        In portable mode HOME points at the app-local runtime folder.  Flet's
        native dialog defaults to ``$HOME/Desktop``, which is not normally
        present there.  Prefer the user's current input location or the export
        root, and guarantee that the path we pass actually exists.
        """

        for item in self.selected_inputs.values():
            candidate = item.path if item.is_dir else item.path.parent
            try:
                if candidate.is_dir():
                    return str(candidate)
            except OSError:
                continue
        try:
            run_dir = self._valid_run_directory(self.last_result)
            if run_dir is not None:
                return str(run_dir)
        except Exception:
            pass
        try:
            self.output_root.mkdir(parents=True, exist_ok=True)
            if self.output_root.is_dir():
                return str(self.output_root)
        except OSError:
            pass
        try:
            home = Path.home()
            home.mkdir(parents=True, exist_ok=True)
            return str(home)
        except OSError:
            return str(Path.cwd())

    async def _pick_files(self, e: Any = None) -> None:
        if self.running:
            return
        result = await self._file_picker.pick_files(
            dialog_title=self.t("choose_inputs"),
            initial_directory=self._picker_initial_directory(),
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=SELECTABLE_EXTENSIONS,
            allow_multiple=True,
        )
        paths = [item.path for item in (result or []) if item.path]
        if paths:
            self._add_inputs(paths)

    async def _pick_folder(self, e: Any = None) -> None:
        if self.running:
            return
        path = await self._file_picker.get_directory_path(
            dialog_title=self.t("choose_folder"),
            initial_directory=self._picker_initial_directory(),
        )
        if path:
            self._add_inputs([path])

    async def _pick_key_source(self, e: Any = None) -> None:
        if self.running:
            return
        result = await self._file_picker.pick_files(
            dialog_title=self.t("choose_key_file"),
            initial_directory=self._picker_initial_directory(),
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=KEY_SOURCE_EXTENSIONS,
            allow_multiple=False,
        )
        paths = [item.path for item in (result or []) if item.path]
        if paths:
            self._run_key_detection(paths)

    async def _choose_output(self, e: Any = None) -> None:
        if self.running:
            return
        path = await self._file_picker.get_directory_path(
            dialog_title=self.t("choose_output"),
            initial_directory=str(self.output_root),
        )
        if not path:
            return
        try:
            self.service.set_output_root(path)
        except OSError as error:
            self._set_status_raw(self.t("failed", error=str(error)), tone="danger")
            self.page.update()
            return
        self.output_root = self.service.output_root()
        self.output_path_text.value = str(self.output_root)
        self.output_path_text.tooltip = str(self.output_root)
        self._append_log(f"Output root: {self.output_root}")
        self.page.update()

    def _add_inputs(self, paths: Sequence[str | os.PathLike[str]]) -> None:
        if self.running:
            return
        changed = False
        for raw in paths:
            try:
                path = normalise_path(raw)
            except OSError:
                continue
            if not path.exists():
                self._append_log(f"Missing path: {path}")
                continue
            key = os.path.normcase(str(path))
            if key in self.selected_inputs:
                continue
            self.selected_inputs[key] = SelectedInput(path=path, is_dir=path.is_dir())
            changed = True
        if changed:
            self._schedule_scan()

    def _remove_input(self, key: str) -> None:
        if self.running:
            return
        self.selected_inputs.pop(key, None)
        self._schedule_scan()

    async def _clear_inputs(self, e: Any = None) -> None:
        if self.running:
            return
        self.selected_inputs.clear()
        self.scan_generation = self.service.scan((), recursive=bool(self.recursive_switch.value))
        self.scanning = False
        self.scan_snapshot = ScanSnapshot(roots=(), files=())
        self.filter_query = ""
        self.filter_field.value = ""
        self._set_status("idle", detail=self.t("no_files_hint"), tone="neutral")
        self._refresh_all()
        self.page.update()

    def _schedule_scan(self) -> None:
        if self.running:
            return
        roots = [item.path for item in self.selected_inputs.values()]
        self.scanning = True
        self.filter_query = self.filter_field.value or ""
        self.scan_generation = self.service.scan(roots, recursive=bool(self.recursive_switch.value))
        if not roots:
            self.scan_snapshot = ScanSnapshot(roots=(), files=())
        self._set_status("status_scanning", detail="", tone="accent")
        self._refresh_roots()
        self._refresh_file_list()
        self._refresh_selection_summary()
        self._refresh_command_bar()
        self.page.update()

    def _on_filter_change(self, e: Any = None) -> None:
        self.filter_query = self.filter_field.value or ""
        self._refresh_file_list()
        self.page.update()

    def _on_recursive_change(self, e: Any = None) -> None:
        if self.selected_inputs and not self.running:
            self._schedule_scan()

    def _set_mode(self, mode: str) -> None:
        if self.running or mode not in MODE_LABEL_KEYS:
            return
        self.mode = mode
        self._refresh_mode_ui()
        self._refresh_file_list()
        self._refresh_selection_summary()
        self._refresh_command_bar()
        self.page.update()

    def _set_rpgmaker(self, value: str) -> None:
        if self.running or value not in {"MV", "MZ"}:
            return
        self.rpgmaker = value
        self._refresh_mode_ui()
        self.page.update()

    def _toggle_advanced(self, e: Any = None) -> None:
        if self.running:
            return
        self.advanced_open = not self.advanced_open
        self.advanced_panel.visible = self.advanced_open
        self._refresh_advanced_toggle()
        self.page.update()
        self.page.run_task(
            self._scroll_settings_to,
            9999 if self.advanced_open else 0,
        )

    async def _scroll_settings_to(self, offset: int) -> None:
        await asyncio.sleep(0.12)
        try:
            await self.settings_scroll.scroll_to(offset=offset, duration=240)
            self.page.update()
        except Exception:
            return

    def _on_key_change(self, e: Any = None) -> None:
        if self.mode == MODE_RESTORE:
            return
        value = (self.key_field.value or "").strip()
        if value and self.key_feedback.color == th.SUCCESS:
            self.key_feedback.value = self.t("manual_key")
            self.key_feedback.color = th.TEXT_FAINT
        self._refresh_command_bar()
        self.page.update()

    # ------------------------------------------------------------------
    # key detection
    # ------------------------------------------------------------------
    def _run_key_detection(self, paths: Sequence[str | os.PathLike[str]]) -> None:
        if self.running or not paths:
            return
        try:
            header_len = int(self.header_len_field.value or DEFAULT_HEADER_LEN)
        except (TypeError, ValueError):
            header_len = DEFAULT_HEADER_LEN
        self.detect_key_button.disabled = True
        self.pick_key_button.disabled = True
        self.key_feedback.value = self.t("key_detecting")
        self.key_feedback.color = th.BLUE
        self.service.detect_key(paths, header_len=header_len)
        self.page.update()

    async def _detect_key_from_selection(self, e: Any = None) -> None:
        if self.mode == MODE_RESTORE or self.running:
            return
        paths = [item.path for item in self.selected_inputs.values()]
        if not paths:
            await self._pick_key_source()
            return
        self._run_key_detection(paths)

    # ------------------------------------------------------------------
    # job lifecycle
    # ------------------------------------------------------------------
    def _start_job(self, e: Any = None) -> None:
        if self.running or self.scanning:
            return
        if not self.selected_inputs:
            self._set_status_raw(
                self.t("no_files_title"), detail=self.t("no_files_hint"), tone="warning"
            )
            self.page.update()
            return
        usable = sum(1 for item in self.scan_snapshot.files if self._is_usable(item))
        if usable == 0:
            self._set_status(
                "status_no_usable",
                detail=self.t(
                    "nothing_to_process_hint",
                    extensions=", ".join(sorted(self._allowed_extensions())),
                ),
                tone="warning",
            )
            self.page.update()
            return

        options, error = ui_logic.build_options(
            verify_fake_header=self.verify_switch.value,
            header_len=self.header_len_field.value,
            signature=self.signature_field.value,
            version=self.version_field.value,
            remain=self.remain_field.value,
            rpgmaker=self.rpgmaker,
            recursive=bool(self.recursive_switch.value),
        )
        if error or options is None:
            self._set_status_raw(self.t("failed", error=error or "invalid options"), tone="danger")
            self.page.update()
            return

        key: str | None = None
        if self.mode != MODE_RESTORE:
            key, key_error = ui_logic.validate_key(self.key_field.value, options.header_len)
            if key_error or not key:
                self._set_status_raw(
                    self.t("key_format_error") if key_error else self.t("key_needed"),
                    detail=key_error or "",
                    tone="warning",
                )
                self._refresh_command_bar()
                self.page.update()
                return
        request = ui_logic.BatchRequest(
            mode=self.mode,
            inputs=[item.path for item in self.selected_inputs.values()],
            key=key,
            options=options,
            package_zip=bool(self.zip_switch.value),
            version_override=RpgMakerVersion.MZ if self.rpgmaker == "MZ" else RpgMakerVersion.MV,
        )
        self._append_log(
            f"Starting {self.mode} · {usable} usable file(s) · output root {self.output_root}"
        )
        self._last_log_bucket = -1
        self.progress_bar.value = 0
        self.progress_pct.value = "0%"
        self._set_running_ui(True)
        if not self.service.start_job(request, output_root=self.output_root):
            self._set_running_ui(False)
            self._set_status_raw("A batch is already running", tone="danger")
            self.page.update()
            return
        self._set_status("status_running", detail="", tone="accent", done=0, total=usable)
        self.page.update()

    def _cancel_job(self, e: Any = None) -> None:
        if not self.running or self.cancel_requested:
            return
        self.cancel_requested = True
        self.cancel_button.disabled = True
        self._set_status("status_cancelling", detail="", tone="warning")
        self._append_log("Cancel requested")
        self.service.cancel_job()
        self.page.update()

    def _set_running_ui(self, running: bool) -> None:
        self.running = running
        self.start_button.disabled = running
        self.cancel_button.visible = running
        self.cancel_button.disabled = False
        self.add_files_button.disabled = running
        self.add_folder_button.disabled = running
        self.clear_inputs_button.disabled = running or not bool(self.selected_inputs)
        self.change_output_button.disabled = running
        self.open_output_button.disabled = running
        self.detect_key_button.disabled = running or self.mode == MODE_RESTORE
        self.pick_key_button.disabled = running or self.mode == MODE_RESTORE
        self.key_field.disabled = running or self.mode == MODE_RESTORE
        self._refresh_mode_ui()
        self._refresh_command_bar()

    def _valid_run_directory(self, result: ui_logic.RunResult | None = None) -> Path | None:
        candidate = (
            result.run_directory
            if result is not None
            else (self.last_result.run_directory if self.last_result is not None else None)
        )
        if candidate is None:
            return None
        if str(candidate) in {"", "."}:
            return None
        try:
            return candidate if candidate.exists() and candidate.is_dir() else None
        except OSError:
            return None

    def _handle_job_finished(self, result: ui_logic.RunResult) -> None:
        self.last_result = result
        self.running = False
        self.cancel_requested = False
        self._set_running_ui(False)
        rr = result.result
        success = len(rr.succeeded)
        skipped = len(rr.skipped)
        failed = len(rr.failed)
        log_line = self.t(
            "finished_ok" if not failed else "finished_with_errors",
            ok=success,
            skipped=skipped,
            failed=failed,
        )
        self._append_log(log_line)
        if result.cancelled:
            self._set_status(
                "status_cancelled", detail=str(result.run_directory or ""), tone="warning"
            )
        elif result.error:
            self._set_status_raw(self.t("failed", error=result.error), tone="danger")
        elif result.nothing_to_do:
            detail = (
                self.t("all_already_done")
                if rr.skipped
                else self.t(
                    "nothing_to_process_hint",
                    extensions=", ".join(sorted(self._allowed_extensions())),
                )
            )
            self._set_status("nothing_to_do", detail=detail, tone="warning")
        elif failed:
            self._set_status(
                "finished_with_errors",
                detail=self.t("exported_to", path=str(result.run_directory)),
                tone="warning",
                ok=success,
                skipped=skipped,
                failed=failed,
            )
            self.progress_bar.value = 1
        else:
            self._set_status(
                "finished_ok",
                detail=self.t("exported_to", path=str(result.run_directory)),
                tone="success",
                ok=success,
                skipped=skipped,
                failed=failed,
            )
            self.progress_bar.value = 1
            self.progress_pct.value = "100%"
        self.report_button.visible = bool(rr.outcomes)
        run_dir = self._valid_run_directory(result)
        self.open_results_button.visible = run_dir is not None
        self._refresh_command_bar()
        self.page.update()

    def _handle_job_failed(self, error: str, trace: str = "") -> None:
        self.running = False
        self.cancel_requested = False
        self._set_running_ui(False)
        self._append_log(f"ERROR {error}")
        if trace:
            self._append_log(trace.strip().splitlines()[-1])
        self._set_status_raw(self.t("failed", error=error), tone="danger")
        self.page.update()

    def _refresh_command_bar(self) -> None:
        usable = sum(1 for item in self.scan_snapshot.files if self._is_usable(item))
        if not self.running:
            self.start_button.disabled = self.scanning or usable == 0 or not self.selected_inputs
        else:
            self.start_button.disabled = True
        self.cancel_button.visible = self.running
        self.report_button.visible = self.last_result is not None and not self.running
        self.open_results_button.visible = bool(
            self._valid_run_directory(self.last_result) is not None and not self.running
        )
        self.clear_inputs_button.disabled = self.running or not bool(self.selected_inputs)

    def _allowed_extensions(self) -> frozenset[str]:
        if self.mode == MODE_ENCRYPT:
            return ENCRYPT_EXTENSIONS
        if self.mode == MODE_RESTORE:
            return frozenset({"rpgmvp", "png_"})
        return DECRYPT_EXTENSIONS

    def _is_usable(self, item: ScannedFile) -> bool:
        return item.extension in self._allowed_extensions()

    # ------------------------------------------------------------------
    # event pump
    # ------------------------------------------------------------------
    async def _pump_events(self) -> None:
        while not self._shutdown:
            events = self.service.drain_events()
            if events:
                for event in events:
                    if self._shutdown:
                        break
                    try:
                        self._handle_event(event)
                    except Exception as error:  # pragma: no cover - last resort
                        self._append_log(f"UI event error: {type(error).__name__}: {error}")
                        traceback.print_exc()
                try:
                    self.page.update()
                except Exception:
                    break
            await asyncio.sleep(0.06)

    def _handle_event(self, event: dict[str, Any]) -> None:
        kind = event.get("type")
        if kind == "scan_started":
            return
        if kind == "scan_finished":
            if event.get("generation") != self.scan_generation:
                return
            self.scanning = False
            self.scan_snapshot = event["snapshot"]
            self._refresh_roots()
            self._refresh_file_list()
            self._refresh_selection_summary()
            self._refresh_command_bar()
            usable = sum(1 for item in self.scan_snapshot.files if self._is_usable(item))
            self._append_log(
                f"Scanned {len(self.scan_snapshot.files)} file(s); {usable} usable for {self.mode}"
            )
            if usable:
                self._set_status(
                    "status_ready",
                    detail=self.t("files_found", count=len(self.scan_snapshot.files)),
                    tone="neutral",
                )
            elif self.scan_snapshot.files:
                self._set_status(
                    "status_no_usable",
                    detail=self.t(
                        "nothing_to_process_hint",
                        extensions=", ".join(sorted(self._allowed_extensions())),
                    ),
                    tone="warning",
                )
            else:
                self._set_status("nothing_to_do", detail=self.t("no_files_hint"), tone="warning")
            return
        if kind == "scan_failed":
            if event.get("generation") != self.scan_generation:
                return
            self.scanning = False
            self.scan_snapshot = ScanSnapshot(roots=(), files=())
            self._refresh_file_list()
            self._refresh_selection_summary()
            self._refresh_command_bar()
            self._set_status_raw(self.t("failed", error=event.get("error", "")), tone="danger")
            self._append_log(f"Scan failed: {event.get('error', '')}")
            return
        if kind == "key_detection_started":
            return
        if kind == "key_detected":
            key = event.get("key") or ""
            self.key_field.value = key
            source = Path(str(event.get("source") or "")).name
            strategy = event.get("strategy") or ""
            extra = self.t("detected_from", source=source) if source else ""
            if strategy:
                extra = (extra + " · " if extra else "") + self.t(
                    "detected_strategy", strategy=strategy
                )
            self.key_feedback.value = self.t("key_detected") + (f" · {extra}" if extra else "")
            self.key_feedback.color = th.SUCCESS
            self.detect_key_button.disabled = self.mode == MODE_RESTORE
            self.pick_key_button.disabled = self.mode == MODE_RESTORE
            self._append_log(f"Key detected from {source or 'selection'}")
            self._refresh_command_bar()
            return
        if kind == "key_not_found":
            self.key_feedback.value = self.t("detection_failed")
            self.key_feedback.color = th.WARNING
            self.detect_key_button.disabled = self.mode == MODE_RESTORE
            self.pick_key_button.disabled = self.mode == MODE_RESTORE
            self._append_log("Key detection did not find a key")
            return
        if kind == "job_started":
            self._append_log("Worker started")
            return
        if kind == "progress_start":
            total = int(event.get("total") or 0)
            self.progress_bar.value = 0
            self.progress_pct.value = "0%"
            self._set_status("status_running", detail="", tone="accent", done=0, total=total)
            return
        if kind == "progress":
            done = int(event.get("done") or 0)
            total = int(event.get("total") or 0)
            name = str(event.get("name") or "")
            fraction = (done / total) if total else 0
            self.progress_bar.value = min(1.0, max(0.0, fraction))
            self.progress_pct.value = f"{fraction * 100:.0f}%"
            self._set_status("status_running", detail=name, tone="accent", done=done, total=total)
            bucket = int(fraction * 10)
            if bucket != self._last_log_bucket:
                self._last_log_bucket = bucket
                self._append_log(f"Progress {done}/{total} · {name}")
            return
        if kind == "progress_finish":
            return
        if kind == "cancel_requested":
            return
        if kind == "job_finished":
            self._handle_job_finished(event["result"])
            return
        if kind == "job_failed":
            self._handle_job_failed(event.get("error", "unknown error"), event.get("traceback", ""))
            return
        if kind == "job_rejected":
            self._set_running_ui(False)
            self._set_status_raw(self.t("failed", error=event.get("error", "")), tone="danger")
            return

    # ------------------------------------------------------------------
    # status / log
    # ------------------------------------------------------------------
    def _set_status(
        self,
        key: str,
        *,
        detail: str = "",
        tone: str = "neutral",
        **values: Any,
    ) -> None:
        self._status = StatusMessage(key=key, values=dict(values), detail=detail, tone=tone)
        self._refresh_status_from_state()

    def _set_status_raw(self, text: str, *, detail: str = "", tone: str = "danger") -> None:
        self._status = StatusMessage(key=None, values={}, raw=text, detail=detail, tone=tone)
        self._refresh_status_from_state()

    def _refresh_status_from_state(self) -> None:
        status = self._status
        if status.key:
            self.status_title.value = self.t(status.key, **status.values)
        else:
            self.status_title.value = status.raw
        self.status_detail.value = status.detail
        tone_map = {
            "accent": (th.ACCENT, 0.10, 0.18),
            "success": (th.SUCCESS, 0.10, 0.18),
            "warning": (th.WARNING, 0.10, 0.18),
            "danger": (th.DANGER, 0.10, 0.18),
            "neutral": (th.TEXT_SECONDARY, 0.07, 0.12),
        }
        colour, bg, border = tone_map.get(status.tone, tone_map["neutral"])
        self.status_icon.color = colour
        self.status_icon_bg.bgcolor = ft.Colors.with_opacity(bg, colour)
        self.status_icon_bg.border = ft.Border.all(1, ft.Colors.with_opacity(border, colour))
        self.status_icon.icon = {
            "success": ft.Icons.CHECK_CIRCLE_ROUNDED,
            "warning": ft.Icons.INFO_OUTLINE_ROUNDED,
            "danger": ft.Icons.ERROR_OUTLINE_ROUNDED,
        }.get(status.tone, ft.Icons.BOLT_ROUNDED)

    def _append_log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{stamp}] {message}")

    # ------------------------------------------------------------------
    # dialogs
    # ------------------------------------------------------------------
    async def _open_results(self, e: Any = None) -> None:
        run_dir = self._valid_run_directory(self.last_result)
        if run_dir is not None:
            self._open_path(run_dir)

    async def _open_output_root(self, e: Any = None) -> None:
        self._open_path(self.output_root)

    def _open_path(self, path: Path) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
        except OSError as error:
            self._append_log(f"Could not open {path}: {error}")

    async def _open_log(self, e: Any = None) -> None:
        lines = list(self.logs) or [self.t("log_empty")]
        log_text = ft.Text(
            "\n".join(lines),
            selectable=True,
            size=10,
            color=th.TEXT_SECONDARY,
            font_family="Consolas",
        )
        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=th.BG_MID,
            shape=th.rounded(22),
            title=ft.Text(
                self.t("log_title"), size=16, color=th.TEXT_PRIMARY, weight=ft.FontWeight.W_600
            ),
            content=ft.Container(
                width=760,
                height=400,
                padding=16,
                border_radius=16,
                bgcolor=th.black(0.18),
                border=ft.Border.all(1, th.white(0.07)),
                content=ft.ListView([log_text], expand=True, auto_scroll=True),
            ),
            actions=[
                ft.TextButton(
                    self.t("close"),
                    on_click=lambda e: self.page.pop_dialog(),
                    style=ft.ButtonStyle(color=th.ACCENT),
                )
            ],
        )
        self.page.show_dialog(dialog)
        self.page.update()

    async def _show_report(self, e: Any = None) -> None:
        result = self.last_result
        if not result:
            return
        rr = result.result
        outcomes = list(rr.outcomes)
        if result.cancelled:
            summary_text = self.t("status_cancelled")
        elif rr.failed or result.error:
            summary_text = self.t(
                "finished_with_errors",
                ok=len(rr.succeeded),
                skipped=len(rr.skipped),
                failed=len(rr.failed),
            )
        else:
            summary_text = self.t(
                "finished_ok", ok=len(rr.succeeded), skipped=len(rr.skipped), failed=len(rr.failed)
            )
        summary = ft.Text(summary_text, size=11, color=th.TEXT_SECONDARY)
        run_dir = self._valid_run_directory(result)
        output_text = str(run_dir) if run_dir is not None else ""
        archive_text = (
            str(result.archive) if result.archive is not None and result.archive.exists() else ""
        )
        preview_title = ft.Text(
            self.t("preview"), size=12, color=th.TEXT_PRIMARY, weight=ft.FontWeight.W_600
        )
        preview_body = ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            border_radius=16,
            bgcolor=th.black(0.20),
            border=ft.Border.all(1, th.white(0.06)),
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.IMAGE_ROUNDED, size=38, color=th.white(0.18)),
                    ft.Text(
                        self.t("preview_hint"),
                        size=10,
                        color=th.TEXT_FAINT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        )

        def show_preview(outcome: Any) -> None:
            destination = getattr(outcome, "destination", None)
            preview_title.value = (
                Path(destination).name if destination else getattr(outcome, "output_name", "")
            )
            preview_body.content = self._preview_content(
                destination, getattr(outcome, "error", None)
            )
            self.page.update()

        rows: list[ft.Control] = []
        for outcome in outcomes:
            destination = getattr(outcome, "destination", None)
            error = getattr(outcome, "error", None)
            skipped = getattr(outcome, "skipped", False)
            if error:
                colour, icon = th.DANGER, ft.Icons.ERROR_OUTLINE_ROUNDED
            elif skipped:
                colour, icon = th.WARNING, ft.Icons.SKIP_NEXT_ROUNDED
            else:
                colour, icon = th.SUCCESS, ft.Icons.CHECK_CIRCLE_ROUNDED
            size_text = ui_logic.format_size(getattr(outcome, "size", 0))
            row = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(icon, size=15, color=colour),
                        ft.Column(
                            [
                                ft.Text(
                                    Path(destination).name if destination else outcome.output_name,
                                    size=10,
                                    color=th.TEXT_PRIMARY,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    error or size_text,
                                    size=8,
                                    color=colour if error else th.TEXT_FAINT,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                            spacing=1,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                ),
                padding=ft.Padding.symmetric(horizontal=9, vertical=7),
                border_radius=10,
                bgcolor=th.white(0.025),
                on_click=lambda e, o=outcome: show_preview(o),
            )
            rows.append(row)
        if not rows:
            rows.append(ft.Text(self.t("report_empty"), size=10, color=th.TEXT_FAINT))
        details = ft.ListView(rows, expand=True, spacing=4, padding=0)
        report = ft.Row(
            [
                ft.Column(
                    [
                        summary,
                        ft.Text(
                            output_text or self.t("report_empty"),
                            size=9,
                            color=th.TEXT_FAINT,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            archive_text,
                            size=9,
                            color=th.TEXT_FAINT,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        )
                        if archive_text
                        else ft.Container(height=0),
                        th.divider_line(opacity=0.06, margin=2),
                        details,
                    ],
                    spacing=8,
                    expand=True,
                ),
                ft.Container(width=12),
                ft.Column(
                    [preview_title, preview_body],
                    spacing=8,
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        )
        actions: list[ft.Control] = []
        if run_dir is not None:
            actions.append(
                ft.TextButton(
                    self.t("open_results"),
                    on_click=lambda e, p=run_dir: self._open_path(p),
                    style=ft.ButtonStyle(color=th.ACCENT),
                )
            )
        actions.append(
            ft.TextButton(
                self.t("close"),
                on_click=lambda e: self.page.pop_dialog(),
                style=ft.ButtonStyle(color=th.TEXT_SECONDARY),
            )
        )
        # Make the report immediately useful: preselect the first image result
        # so the preview pane is populated rather than empty on every open.
        first_preview = next(
            (
                item
                for item in outcomes
                if getattr(item, "ok", False)
                and getattr(item, "destination", None)
                and Path(item.destination).suffix.lower()
                in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
            ),
            None,
        )
        if first_preview is not None:
            show_preview(first_preview)

        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=th.BG_MID,
            shape=th.rounded(24),
            title=ft.Text(
                self.t("report_title"), size=16, color=th.TEXT_PRIMARY, weight=ft.FontWeight.W_600
            ),
            content=ft.Container(
                width=860,
                height=460,
                padding=16,
                border_radius=18,
                bgcolor=th.black(0.12),
                border=ft.Border.all(1, th.white(0.06)),
                content=report,
            ),
            actions=actions,
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dialog)
        self.page.update()

    def _preview_content(self, path: Any, error: Any = None) -> ft.Control:
        if error:
            return ft.Text(str(error), size=10, color=th.DANGER, text_align=ft.TextAlign.CENTER)
        if not path:
            return ft.Text(self.t("preview_unavailable"), size=10, color=th.TEXT_FAINT)
        target = Path(path)
        if not target.exists():
            return ft.Text(self.t("preview_unavailable"), size=10, color=th.TEXT_FAINT)
        if target.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
            return ft.Column(
                [
                    ft.Icon(ft.Icons.INSERT_DRIVE_FILE_ROUNDED, size=38, color=th.white(0.18)),
                    ft.Text(
                        self.t("preview_unavailable"),
                        size=10,
                        color=th.TEXT_FAINT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            )
        try:
            if target.stat().st_size > PREVIEW_LIMIT_BYTES:
                return ft.Text(
                    self.t("preview_too_large"),
                    size=10,
                    color=th.TEXT_FAINT,
                    text_align=ft.TextAlign.CENTER,
                )
            data = target.read_bytes()
            return ft.Image(src=data, fit=ft.BoxFit.CONTAIN, expand=True, border_radius=12)
        except OSError as read_error:
            return ft.Text(
                str(read_error), size=10, color=th.DANGER, text_align=ft.TextAlign.CENTER
            )

    # ------------------------------------------------------------------
    # aggregate refresh
    # ------------------------------------------------------------------
    def _refresh_all(self) -> None:
        self._refresh_language_buttons()
        self._refresh_mode_ui()
        self._refresh_roots()
        self._refresh_file_list()
        self._refresh_selection_summary()
        self._refresh_advanced_toggle()
        self._refresh_status_from_state()
        self._refresh_command_bar()


def app(page: ft.Page) -> None:
    GlassDecrypterApp(page)


def run() -> None:
    ft.run(app, assets_dir=str(APP_DIR / "assets"))


if __name__ == "__main__":
    run()
