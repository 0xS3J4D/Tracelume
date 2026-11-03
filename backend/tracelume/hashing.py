import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

CHUNK = 4 * 1024 * 1024


class DualHasher:
    """Computes SHA-256 and MD5 in a single pass."""

    def __init__(self) -> None:
        self._sha256 = hashlib.sha256()
        self._md5 = hashlib.md5(usedforsecurity=False)
        self.size = 0

    def update(self, data: bytes) -> None:
        self._sha256.update(data)
        self._md5.update(data)
        self.size += len(data)

    @property
    def sha256(self) -> str:
        return self._sha256.hexdigest()

    @property
    def md5(self) -> str:
        return self._md5.hexdigest()


def hash_stream(
    src: BinaryIO, dst: BinaryIO | None = None, progress: Callable[[int], None] | None = None
) -> DualHasher:
    h = DualHasher()
    while chunk := src.read(CHUNK):
        h.update(chunk)
        if dst is not None:
            dst.write(chunk)
        if progress:
            progress(h.size)
    return h


def hash_file(path: Path) -> DualHasher:
    with path.open("rb") as f:
        return hash_stream(f)
