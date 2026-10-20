"""Chinese and English strings for the Flet desktop interface."""

from __future__ import annotations

from typing import Any

DEFAULT_LANGUAGE = "zh"
LANGUAGES: dict[str, str] = {"zh": "中文", "en": "English"}

TEXT: dict[str, dict[str, str]] = {
    "add_files": {
        "zh": "添加文件…",
        "en": "Add files…",
    },
    "add_folder": {
        "zh": "添加文件夹…",
        "en": "Add folder…",
    },
    "add_sources_title": {
        "zh": "添加文件或文件夹",
        "en": "Add files or folders",
    },
    "advanced_hide": {
        "zh": "收起高级设置",
        "en": "Hide advanced settings",
    },
    "advanced_hint": {
        "zh": "一般保持默认即可；特殊伪头游戏才需要调整。",
        "en": "Defaults are almost always right; change these only for custom headers.",
    },
    "advanced_show": {
        "zh": "高级设置",
        "en": "Advanced settings",
    },
    "all_already_done": {
        "zh": "选中的文件都已转换过，无需重复处理",
        "en": "Every selected file was already converted",
    },
    "app_subtitle": {
        "zh": "解密、重新加密与修复 RPG Maker MV / MZ 资源文件",
        "en": "Decrypt, re-encrypt and repair RPG Maker MV / MZ resources",
    },
    "app_title": {
        "zh": "RPG Maker MV / MZ 解密工具",
        "en": "RPG Maker MV/MZ Decrypter",
    },
    "browse_key_file": {
        "zh": "选择文件…",
        "en": "Choose file…",
    },
    "cancel_run": {
        "zh": "取消任务",
        "en": "Cancel",
    },
    "change_output": {
        "zh": "更改…",
        "en": "Change…",
    },
    "choose_folder": {
        "zh": "选择文件夹",
        "en": "Choose a folder",
    },
    "choose_inputs": {
        "zh": "选择要处理的文件",
        "en": "Choose files to process",
    },
    "choose_key_file": {
        "zh": "选择用于识别密钥的文件",
        "en": "Choose a file to detect the key from",
    },
    "choose_output": {
        "zh": "选择导出根目录",
        "en": "Choose the export root",
    },
    "clear_all": {
        "zh": "清空输入",
        "en": "Clear inputs",
    },
    "close": {
        "zh": "关闭",
        "en": "Close",
    },
    "close_window": {
        "zh": "关闭窗口",
        "en": "Close window",
    },
    "detect_from_selection": {
        "zh": "从所选内容识别",
        "en": "Detect from selection",
    },
    "detected_from": {
        "zh": "来源：{source}",
        "en": "Source: {source}",
    },
    "detected_strategy": {
        "zh": "策略：{strategy}",
        "en": "Method: {strategy}",
    },
    "detection_failed": {
        "zh": "没有从所选内容中识别到密钥。",
        "en": "No key could be detected from the selection.",
    },
    "done": {
        "zh": "完成",
        "en": "Done",
    },
    "exported_to": {
        "zh": "已导出到 {path}",
        "en": "Exported to {path}",
    },
    "failed": {
        "zh": "失败：{error}",
        "en": "Failed: {error}",
    },
    "files_found": {
        "zh": "已发现 {count} 个文件",
        "en": "{count} files found",
    },
    "files_showing": {
        "zh": "显示前 {shown} 个（共 {total} 个）",
        "en": "Showing first {shown} of {total}",
    },
    "files_usable": {
        "zh": "{count} 个适用于当前操作",
        "en": "{count} usable for this operation",
    },
    "finished_ok": {
        "zh": "完成：{ok} 个成功，{skipped} 个跳过，{failed} 个失败",
        "en": "Done: {ok} succeeded, {skipped} skipped, {failed} failed",
    },
    "finished_with_errors": {
        "zh": "完成（有失败项）：{ok} 个成功，{skipped} 个跳过，{failed} 个失败",
        "en": "Finished with failures: {ok} succeeded, {skipped} skipped, {failed} failed",
    },
    "header_len": {
        "zh": "头长度",
        "en": "Header length",
    },
    "idle": {
        "zh": "就绪",
        "en": "Ready",
    },
    "input_helper": {
        "zh": "添加游戏目录、资源文件夹，或直接选择要处理的文件。",
        "en": "Add a game folder, a resource folder, or individual files.",
    },
    "input_section": {
        "zh": "输入资源",
        "en": "Source files",
    },
    "key_detected": {
        "zh": "已识别到密钥",
        "en": "Key detected",
    },
    "key_detecting": {
        "zh": "正在寻找密钥…",
        "en": "Looking for the key…",
    },
    "key_format_error": {
        "zh": "密钥格式不正确。",
        "en": "The key format is invalid.",
    },
    "key_hint": {
        "zh": "加解密必填；还原图片不需要密钥。",
        "en": "Required for en-/decrypt; restoring images needs no key.",
    },
    "key_needed": {
        "zh": "请输入密钥，或先使用自动识别。",
        "en": "Enter a key, or detect one automatically.",
    },
    "key_not_found": {
        "zh": "没有找到密钥",
        "en": "No key found",
    },
    "key_optional": {
        "zh": "还原图片时不需要密钥",
        "en": "Not needed when restoring images",
    },
    "key_placeholder": {
        "zh": "例如 1234567890abcdef1234567890abcdef",
        "en": "e.g. 1234567890abcdef1234567890abcdef",
    },
    "key_section": {
        "zh": "加密密钥",
        "en": "Encryption key",
    },
    "lang_en": {
        "zh": "EN",
        "en": "EN",
    },
    "lang_zh": {
        "zh": "中",
        "en": "中",
    },
    "log_empty": {
        "zh": "还没有运行记录。",
        "en": "No run activity yet.",
    },
    "log_title": {
        "zh": "运行日志",
        "en": "Run log",
    },
    "manual_key": {
        "zh": "手动输入",
        "en": "Manual entry",
    },
    "maximize": {
        "zh": "最大化",
        "en": "Maximise",
    },
    "minimize": {
        "zh": "最小化",
        "en": "Minimize",
    },
    "mode_encrypt": {
        "zh": "加密",
        "en": "Encrypt",
    },
    "mode_hint_decrypt": {
        "zh": "把加密资源还原成 .png / .ogg / .m4a",
        "en": "Turn encrypted resources back into .png / .ogg / .m4a",
    },
    "mode_hint_encrypt": {
        "zh": "把改好的 .png / .ogg / .m4a 加密回游戏格式",
        "en": "Encrypt edited .png / .ogg / .m4a back into game format",
    },
    "mode_hint_restore": {
        "zh": "不需要密钥，直接修复加密图片的 PNG 头",
        "en": "Repair encrypted images' PNG headers without a key",
    },
    "mode_section": {
        "zh": "操作方式",
        "en": "Operation",
    },
    "no_files_hint": {
        "zh": "从文件或文件夹开始，所有处理都会输出到独立的时间戳目录。",
        "en": "Start with files or a folder. Every run gets its own timestamped output folder.",
    },
    "no_files_title": {
        "zh": "还没有添加文件",
        "en": "No files added yet",
    },
    "not_supported": {
        "zh": "当前操作不适用",
        "en": "Not usable for this operation",
    },
    "nothing_to_do": {
        "zh": "没有可处理的文件",
        "en": "Nothing to process",
    },
    "nothing_to_process_hint": {
        "zh": "选中的文件里没有本操作支持的扩展名（需要 {extensions}）",
        "en": "None of the selected files has an extension this operation handles (needs {extensions})",
    },
    "open_output_root": {
        "zh": "打开导出根目录",
        "en": "Open export root",
    },
    "open_results": {
        "zh": "打开输出文件夹",
        "en": "Open output folder",
    },
    "output_hint": {
        "zh": "每次运行会在这里新建一个时间戳文件夹，不会覆盖已有文件。",
        "en": "Each run creates a new timestamped folder here; nothing is overwritten.",
    },
    "output_is_input_warning": {
        "zh": "你选择的是导出目录（{path}）。如果没有结果，试试选择游戏目录里的资源文件。",
        "en": "You selected an export folder ({path}). If nothing happens, pick the game's resource files instead.",
    },
    "output_section": {
        "zh": "输出位置",
        "en": "Output location",
    },
    "package_zip": {
        "zh": "额外打包成 ZIP",
        "en": "Also create a ZIP",
    },
    "package_zip_hint": {
        "zh": "可选，默认只导出文件夹。",
        "en": "Optional; the folder alone is usually easier to browse.",
    },
    "preview": {
        "zh": "预览",
        "en": "Preview",
    },
    "preview_hint": {
        "zh": "选择一个图片结果查看预览。",
        "en": "Select an image result to preview it.",
    },
    "preview_too_large": {
        "zh": "文件较大，不在窗口内预览。",
        "en": "File is too large to preview here.",
    },
    "preview_unavailable": {
        "zh": "这个文件类型不支持预览。",
        "en": "No preview for this file type.",
    },
    "privacy_note": {
        "zh": "本地处理 · 不上传文件",
        "en": "Local only · Nothing uploaded",
    },
    "recursive": {
        "zh": "递归处理子文件夹",
        "en": "Include sub-folders",
    },
    "remain": {
        "zh": "Remain",
        "en": "Remain",
    },
    "remove": {
        "zh": "移除",
        "en": "Remove",
    },
    "report_empty": {
        "zh": "当前还没有结果。",
        "en": "There are no results yet.",
    },
    "report_title": {
        "zh": "处理结果",
        "en": "Run report",
    },
    "restore_window": {
        "zh": "还原",
        "en": "Restore",
    },
    "rpgmaker_mv": {
        "zh": "MV（.rpgmvp / .rpgmvo）",
        "en": "MV (.rpgmvp / .rpgmvo)",
    },
    "rpgmaker_mz": {
        "zh": "MZ（.png_ / .ogg_）",
        "en": "MZ (.png_ / .ogg_)",
    },
    "run_decrypt": {
        "zh": "解密",
        "en": "Decrypt",
    },
    "run_restore": {
        "zh": "还原 PNG 头",
        "en": "Restore PNG headers",
    },
    "search_files": {
        "zh": "筛选文件…",
        "en": "Filter files…",
    },
    "show_log": {
        "zh": "运行日志",
        "en": "Run log",
    },
    "signature": {
        "zh": "Signature",
        "en": "Signature",
    },
    "start_run": {
        "zh": "开始处理",
        "en": "Start",
    },
    "status_cancelled": {
        "zh": "任务已取消",
        "en": "Run cancelled",
    },
    "status_cancelling": {
        "zh": "正在取消…",
        "en": "Cancelling…",
    },
    "status_failed": {
        "zh": "运行失败",
        "en": "Run failed",
    },
    "status_no_usable": {
        "zh": "没有适用于当前操作的文件",
        "en": "No files are usable for this operation",
    },
    "status_ok": {
        "zh": "成功",
        "en": "OK",
    },
    "status_ready": {
        "zh": "准备就绪",
        "en": "Ready",
    },
    "status_running": {
        "zh": "正在处理 · {done}/{total}",
        "en": "Processing · {done}/{total}",
    },
    "status_scanning": {
        "zh": "正在扫描所选内容…",
        "en": "Scanning selection…",
    },
    "status_skipped": {
        "zh": "跳过",
        "en": "Skipped",
    },
    "target_rpgmaker": {
        "zh": "目标引擎",
        "en": "Target engine",
    },
    "verify_header": {
        "zh": "校验伪头",
        "en": "Verify fake header",
    },
    "verify_header_hint": {
        "zh": "文件头不匹配时取消勾选。",
        "en": "Untick if the header does not match.",
    },
    "version_field": {
        "zh": "Version",
        "en": "Version",
    },
    "view_report": {
        "zh": "查看报告",
        "en": "View report",
    },
}


