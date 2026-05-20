"""
ingest.py

Owns CSV loading and schema validation.
Checks that all required SCADA columns are present before
returning a raw DataFrame. Does not clean or transform data.
"""

import pandas as pd
from pathlib import Path
import config


def load_csv(file_path: Path) -> pd.DataFrame:
    """
    Load a CSV file and return the raw DataFrame.

    Uses pd.read_csv() with no additional arguments — date parsing
    and type coercion belong to clean.py, not here.

    Parameters:
        file_path (Path): Path to the CSV file to load.

    Returns:
        pd.DataFrame: Raw contents of the CSV, no transforms applied.

    Raises:
        SystemExit: If the file does not exist or cannot be read.
    """
    try:
        return pd.read_csv(file_path)
    except FileNotFoundError:
        raise SystemExit(f"Error: File not found — {file_path}")
    except Exception as e:
        raise SystemExit(f"Error: Could not read file — {file_path}\nReason: {e}")


def validate_schema(df: pd.DataFrame) -> None:
    """
    Validate that the DataFrame contains all five required SCADA columns.

    Compares the DataFrame columns against the config.COL_* constants.
    Does not check column order or dtypes — those belong to clean.py.

    Parameters:
        df (pd.DataFrame): Raw DataFrame to validate.

    Returns:
        None: If all required columns are present.

    Raises:
        SystemExit: With a plain-English message listing the missing
                    and expected columns.
    """
    REQUIRED_COLUMNS = [
        config.COL_DATETIME,
        config.COL_ACTIVE_POWER,
        config.COL_WIND_SPEED,
        config.COL_THEORETICAL,
        config.COL_WIND_DIRECTION,
    ]

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]

    if not missing_columns:
        return

    raise SystemExit(
        f"Error: Schema validation failed.\n"
        f"Missing columns: {missing_columns}\n"
        f"Expected columns: {REQUIRED_COLUMNS}"
    )