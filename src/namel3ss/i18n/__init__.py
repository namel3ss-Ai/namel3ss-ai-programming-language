"""
Simple i18n utilities with fallback.
"""

from __future__ import annotations

from typing import Dict

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        "error.memory.forbidden": "You are not allowed to view this memory.",
        "label.optimizer.suggestion.accepted": "Suggestion accepted",
    },
    "fr": {
        "error.memory.forbidden": "Vous n'êtes pas autorisé à voir cette mémoire.",
        "label.optimizer.suggestion.accepted": "Suggestion acceptée",
    },
}


def translate(key: str, lang: str = "en") -> str:
    lang_map = TRANSLATIONS.get(lang, {})
    if key in lang_map:
        return lang_map[key]
    if key in TRANSLATIONS.get("en", {}):
        return TRANSLATIONS["en"][key]
    return key
