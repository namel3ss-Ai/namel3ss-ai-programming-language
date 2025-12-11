import re, pathlib
pat=re.compile(r"with:\n\s+([A-Za-z_][A-Za-z0-9_]*)\s+\"")
print(pat.pattern)