def tr(key: str, lang: str = DEFAULT_LANGUAGE, **values: Any) -> str:
    """Return a localized string, falling back to Chinese when necessary."""

    entry = TEXT.get(key)
    if entry is None:
        return key
    template = entry.get(lang) or entry.get(DEFAULT_LANGUAGE) or key
    try:
        return template.format(**values) if values else template
    except (KeyError, IndexError, ValueError):
        return template


class Translator:
    """Small observable catalogue used by the Flet view."""

    def __init__(self, language: str = DEFAULT_LANGUAGE) -> None:
        self.language = language if language in LANGUAGES else DEFAULT_LANGUAGE
        self._bindings: list[tuple[Any, str, str]] = []

    def __call__(self, key: str, **values: Any) -> str:
        return tr(key, self.language, **values)

    def bind(self, control: Any, key: str, *, attr: str = "value") -> Any:
        setattr(control, attr, self(key))
        self._bindings.append((control, attr, key))
        return control

    def set_language(self, language: str) -> None:
        if language not in LANGUAGES or language == self.language:
            return
        self.language = language
        for control, attr, key in list(self._bindings):
            setattr(control, attr, self(key))


__all__ = ["DEFAULT_LANGUAGE", "LANGUAGES", "TEXT", "Translator", "tr"]
