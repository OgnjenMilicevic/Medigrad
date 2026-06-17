"""
activity_log.py — local, append-only record of what was done in the app.

Designed for classroom / exam use: every analysis a student runs is recorded
with a timestamp, the chosen test, the columns/parameters, and the headline
result (statistic + p-value). Entries are written to the student's own user
folder in two formats:

  - datagrad_activity.log   human-readable, one line per action
  - datagrad_activity.csv   structured, opens in any spreadsheet for review

A short, student-supplied "Session ID" (name / student number) is stamped on
every entry so a stack of logs can be sorted by student.

This is an integrity AID and convenience record — not tamper-proof. The files
live on the local machine and a determined user could edit or delete them. For
real proctoring rely on the exam environment, not this log.
"""

import csv
import json
import os
import threading
from datetime import datetime

_LOCK = threading.Lock()

# Resolve a writable per-user directory (works the same on Win/macOS/Linux).
def _log_dir():
    override = os.environ.get("DATAGRAD_LOG_DIR")
    if override:
        base = override
    else:
        base = os.path.join(os.path.expanduser("~"), "Datagrad")
    os.makedirs(base, exist_ok=True)
    return base


def _paths():
    d = _log_dir()
    return (
        os.path.join(d, "datagrad_activity.log"),
        os.path.join(d, "datagrad_activity.csv"),
    )


_CSV_HEADER = ["timestamp", "session_id", "action", "method", "dataset", "rows", "parameters", "result"]


def _summarize_result(result):
    """Pull a compact statistic/p-value string out of a result dict."""
    if not isinstance(result, dict):
        return ""
    # Gather candidate tables: the per-test 'tables' dict plus a top-level
    # 'summary' table (used by correlation).
    candidate_tables = []
    tables = result.get("tables", {})
    if isinstance(tables, dict):
        candidate_tables.extend(tables.values())
    if isinstance(result.get("summary"), dict):
        candidate_tables.append(result["summary"])

    bits = []
    for tbl in candidate_tables:
        if not isinstance(tbl, dict):
            continue
        headers = tbl.get("headers") or []
        data = tbl.get("data") or []
        if not headers or not data:
            continue
        row = data[0]
        for h, v in zip(headers, row):
            hl = str(h).lower()
            if any(k in hl for k in ("p_value", "p-value", "pvalue", "p value")):
                bits.append(f"{h}={v}")
            elif any(k in hl for k in (
                "coefficient", "stat", "chi2", "rho", "u_", "w_", "h_",
                "f_", "t_", "odds", "eta", "coef",
            )):
                bits.append(f"{h}={v}")
    seen, out = set(), []
    for b in bits:
        if b not in seen:
            seen.add(b)
            out.append(b)
        if len(out) >= 6:
            break
    return "; ".join(out)


def _clean_params(payload):
    if not isinstance(payload, dict):
        return ""
    keep = {}
    for k, v in payload.items():
        if k in ("session_id", "_session_id"):
            continue
        keep[k] = v
    return json.dumps(keep, ensure_ascii=False, sort_keys=True)


def record(action, method=None, payload=None, result=None, session_id=None,
           dataset=None, n_rows=None):
    """
    Append one entry to both log files. Never raises — logging must not break
    the analysis it is recording.
    """
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sid = (session_id or "").strip() or "(unset)"
        params = _clean_params(payload)
        summary = _summarize_result(result)
        method = method or action
        ds = (dataset or "").strip()
        rows_str = "" if n_rows is None else str(n_rows)

        log_path, csv_path = _paths()
        line = (f"[{ts}] session={sid} | {action} | method={method} | "
                f"dataset={ds or '-'} | rows={rows_str or '-'} | "
                f"params={params} | result={summary}\n")

        with _LOCK:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line)

            new_csv = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
            with open(csv_path, "a", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                if new_csv:
                    w.writerow(_CSV_HEADER)
                w.writerow([ts, sid, action, method, ds, rows_str, params, summary])
    except Exception:
        # Deliberately swallow — a logging failure must never affect the user.
        pass


def log_location():
    """Return the folder where logs are written (for display in the UI)."""
    return _log_dir()
