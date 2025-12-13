import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
TARGETS = [
    BASE_DIR / "templates",
    BASE_DIR / "examples",
    BASE_DIR / "src/namel3ss/macros.py",
]


PATTERNS = {
    "use macro without is": re.compile(r'use\s+macro\s+"'),
    "select block": re.compile(r'^\s*select\s*:', re.MULTILINE),
    "source block": re.compile(r'^\s*source\s*:', re.MULTILINE),
}


def _scan_file(path: Path) -> list[tuple[int, str, str]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    offenses: list[tuple[int, str, str]] = []
    for label, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            line = text.splitlines()[line_no - 1].rstrip()
            offenses.append((line_no, label, line))
    return offenses


def test_no_legacy_templates_syntax():
    offenders: list[tuple[Path, int, str, str]] = []
    for target in TARGETS:
        if target.is_file():
            for line_no, label, line in _scan_file(target):
                offenders.append((target, line_no, label, line))
            continue
        if target.exists():
            for path in target.rglob("*"):
                if path.is_file():
                    for line_no, label, line in _scan_file(path):
                        offenders.append((path, line_no, label, line))
    if offenders:
        details = "\n".join(
            f"{p}:{ln}: {label}: {snippet}" for p, ln, label, snippet in offenders[:30]
        )
        raise AssertionError(
            "Legacy template syntax found (showing first offenders):\n" + details
        )
