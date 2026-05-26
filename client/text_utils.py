"""Helpers for rendering text that may contain Hebrew (or other RTL scripts).

Pygame's text pipeline has two gaps that matter for Hebrew:

1. ``pygame.font.SysFont("Helvetica", ...)`` rarely has Hebrew glyphs on
   non-macOS systems, so Hebrew letters render as empty boxes.
2. ``font.render()`` performs no bidirectional reordering — Hebrew strings
   come out in logical order (reversed visually) and mixed Hebrew/English
   strings are jumbled.

This module fixes both:

* :func:`make_font` returns a font sourced from a Hebrew-capable family list
  (Arial Hebrew on macOS, DejaVu/Noto on Linux, Arial on Windows).
* The returned object is a :class:`BidiFont` whose ``render`` and ``size``
  methods automatically reorder the input string with python-bidi.
  Pure-ASCII strings are passed through unchanged, so English text behaves
  exactly as before.

If python-bidi isn't installed the module still works: Hebrew glyphs render
(thanks to the font fallback) but in logical order. A one-line install
(``pip install python-bidi``) restores correct visual order.
"""

import pygame

try:
    from bidi.algorithm import get_display as _bidi_get_display
    _BIDI_AVAILABLE = True
except ImportError:
    _BIDI_AVAILABLE = False

    def _bidi_get_display(s):
        return s


# Fonts tried, in order, when looking for a face with Hebrew coverage.
# pygame.font.SysFont accepts a comma-separated list and picks the first
# installed match.
_HEBREW_CAPABLE_FONTS = ",".join([
    "Arial Hebrew",          # macOS
    "Heebo",                 # macOS / Linux (if installed)
    "Noto Sans Hebrew",      # Linux (Noto family)
    "DejaVu Sans",           # most Linux desktops
    "FreeSans",              # Linux fallback
    "Arial Unicode MS",      # cross-platform Unicode font
    "Segoe UI",              # Windows
    "Arial",                 # Windows / macOS
    "Helvetica Neue",
    "Helvetica",
])


def _needs_bidi(text: str) -> bool:
    """Cheap check: any character above U+0590? Then run BiDi."""
    return any(ord(c) >= 0x0590 for c in text)


def shape(text: str) -> str:
    """Reorder a logical-order Unicode string to visual order.

    No-op for plain ASCII strings or when python-bidi isn't installed.
    """
    if not text or not _BIDI_AVAILABLE or not _needs_bidi(text):
        return text
    return _bidi_get_display(text)


class BidiFont:
    """Thin wrapper around ``pygame.font.Font`` that applies BiDi shaping.

    Forwards every other attribute lookup to the underlying font, so it
    behaves like a drop-in replacement.
    """

    def __init__(self, font: pygame.font.Font):
        self._font = font

    def render(self, text, antialias, color, *args, **kwargs):
        return self._font.render(shape(text), antialias, color, *args, **kwargs)

    def size(self, text):
        return self._font.size(shape(text))

    def __getattr__(self, name):
        return getattr(self._font, name)


def make_font(size: int, bold: bool = False) -> BidiFont:
    """Return a BiDi-aware font preferring families that include Hebrew."""
    return BidiFont(pygame.font.SysFont(_HEBREW_CAPABLE_FONTS, size, bold=bold))
