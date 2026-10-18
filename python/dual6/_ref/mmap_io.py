"""File and mmap helpers for Dual6 frames.

The mmap path is read-only.  It lets a caller decode a frame without first
copying the whole file into a Python ``bytes`` object.
"""

from __future__ import annotations

import mmap
import os
from types import TracebackType
from typing import List, Optional, Tuple, Type

from .errors import Dual6Error, ErrorCode


def write_frame(path: str | os.PathLike[str], frame: bytes) -> int:
    """Write a complete frame to ``path``; return the number of bytes written."""
    data = bytes(frame)
    with open(path, "wb") as fh:
        return fh.write(data)


def read_frame(path: str | os.PathLike[str]) -> bytes:
    """Read a complete frame from ``path``."""
    with open(path, "rb") as fh:
        return fh.read()


class MappedFrame:
    """Read-only mmap view over a complete Dual6 frame file."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = os.fspath(path)
        self._file = open(self._path, "rb")
        try:
            self._mm = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
        except Exception:
            self._file.close()
            raise

    def __enter__(self) -> "MappedFrame":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.close()

    @property
    def buffer(self) -> mmap.mmap:
        return self._mm

    def close(self) -> None:
        try:
            self._mm.close()
        finally:
            self._file.close()

    def unpack(self) -> Tuple[int, List[int], List[int], dict]:
        """Auto-detect and decode the mapped frame.

        Prefer the native buffer decoder when it is available; it reads the
        mmap through PyBuffer without copying the whole file into a Vec.
        """
        from .. import unpack_frame_auto_buffer

        return unpack_frame_auto_buffer(self._mm)


def main_check(path: str | os.PathLike[str]) -> dict:
    """Small convenience helper used by tests and CLI experiments."""
    with MappedFrame(path) as mapped:
        version, bits, trits, meta = mapped.unpack()
    return {"version": version, "width": len(bits), "meta": meta}
