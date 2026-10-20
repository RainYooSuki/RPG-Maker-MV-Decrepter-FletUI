"""Visual tokens and reusable liquid-glass building blocks for the Flet UI."""

from __future__ import annotations

from typing import Any

import flet as ft

# ---------------------------------------------------------------------------
# palette
# ---------------------------------------------------------------------------
BG_DEEP = "#050914"
BG_TOP = "#081526"
BG_MID = "#0C1D31"
BG_WARM = "#24132F"
FONT_UI = "Noto Sans SC"
TEXT_PRIMARY = "#F4F8FF"
TEXT_SECONDARY = "#C7D4EA"
TEXT_MUTED = "#9BACBF"
TEXT_FAINT = "#71829A"
ACCENT = "#66E7D5"
ACCENT_STRONG = "#29C9BB"
ACCENT_SOFT = "#A9FFF4"
MINT = "#8FF5CD"
BLUE = "#82AFFF"
VIOLET = "#C29CFF"
WARNING = "#FFD479"
DANGER = "#FF7D8D"
SUCCESS = "#79F2B2"

GLASS_TINT = 0.065
GLASS_TINT_STRONG = 0.11
GLASS_EDGE = 0.22
GLASS_EDGE_SOFT = 0.11

RADIUS_XL = 30
RADIUS_LG = 22
RADIUS_MD = 16
RADIUS_SM = 12


def white(opacity: float) -> str:
    return ft.Colors.with_opacity(opacity, ft.Colors.WHITE)


def black(opacity: float) -> str:
    return ft.Colors.with_opacity(opacity, ft.Colors.BLACK)


def accent(opacity: float) -> str:
    return ft.Colors.with_opacity(opacity, ACCENT)


def rounded(radius: int | float) -> ft.RoundedRectangleBorder:
    return ft.RoundedRectangleBorder(radius=radius)


def soft_shadow(
    *,
    blur: int = 42,
    y: int = 18,
    opacity: float = 0.30,
    spread: int = -8,
) -> ft.BoxShadow:
    return ft.BoxShadow(
        blur_radius=blur,
        spread_radius=spread,
        color=black(opacity),
        offset=ft.Offset(0, y),
    )


def glow_shadow(*, blur: int = 28, opacity: float = 0.28) -> ft.BoxShadow:
    return ft.BoxShadow(
        blur_radius=blur,
        spread_radius=-4,
        color=accent(opacity),
        offset=ft.Offset(0, 8),
    )


def gradient_rim(radius: int = RADIUS_XL, *, strength: float = 1.0) -> ft.LinearGradient:
    return ft.LinearGradient(
        begin=ft.Alignment.TOP_LEFT,
        end=ft.Alignment.BOTTOM_RIGHT,
        colors=[
            white(0.34 * strength),
            white(0.10 * strength),
            white(0.035 * strength),
            accent(0.16 * strength),
        ],
        stops=[0.0, 0.38, 0.72, 1.0],
    )


def panel_gradient() -> ft.LinearGradient:
    """A mostly opaque, low-chroma glass surface.

    The earlier version let the colourful aurora through every panel, which
    made long labels and file paths compete with the background.  Keeping the
    panel itself dark and letting only the rim/shadow reveal the backdrop keeps
    the liquid-glass feel without compromising legibility.
    """

    return ft.LinearGradient(
        begin=ft.Alignment.TOP_LEFT,
        end=ft.Alignment.BOTTOM_RIGHT,
        colors=[
            ft.Colors.with_opacity(0.90, "#111D2D"),
            ft.Colors.with_opacity(0.86, "#0C1624"),
            ft.Colors.with_opacity(0.84, "#111526"),
        ],
        stops=[0.0, 0.52, 1.0],
    )


# ---------------------------------------------------------------------------
# surfaces
# ---------------------------------------------------------------------------
def glass_panel(
    content: ft.Control,
    *,
    radius: int = RADIUS_XL,
    padding: int | ft.Padding = 22,
    tint: float = GLASS_TINT,
    edge: float = GLASS_EDGE,
    shadow: bool = True,
    expand: bool | int = False,
    height: int | float | None = None,
) -> ft.Container:
    """A layered translucent panel with a fine gradient rim.

    Flet does not expose Flutter's ``BackdropFilter``.  The visual result here
    is built from a translucent tinted surface, a one-pixel gradient rim and
    soft shadows over the aurora background below the window.  It is deliberately
    restrained so it remains readable and cheap to animate.
    """

    inner = ft.Container(
        content=content,
        padding=padding,
        border_radius=max(0, radius - 1),
        bgcolor=ft.Colors.with_opacity(tint, "#EAF3FF"),
        gradient=panel_gradient() if tint <= 0.08 else None,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        expand=expand if isinstance(expand, bool) else False,
    )
    return ft.Container(
        content=inner,
        padding=1,
        border_radius=radius,
        gradient=gradient_rim(radius),
        border=ft.Border.all(1, ft.Colors.with_opacity(edge, ft.Colors.WHITE)),
        shadow=soft_shadow() if shadow else None,
        expand=expand,
        height=height,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )


