"""
DuckDB URL Builder
==================

Build DuckDB connection URL for TPC-H data.
"""

from os import getenv
from pathlib import Path


def build_duckdb_url() -> str:
    """Build DuckDB URL for TPC-H data.

    Returns:
        DuckDB connection URL in SQLAlchemy format.
    """
    # Get path from env or use default
    db_path = getenv("DUCKDB_PATH", "data/tpch_sf1.db")

    # Convert to absolute path
    db_path = Path(db_path).resolve()

    # Verify file exists
    if not db_path.exists():
        print(f"Warning: DuckDB file not found at {db_path}")

    # DuckDB SQLAlchemy URL format: duckdb:///path/to/file.db
    return f"duckdb:///{db_path}"


# Export the URL
duckdb_url = build_duckdb_url()
