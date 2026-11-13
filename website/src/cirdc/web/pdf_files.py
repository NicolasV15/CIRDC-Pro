"""Lightweight PDF checks at the file-output boundary; never parse a document."""
import os
from pathlib import Path
import stat


def pdf_file_stat(path, *, signature=False):
    """Check readable regular bytes; only an actual output checks the signature."""
    with Path(path).open('rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size <= 0:
            raise ValueError('Unavailable file')
        if signature and (info.st_size <= 5 or b'%PDF-' not in stream.read(1024)):
            raise ValueError('Invalid PDF signature')
    return info
