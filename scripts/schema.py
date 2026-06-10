"""Shared paths and the unified per-source column contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache"
OUT = ROOT / "public" / "deposits.json"

# Each source's load() returns a pandas DataFrame with exactly these columns. Commodity
# bucketing and coordinate rounding happen centrally in the orchestrator — sources only
# rename/parse their native columns into this shape.
UNIFIED_COLUMNS = [
    "name",         # str (may be empty -> "Unnamed site" at output)
    "lat",          # raw lat (str/float); orchestrator coerces + rounds
    "lng",          # raw lng
    "commodities",  # list[str]: ordered raw commodity field strings, primary first
    "status_raw",   # source's own status string (or None)
    "depositType",  # source's deposit-type / facility-type string (or None)
    "source",       # short stable id: "mrds", "gsc", "minfac", ...
    "country",      # country name when the source provides it (or None) — for the report
    "source_id",    # source's native record id (or None) — for dedup provenance/debugging
]
