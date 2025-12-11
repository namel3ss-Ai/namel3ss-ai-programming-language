import re, pathlib
pat=re.compile(r"with:\n\s+([A-Za-z_][A-Za-z0-9_]*)\s+\"")
paths=list(pathlib.Path('tests').rglob('*.py'))+list(pathlib.Path('examples').rglob('*.ai'))+list(pathlib.Path('docs').rglob('*.md'))
for path in paths:
    text=path.read_text(encoding='utf-8', errors='ignore')
    for m in pat.finditer(text):
        print(f"{path}:{m.start()} -> {m.group(1)}")
