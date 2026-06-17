"""
app_state.py — AppState class.

Encapsulates all mutable session state that was previously scattered across
module-level globals in state.py. A single instance is created in app.py and
injected into every blueprint via the factory pattern.

Key properties:
  - No module-level variables. No `global` keyword anywhere.
  - Fully testable: create AppState(), call load(), run assertions directly.
  - Cloud-ready: serialise() / deserialise() stubs are here for step 2
    of the cloud migration (per-session state in Redis/DB).
"""

import os
import numpy as np
import pandas as pd

from serializers import json_safe, df_to_json, get_unique_col_name

BASE_DIR = os.environ.get("DATAGRAD_BASE_DIR") or os.path.dirname(os.path.abspath(__file__))


class AppState:
    # ------------------------------------------------------------------
    # Construction and loading
    # ------------------------------------------------------------------

    def __init__(self):
        self.current_df: pd.DataFrame | None = None
        self.row_excluded_mask: np.ndarray | None = None
        self.row_exclusion_reason: list | None = None
        self.filter_rules: list = []
        self.pre_imputation_df: pd.DataFrame | None = None
        self.imputation_metadata: list = []
        self.dataset_name: str | None = None

    def load(self, df: pd.DataFrame, name: str | None = None) -> None:
        """Replace the current dataset and reset all derived state."""
        self.current_df = df.copy()
        self.dataset_name = name
        self.filter_rules = []
        self.pre_imputation_df = None
        self.imputation_metadata = []
        self._reset_exclusion_state(len(self.current_df))

    @property
    def has_data(self) -> bool:
        return self.current_df is not None

    # ------------------------------------------------------------------
    # Exclusion state management
    # ------------------------------------------------------------------

    def _reset_exclusion_state(self, length: int) -> None:
        self.row_excluded_mask = np.zeros(length, dtype=bool)
        self.row_exclusion_reason = [None] * length

    def _append_reason(self, index: int, reason: str) -> None:
        existing = self.row_exclusion_reason[index]
        if not existing:
            self.row_exclusion_reason[index] = reason
        elif reason not in existing:
            self.row_exclusion_reason[index] = f"{existing}; {reason}"

    def rebuild_exclusion_state(self) -> None:
        """Recompute row_excluded_mask from scratch using current filter_rules."""
        if self.current_df is None:
            self.row_excluded_mask = None
            self.row_exclusion_reason = None
            return

        self._reset_exclusion_state(len(self.current_df))

        for rule in self.filter_rules:
            rule_type = rule.get('type')

            if rule_type == 'category':
                column = rule.get('column')
                values = rule.get('values', [])
                if not column or column not in self.current_df.columns:
                    continue

                series = self.current_df[column]
                normalized = [None if v in ('__BLANK__', None, '') else v for v in values]
                non_null = [v for v in normalized if v is not None]
                coerced = []

                if pd.api.types.is_numeric_dtype(series):
                    for v in non_null:
                        try:
                            num = pd.to_numeric(pd.Series([v]), errors='coerce').iloc[0]
                            if pd.notna(num):
                                coerced.append(num.item() if hasattr(num, 'item') else num)
                        except Exception:
                            continue
                elif pd.api.types.is_bool_dtype(series):
                    for v in non_null:
                        if isinstance(v, bool):
                            coerced.append(v)
                        elif str(v).strip().lower() in ('true', '1', 'yes'):
                            coerced.append(True)
                        elif str(v).strip().lower() in ('false', '0', 'no'):
                            coerced.append(False)
                else:
                    coerced = [str(v) for v in non_null]
                    series = series.astype(str).where(series.notna(), None)

                if pd.api.types.is_numeric_dtype(self.current_df[column]):
                    mask = self.current_df[column].isin(coerced)
                elif pd.api.types.is_bool_dtype(self.current_df[column]):
                    mask = self.current_df[column].isin(coerced)
                else:
                    mask = series.isin(coerced)

                if None in normalized:
                    mask = mask | self.current_df[column].isna()

                self.row_excluded_mask = self.row_excluded_mask | mask.to_numpy()
                reason = f"{column} in {values}"
                for idx, excluded in enumerate(mask.to_numpy()):
                    if excluded:
                        self._append_reason(idx, reason)

            elif rule_type == 'expression':
                expression = rule.get('expression')
                if not expression:
                    continue
                try:
                    mask = self.current_df.eval(expression)
                    mask = pd.Series(mask).fillna(False).astype(bool)
                    self.row_excluded_mask = self.row_excluded_mask | mask.to_numpy()
                    reason = f"expression: {expression}"
                    for idx, excluded in enumerate(mask.to_numpy()):
                        if excluded:
                            self._append_reason(idx, reason)
                except Exception:
                    continue

    # ------------------------------------------------------------------
    # Active DataFrame
    # ------------------------------------------------------------------

    def get_active_df(self) -> pd.DataFrame | None:
        """Return current_df with excluded rows removed."""
        if self.current_df is None:
            return None
        if self.row_excluded_mask is None:
            return self.current_df.copy()
        return self.current_df.loc[~self.row_excluded_mask].copy()

    # ------------------------------------------------------------------
    # Serialisation helpers used by route handlers
    # ------------------------------------------------------------------

    def get_exclusion_payload(self) -> dict:
        """Return the exclusion state dict that routes attach to responses."""
        total = 0 if self.current_df is None else len(self.current_df)
        excluded = 0 if self.row_excluded_mask is None else int(np.sum(self.row_excluded_mask))
        return {
            "row_excluded_mask": [] if self.row_excluded_mask is None
                                  else self.row_excluded_mask.astype(bool).tolist(),
            "row_exclusion_reason": [] if self.row_exclusion_reason is None
                                    else self.row_exclusion_reason,
            "filter_summary": {
                "total_rows": total,
                "excluded_rows": excluded,
                "active_rows": total - excluded,
                "rule_count": len(self.filter_rules),
            },
            "filter_rules": self.filter_rules,
        }

    def merge_exclusion_payload(self, payload: dict) -> dict:
        """Merge exclusion state into an existing response payload dict."""
        payload.update(self.get_exclusion_payload())
        return payload

    def get_table_data(self) -> dict:
        """Full serialised DataFrame payload for the frontend grid."""
        df = self.current_df
        df_safe = df.astype(object).replace({
            pd.NA: None, np.nan: None, np.inf: '∞', -np.inf: '-∞'
        })
        payload = {
            "headers": df.columns.tolist(),
            "data": df_safe.values.tolist(),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "has_pending_imputation": self.pre_imputation_df is not None,
        }
        if self.imputation_metadata and self.pre_imputation_df is not None:
            if list(df.columns) == list(self.pre_imputation_df.columns):
                payload["imputation_metadata"] = self.imputation_metadata
            else:
                payload["imputation_metadata"] = []
        else:
            payload["imputation_metadata"] = self.imputation_metadata or []

        return self.merge_exclusion_payload(payload)

    def unique_col_name(self, base_name: str) -> str:
        """Delegate to serializers helper, bound to current_df."""
        return get_unique_col_name(self.current_df, base_name)

    # ------------------------------------------------------------------
    # Cloud migration stubs (step 2)
    # ------------------------------------------------------------------

    def serialise(self) -> dict:
        """
        Serialise session state to a JSON-safe dict for external storage
        (Redis, DB, etc.). DataFrame stored as Parquet bytes.

        Not yet called — wired up when per-session storage is added.
        """
        import io as _io
        buf = _io.BytesIO()
        if self.current_df is not None:
            self.current_df.to_parquet(buf, index=False)
        pre_buf = _io.BytesIO()
        if self.pre_imputation_df is not None:
            self.pre_imputation_df.to_parquet(pre_buf, index=False)
        return {
            "current_df": buf.getvalue().hex() if self.current_df is not None else None,
            "pre_imputation_df": pre_buf.getvalue().hex() if self.pre_imputation_df is not None else None,
            "row_excluded_mask": self.row_excluded_mask.tolist() if self.row_excluded_mask is not None else None,
            "row_exclusion_reason": self.row_exclusion_reason,
            "filter_rules": self.filter_rules,
            "imputation_metadata": self.imputation_metadata,
        }

    @classmethod
    def deserialise(cls, data: dict) -> "AppState":
        """Reconstruct an AppState from a serialise() dict."""
        import io as _io
        s = cls()
        if data.get("current_df"):
            s.current_df = pd.read_parquet(_io.BytesIO(bytes.fromhex(data["current_df"])))
        if data.get("pre_imputation_df"):
            s.pre_imputation_df = pd.read_parquet(_io.BytesIO(bytes.fromhex(data["pre_imputation_df"])))
        mask = data.get("row_excluded_mask")
        s.row_excluded_mask = np.array(mask, dtype=bool) if mask is not None else None
        s.row_exclusion_reason = data.get("row_exclusion_reason")
        import copy
        s.filter_rules = copy.deepcopy(data.get("filter_rules", []))
        s.imputation_metadata = copy.deepcopy(data.get("imputation_metadata", []))
        return s

    # ------------------------------------------------------------------
    # Compact binary form for Redis (raw Parquet bytes, no hex doubling)
    # ------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """
        Serialise to a compact bytes blob suitable for a Redis value.

        Uses pickle of a dict whose dataframe entries are raw Parquet bytes.
        This avoids the 2x size cost of the hex encoding in serialise() and is
        what RedisSessionStore writes on every request.
        """
        import io as _io
        import pickle

        from serializers import make_parquet_safe

        def _pq(df):
            if df is None:
                return None
            buf = _io.BytesIO()
            make_parquet_safe(df).to_parquet(buf, index=False)
            return buf.getvalue()

        blob = {
            "current_df": _pq(self.current_df),
            "pre_imputation_df": _pq(self.pre_imputation_df),
            "row_excluded_mask": self.row_excluded_mask.tolist() if self.row_excluded_mask is not None else None,
            "row_exclusion_reason": self.row_exclusion_reason,
            "filter_rules": self.filter_rules,
            "imputation_metadata": self.imputation_metadata,
        }
        return pickle.dumps(blob, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def from_bytes(cls, data: bytes) -> "AppState":
        """Reconstruct an AppState from a to_bytes() blob."""
        import io as _io
        import pickle

        blob = pickle.loads(data)
        s = cls()
        if blob.get("current_df") is not None:
            s.current_df = pd.read_parquet(_io.BytesIO(blob["current_df"]))
        if blob.get("pre_imputation_df") is not None:
            s.pre_imputation_df = pd.read_parquet(_io.BytesIO(blob["pre_imputation_df"]))
        mask = blob.get("row_excluded_mask")
        s.row_excluded_mask = np.array(mask, dtype=bool) if mask is not None else None
        s.row_exclusion_reason = blob.get("row_exclusion_reason")
        s.filter_rules = blob.get("filter_rules", [])
        s.imputation_metadata = blob.get("imputation_metadata", [])
        return s
