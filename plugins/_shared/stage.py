"""Shared by tool images: make evidence available as a directory without touching the original.

    stage.py <evidence> <workdir>    -> prints the directory (or file) tools should read

Folders are used in place (read-only mount). .zip / .tar / .tar.gz / .tgz are extracted into
<workdir>/_input with path-traversal protection. Any other single file is used as-is.
"""

import sys
import tarfile
import zipfile
from pathlib import Path

ev, work = Path(sys.argv[1]), Path(sys.argv[2])
name = ev.name.lower()
dest = work / "_input"
if ev.is_dir():
    print(ev)
elif name.endswith(".zip"):
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    with zipfile.ZipFile(ev) as z:
        for m in z.infolist():
            target = (dest / m.filename).resolve()
            if not target.is_relative_to(root):
                print(f"skipping unsafe path {m.filename}", file=sys.stderr)
                continue
            z.extract(m, dest)
    print(dest)
elif name.endswith((".tar", ".tar.gz", ".tgz")):
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(ev) as t:
        t.extractall(dest, filter="data")
    print(dest)
else:
    print(ev)
