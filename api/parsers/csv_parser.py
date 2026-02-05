"""CSV parser using Pandas with schema detection."""

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import chardet

from parsers.base import BaseParser, ParseResult, TableData

logger = logging.getLogger(__name__)


class CSVParser(BaseParser):
    """Parser for CSV files using Pandas."""

    MAX_SAMPLE_ROWS = 10
    MAX_TEXT_ROWS = 100

    @property
    def supported_extensions(self) -> list[str]:
        return ["csv"]

    def parse(self, file_path: Path) -> ParseResult:
        """Parse a CSV file and extract schema and content."""
        try:
            # Detect encoding
            encoding = self._detect_encoding(file_path)

            # Read CSV
            df = pd.read_csv(file_path, encoding=encoding)

            # Extract schema info
            column_headers = list(df.columns)
            column_types = self._detect_column_types(df)
            row_count = len(df)

            # Get sample rows
            sample_df = df.head(self.MAX_SAMPLE_ROWS)
            sample_rows = sample_df.values.tolist()

            # Calculate numeric statistics
            numeric_stats = self._calculate_stats(df)

            # Create text representation for indexing
            text = self._create_text_representation(df, file_path.name)

            # Create table data
            tables = [
                TableData(
                    headers=column_headers,
                    rows=sample_rows,
                    title=f"CSV Data: {file_path.name}",
                )
            ]

            # Metadata
            metadata = {
                "file_name": file_path.name,
                "file_type": "csv",
                "encoding": encoding,
                "row_count": row_count,
                "column_count": len(column_headers),
            }

            return ParseResult(
                text=text,
                tables=tables,
                metadata=metadata,
                column_headers=column_headers,
                column_types=column_types,
                sample_rows=sample_rows,
                row_count=row_count,
                numeric_stats=numeric_stats,
                dataframe=df,
            )

        except Exception as e:
            logger.error(f"Failed to parse CSV {file_path}: {e}")
            return ParseResult(
                text=f"[CSV parsing failed: {e}]",
                metadata={
                    "file_name": file_path.name,
                    "file_type": "csv",
                    "error": str(e),
                },
            )

    def _detect_encoding(self, file_path: Path) -> str:
        """Detect file encoding using chardet."""
        try:
            with open(file_path, "rb") as f:
                raw = f.read(10000)  # Read first 10KB
                result = chardet.detect(raw)
                return result.get("encoding", "utf-8") or "utf-8"
        except Exception:
            return "utf-8"

    def _detect_column_types(self, df: pd.DataFrame) -> dict[str, str]:
        """Detect and describe column data types."""
        type_map = {}
        for col in df.columns:
            dtype = df[col].dtype
            if pd.api.types.is_datetime64_any_dtype(dtype):
                type_map[col] = "datetime"
            elif pd.api.types.is_numeric_dtype(dtype):
                if pd.api.types.is_integer_dtype(dtype):
                    type_map[col] = "integer"
                else:
                    type_map[col] = "decimal"
            elif pd.api.types.is_bool_dtype(dtype):
                type_map[col] = "boolean"
            else:
                # Check for date-like strings
                if self._looks_like_date(df[col]):
                    type_map[col] = "date_string"
                # Check for currency
                elif self._looks_like_currency(df[col]):
                    type_map[col] = "currency"
                else:
                    type_map[col] = "text"
        return type_map

    def _looks_like_date(self, series: pd.Series) -> bool:
        """Check if a series looks like dates."""
        try:
            sample = series.dropna().head(10)
            if len(sample) == 0:
                return False
            pd.to_datetime(sample)
            return True
        except Exception:
            return False

    def _looks_like_currency(self, series: pd.Series) -> bool:
        """Check if a series looks like currency values."""
        try:
            sample = series.dropna().astype(str).head(10)
            currency_chars = ["$", "€", "£", "¥", "₹"]
            return any(
                any(char in val for char in currency_chars) for val in sample
            )
        except Exception:
            return False

    def _calculate_stats(self, df: pd.DataFrame) -> dict[str, dict[str, float]]:
        """Calculate statistics for numeric columns."""
        stats = {}
        numeric_cols = df.select_dtypes(include=["number"]).columns

        for col in numeric_cols:
            try:
                col_stats = df[col].describe()
                stats[col] = {
                    "min": float(col_stats.get("min", 0)),
                    "max": float(col_stats.get("max", 0)),
                    "mean": float(col_stats.get("mean", 0)),
                    "sum": float(df[col].sum()),
                }
            except Exception:
                pass

        return stats

    def _create_text_representation(self, df: pd.DataFrame, file_name: str) -> str:
        """Create a text representation of the CSV for indexing."""
        lines = []

        # File overview
        lines.append(f"CSV File: {file_name}")
        lines.append(f"Total rows: {len(df)}")
        lines.append(f"Columns: {', '.join(df.columns)}")
        lines.append("")

        # Column descriptions
        lines.append("Column Details:")
        for col in df.columns:
            dtype = df[col].dtype
            unique_count = df[col].nunique()
            null_count = df[col].isnull().sum()

            type_desc = self._get_type_description(df[col])
            lines.append(f"  - {col}: {type_desc} ({unique_count} unique values)")

            # Add sample values for categorical columns
            if unique_count <= 10 and dtype == "object":
                sample_vals = df[col].dropna().unique()[:5].tolist()
                lines.append(f"    Sample values: {', '.join(str(v) for v in sample_vals)}")

        lines.append("")

        # Numeric summaries
        numeric_cols = df.select_dtypes(include=["number"]).columns
        if len(numeric_cols) > 0:
            lines.append("Numeric Summaries:")
            for col in numeric_cols:
                try:
                    total = df[col].sum()
                    avg = df[col].mean()
                    lines.append(f"  - {col}: Total={total:,.2f}, Average={avg:,.2f}")
                except Exception:
                    pass
            lines.append("")

        # Sample data as natural language
        lines.append("Sample Data:")
        for idx, row in df.head(5).iterrows():
            row_parts = []
            for col, val in row.items():
                if pd.notna(val):
                    row_parts.append(f"{col}={val}")
            lines.append(f"  Row {idx + 1}: {', '.join(row_parts)}")

        return "\n".join(lines)

    def _get_type_description(self, series: pd.Series) -> str:
        """Get a human-readable type description."""
        dtype = series.dtype

        if pd.api.types.is_datetime64_any_dtype(dtype):
            return "dates"
        elif pd.api.types.is_numeric_dtype(dtype):
            if pd.api.types.is_integer_dtype(dtype):
                return "integers"
            return "decimal numbers"
        elif pd.api.types.is_bool_dtype(dtype):
            return "true/false values"
        else:
            if self._looks_like_date(series):
                return "date strings"
            elif self._looks_like_currency(series):
                return "currency values"
            return "text"


# Create instance
csv_parser = CSVParser()
