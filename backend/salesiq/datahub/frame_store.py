"""Save / load the canonical sales table as a compressed NumPy archive.

Used instead of Parquet so the API needs no pyarrow (keeps the serverless
bundle small). Category columns are stored as integer codes + labels.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def save_frame(frame: pd.DataFrame, path: Path) -> None:
    arrays: dict[str, np.ndarray] = {"__columns__": np.array(list(frame.columns), dtype=str)}
    for col in frame.columns:
        s = frame[col]
        if not (pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s)
                or isinstance(s.dtype, pd.CategoricalDtype)):
            s = s.astype("category")
        if isinstance(s.dtype, pd.CategoricalDtype):
            arrays[f"cat:{col}:codes"] = s.cat.codes.to_numpy(dtype=np.int32)
            arrays[f"cat:{col}:labels"] = np.array(s.cat.categories.astype(str), dtype=str)
        elif pd.api.types.is_datetime64_any_dtype(s):
            arrays[f"dt:{col}"] = s.astype("datetime64[ns]").to_numpy().astype("int64")
        else:
            arrays[f"num:{col}"] = s.to_numpy(dtype=float)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        np.savez_compressed(fh, **arrays)


def load_frame(path: Path) -> pd.DataFrame:
    with np.load(path, allow_pickle=False) as z:
        cols = [str(c) for c in z["__columns__"]]
        data = {}
        for col in cols:
            if f"cat:{col}:codes" in z:
                data[col] = pd.Categorical.from_codes(z[f"cat:{col}:codes"], categories=list(z[f"cat:{col}:labels"]))
            elif f"dt:{col}" in z:
                data[col] = pd.to_datetime(z[f"dt:{col}"], unit="ns")
            else:
                data[col] = z[f"num:{col}"]
    return pd.DataFrame(data, columns=cols)
