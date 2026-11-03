"""Scan evidence with examiner-supplied YARA rules. Usage: run_yara.py <evidence> <out> <rules b64>

Archives are extracted and scanned file by file; anything else (e.g. a disk or memory image)
is scanned as one raw file.
"""

import base64
import json
import subprocess
import sys
from pathlib import Path

ev, out, rules_b64 = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
rules = out / "rules.yar"
rules.write_bytes(base64.b64decode(rules_b64))
check = subprocess.run(
    ["yarac", str(rules), str(out / "rules.compiled")], capture_output=True, text=True
)
if check.returncode != 0:
    print("rule compilation failed:\n" + check.stderr, file=sys.stderr)
    sys.exit(2)
src = Path(
    subprocess.run(
        ["python", "/opt/stage.py", ev, str(out)], capture_output=True, text=True, check=True
    ).stdout.strip()
)
r = subprocess.run(
    ["yara", "-C", "-r", "-s", "-w", "-p", "4", str(out / "rules.compiled"), str(src)],
    capture_output=True,
    text=True,
)
matches, cur = [], None
for line in r.stdout.splitlines():
    if line.startswith("0x") and cur is not None:
        off, _, rest = line.partition(":")
        ident, _, data = rest.partition(":")
        if len(cur["strings"]) < 50:
            cur["strings"].append({"offset": int(off, 16), "id": ident, "data": data[:200]})
    elif " " in line:
        rule, _, path = line.partition(" ")
        p = Path(path)
        rel = str(p.relative_to(src)) if src.is_dir() and p.is_relative_to(src) else p.name
        cur = {"rule": rule, "file": rel, "strings": []}
        matches.append(cur)
(out / "yara.json").write_text(json.dumps(matches))
print(f"{len(matches)} matches", flush=True)
if r.returncode != 0:
    print(r.stderr, file=sys.stderr)
    sys.exit(r.returncode)
