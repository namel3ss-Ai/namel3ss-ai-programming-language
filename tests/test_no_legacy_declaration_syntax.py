import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET_EXTS = {".py", ".ai", ".n3", ".md", ".txt", ".yaml", ".yml", ".toml", ".json"}
SKIP_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv"}
KEYWORDS = {"app", "page", "flow", "agent", "tool", "record", "model", "macro"}

LEGACY_PATTERN = re.compile(
    r'^\s*(%s)\s+"[^"]+' % "|".join(KEYWORDS),
    re.MULTILINE,
)


def _should_skip(path: pathlib.Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def _iter_files() -> list[pathlib.Path]:
    roots = [ROOT / "src", ROOT / "tests", ROOT / "examples", ROOT / "docs"]
    files: list[pathlib.Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_dir() or _should_skip(path):
                continue
            if path.suffix in TARGET_EXTS:
                files.append(path)
    return files


def test_no_legacy_declaration_syntax():
    offenders: list[tuple[str, int, str]] = []
    for file_path in _iter_files():
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        for match in LEGACY_PATTERN.finditer(text):
            # Ignore lines already containing ' is ' between keyword and string
            if ' is "' in match.group(0):
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            line = text.splitlines()[line_no - 1].rstrip()
            offenders.append((str(file_path.relative_to(ROOT)), line_no, line))
            if len(offenders) >= 30:
                break
        if len(offenders) >= 30:
            break

    if offenders:
        details = "\n".join(f"{path}:{line_no}: {line}" for path, line_no, line in offenders)
        raise AssertionError(
            "Legacy declaration headers found (missing 'is'). Fix them:\n" + details
        )
