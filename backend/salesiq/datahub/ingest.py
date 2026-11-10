"""Module A - Data Hub: safe CSV reading.

Uploaded files are treated as plain data. Nothing is executed or evaluated;
every value is read as text first and only converted once its role is known.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass

import pandas as pd


class IngestError(ValueError):
    """Raised when a file cannot be read as a usable sales table."""


@dataclass
class ReadResult:
    frame: pd.DataFrame
    delimiter: str
    encoding: str
    skipped_lines: int


_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
_DELIMS = [",", ";", "\t", "|"]


def _decode(raw: bytes) -> tuple[str, str]:
    for enc in _ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise IngestError("The file is not readable text (unknown encoding).")


def _sniff_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters="".join(_DELIMS)).delimiter
    except csv.Error:
        first = sample.splitlines()[0] if sample else ""
        counts = {d: first.count(d) for d in _DELIMS}
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ","


def read_csv_bytes(raw: bytes, max_rows: int = 2_000_000) -> ReadResult:
    """Read uploaded CSV bytes into a DataFrame of strings."""
    if not raw or not raw.strip():
        raise IngestError("The file is empty.")
    if raw[:4] == b"PK\x03\x04":
        raise IngestError("This looks like an Excel or zip file. Please export it as CSV.")
    if b"\x00" in raw[:4096]:
        raise IngestError("This looks like a binary file, not a CSV.")

    text, encoding = _decode(raw)
    delimiter = _sniff_delimiter(text[:20000])

    skipped = 0

    def _bad_line(_line):  # count malformed rows instead of failing the upload
        nonlocal skipped
        skipped += 1
        return None

    try:
        frame = pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            dtype=str,
            keep_default_na=True,
            na_values=["", "NA", "N/A", "null", "NULL", "None", "nan", "NaN"],
            engine="python",
            on_bad_lines=_bad_line,
            nrows=max_rows,
            skipinitialspace=True,
        )
    except pd.errors.EmptyDataError as exc:
        raise IngestError("The file has no rows.") from exc
    except Exception as exc:  # malformed quoting etc.
        raise IngestError(f"The CSV could not be parsed: {exc}") from exc

    frame.columns = [str(c).strip() for c in frame.columns]
    if frame.columns.duplicated().any():
        dups = sorted(set(frame.columns[frame.columns.duplicated()]))
        raise IngestError(f"Duplicate column names: {', '.join(dups)}")
    if frame.shape[1] < 2:
        raise IngestError("Only one column was found. Check that the file is comma, semicolon or tab separated.")
    if frame.empty:
        raise IngestError("The file has a header but no data rows.")
    frame = frame.loc[:, [c for c in frame.columns if not c.lower().startswith("unnamed:") or frame[c].notna().any()]]
    return ReadResult(frame=frame, delimiter=delimiter, encoding=encoding, skipped_lines=skipped)