def surface(
    content: ft.Control,
    *,
    radius: int = RADIUS_MD,
    padding: int | ft.Padding = 14,
    fill: float = 0.055,
    border: float = 0.09,
) -> ft.Container:
    """Small inset surface used for fields and list rows."""

    return ft.Container(
        content=content,
        padding=padding,
        border_radius=radius,
        bgcolor=ft.Colors.with_opacity(fill, ft.Colors.WHITE),
        border=ft.Border.all(1, ft.Colors.with_opacity(border, ft.Colors.WHITE)),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )


def aurora_background() -> ft.Control:
    """A soft, multi-layer backdrop painted entirely with Flet layers."""

    def orb(
        size: int,
        colour: str,
        opacity: float,
        *,
        left: int | None = None,
        right: int | None = None,
        top: int | None = None,
        bottom: int | None = None,
    ) -> ft.Container:
        return ft.Container(
            width=size,
            height=size,
            left=left,
            right=right,
            top=top,
            bottom=bottom,
            border_radius=size / 2,
            opacity=opacity,
            gradient=ft.RadialGradient(
                colors=[
                    ft.Colors.with_opacity(0.50, colour),
                    ft.Colors.with_opacity(0.20, colour),
                    ft.Colors.with_opacity(0.055, colour),
                    ft.Colors.with_opacity(0.0, colour),
                ],
                stops=[0.0, 0.40, 0.72, 1.0],
            ),
        )

    base = ft.Container(
        expand=True,
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[BG_TOP, BG_MID, BG_WARM],
            stops=[0.0, 0.54, 1.0],
        ),
    )
    blobs = [
        orb(760, "#3ADBCB", 0.34, left=-300, top=-390),
        orb(760, "#607CFF", 0.30, right=-380, top=-190),
        orb(860, "#C66CFF", 0.24, left=230, bottom=-570),
        orb(420, "#DFFDFF", 0.13, right=230, top=-260),
    ]
    noise = ft.Container(
        expand=True,
        image=ft.DecorationImage(
            src="noise.png",
            fit=ft.BoxFit.COVER,
            repeat=ft.ImageRepeat.REPEAT,
            opacity=0.16,
        ),
        opacity=0.42,
    )
    # A pair of very soft diagonal sheens gives the surface depth without
    # introducing rectangular blur layers, which are visible on some GPUs.
    sheen = ft.Container(
        left=40,
        right=180,
        top=12,
        height=100,
        border_radius=50,
        gradient=ft.LinearGradient(
            begin=ft.Alignment.CENTER_LEFT,
            end=ft.Alignment.CENTER_RIGHT,
            colors=[white(0.0), white(0.018), white(0.0)],
        ),
    )
    lower_glow = orb(900, "#85F4E9", 0.05, left=70, bottom=-680)
    # A final low-opacity scrim separates the decorative backdrop from the
    # working surfaces without making the window look flat or opaque.
    scrim = ft.Container(expand=True, bgcolor=ft.Colors.with_opacity(0.20, "#03070D"))
    return ft.Stack(
        [base, *blobs, noise, scrim, sheen, lower_glow],
        expand=True,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
    )


# ---------------------------------------------------------------------------
# typography / small elements
# ---------------------------------------------------------------------------
def eyebrow(text: str) -> ft.Text:
    return ft.Text(
        text.upper(),
        size=11,
        weight=ft.FontWeight.W_700,
        color=ft.Colors.with_opacity(0.80, ACCENT),
        letter_spacing=1.8,
    )


def heading(text: str, *, size: int = 20) -> ft.Text:
    return ft.Text(
        text,
        size=size,
        weight=ft.FontWeight.W_700,
        color=TEXT_PRIMARY,
    )


def subtext(text: str, *, size: int = 12, color: str = TEXT_MUTED) -> ft.Text:
    return ft.Text(text, size=size, color=color)


def section_marker(icon: str, title: str, *, color: str = ACCENT) -> ft.Row:
    return ft.Row(
        [
            ft.Container(
                width=30,
                height=30,
                border_radius=9,
                bgcolor=ft.Colors.with_opacity(0.12, color),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.WHITE)),
                alignment=ft.Alignment.CENTER,
                content=ft.Icon(icon, size=16, color=color),
            ),
            ft.Text(
                title,
                size=14,
                weight=ft.FontWeight.W_600,
                color=TEXT_PRIMARY,
            ),
        ],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def divider_line(*, opacity: float = 0.08, margin: int = 0) -> ft.Container:
    return ft.Container(
        height=1,
        margin=ft.Margin.symmetric(vertical=margin),
        bgcolor=white(opacity),
    )


