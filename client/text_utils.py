_author_ = 'Roy'

import pygame

try:
    from bidi.algorithm import get_display as _bidi_get_display
    _BIDI_AVAILABLE = True
except ImportError:
    _BIDI_AVAILABLE = False

    def _bidi_get_display(s):
        return s



_HEBREW_CAPABLE_FONTS = ",".join([
    "Segoe UI",
    "Arial",
    "Arial Hebrew",
    "Heebo",
    "Noto Sans Hebrew",
    "DejaVu Sans",
    "FreeSans",
    "Arial Unicode MS",
    "Helvetica Neue",
    "Helvetica",
])


def _needs_bidi(text: str) -> bool:
    return any(ord(c) >= 0x0590 for c in text)


def shape(text: str) -> str:
    if not text or not _BIDI_AVAILABLE or not _needs_bidi(text):
        return text
    return _bidi_get_display(text)


class BidiFont:
    def __init__(self, font: pygame.font.Font):
        self._font = font

    def render(self, text, antialias, color, *args, **kwargs):
        return self._font.render(shape(text), antialias, color, *args, **kwargs)

    def size(self, text):
        return self._font.size(shape(text))

    def __getattr__(self, name):
        return getattr(self._font, name)


def make_font(size: int, bold: bool = False) -> BidiFont:
    return BidiFont(pygame.font.SysFont(_HEBREW_CAPABLE_FONTS, size, bold=bold))