def field(
    *,
    hint: str = "",
    value: str = "",
    password: bool = False,
    width: int | float | None = None,
    height: int | None = 44,
    text_size: int = 13,
    keyboard_type: ft.KeyboardType = ft.KeyboardType.TEXT,
    on_change: Any = None,
    on_submit: Any = None,
    prefix_icon: str | None = None,
    dense: bool = True,
) -> ft.TextField:
    return ft.TextField(
        value=value,
        hint_text=hint,
        password=password,
        can_reveal_password=password,
        width=width,
        height=height,
        text_size=text_size,
        color=TEXT_PRIMARY,
        cursor_color=ACCENT,
        bgcolor=ft.Colors.with_opacity(0.045, ft.Colors.WHITE),
        filled=True,
        fill_color=ft.Colors.with_opacity(0.045, ft.Colors.WHITE),
        border=ft.OutlineInputBorder(
            side=ft.BorderSide(0, ft.Colors.TRANSPARENT),
            border_radius=ft.BorderRadius.all(RADIUS_SM),
        ),
        content_padding=ft.Padding.symmetric(horizontal=13, vertical=10),
        hint_style=ft.TextStyle(size=12, color=TEXT_FAINT),
        prefix_icon=prefix_icon,
        dense=dense,
        keyboard_type=keyboard_type,
        on_change=on_change,
        on_submit=on_submit,
    )


def icon_button(
    icon: str,
    *,
    tooltip: str = "",
    on_click: Any = None,
    size: int = 18,
    color: str = TEXT_SECONDARY,
    bgcolor: str | None = None,
    disabled: bool = False,
) -> ft.IconButton:
    return ft.IconButton(
        icon=icon,
        icon_size=size,
        icon_color=color,
        tooltip=tooltip or None,
        on_click=on_click,
        disabled=disabled,
        style=ft.ButtonStyle(
            bgcolor=bgcolor or ft.Colors.with_opacity(0.035, ft.Colors.WHITE),
            overlay_color=white(0.06),
            shape=rounded(11),
            padding=8,
        ),
    )


def primary_button(
    content: str | ft.Control,
    *,
    icon: str | None = None,
    on_click: Any = None,
    disabled: bool = False,
    width: int | float | None = None,
) -> ft.FilledButton:
    return ft.FilledButton(
        content=content,
        icon=icon,
        on_click=on_click,
        disabled=disabled,
        width=width,
        height=46,
        bgcolor=ACCENT,
        color="#06201F",
        elevation=0,
        style=ft.ButtonStyle(
            shape=rounded(15),
            padding=ft.Padding.symmetric(horizontal=18, vertical=10),
            text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_700),
            overlay_color=ft.Colors.with_opacity(0.10, "#00211E"),
            shadow_color=accent(0.25),
        ),
    )


def quiet_button(
    content: str | ft.Control,
    *,
    icon: str | None = None,
    on_click: Any = None,
    disabled: bool = False,
    width: int | float | None = None,
) -> ft.OutlinedButton:
    return ft.OutlinedButton(
        content=content,
        icon=icon,
        on_click=on_click,
        disabled=disabled,
        width=width,
        height=42,
        style=ft.ButtonStyle(
            color=TEXT_SECONDARY,
            side=ft.BorderSide(1, ft.Colors.with_opacity(0.13, ft.Colors.WHITE)),
            shape=rounded(13),
            padding=ft.Padding.symmetric(horizontal=14, vertical=7),
            overlay_color=white(0.04),
            text_style=ft.TextStyle(size=12, weight=ft.FontWeight.W_600),
        ),
    )


def tiny_pill(text: str, *, color: str = ACCENT, active: bool = False) -> ft.Container:
    return ft.Container(
        content=ft.Text(
            text,
            size=10,
            weight=ft.FontWeight.W_700,
            color="#07231F" if active else color,
        ),
        padding=ft.Padding.symmetric(horizontal=9, vertical=4),
        border_radius=99,
        bgcolor=color if active else ft.Colors.with_opacity(0.08, color),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.15 if active else 0.10, color)),
    )


__all__ = [
    "ACCENT",
    "ACCENT_SOFT",
    "ACCENT_STRONG",
    "BG_DEEP",
    "BG_MID",
    "BG_TOP",
    "BG_WARM",
    "BLUE",
    "DANGER",
    "GLASS_TINT",
    "MINT",
    "RADIUS_LG",
    "RADIUS_MD",
    "RADIUS_SM",
    "RADIUS_XL",
    "SUCCESS",
    "TEXT_FAINT",
    "TEXT_MUTED",
    "FONT_UI",
    "TEXT_PRIMARY",
    "TEXT_SECONDARY",
    "VIOLET",
    "WARNING",
    "accent",
    "aurora_background",
    "black",
    "divider_line",
    "eyebrow",
    "field",
    "glass_panel",
    "glow_shadow",
    "gradient_rim",
    "heading",
    "icon_button",
    "panel_gradient",
    "primary_button",
    "quiet_button",
    "rounded",
    "section_marker",
    "soft_shadow",
    "subtext",
    "surface",
    "tiny_pill",
    "white",
]
