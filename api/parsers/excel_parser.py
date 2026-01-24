"""Excel parser using Pandas with multi-sheet support."""

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from parsers.base import BaseParser, ParseResult, TableData

logger = logging.getLogger(__name__)


class ExcelParser(BaseParser):
    """Parser for Excel files (xlsx, xls) using Pandas."""

    MAX_SAMPLE_ROWS = 10

    @property
    def supported_extensions(self) -> list[str]:
        return ["xlsx", "xls"]

    def parse(self, file_path: Path) -> ParseResult:
        """Parse an Excel file and extract all sheets."""
        try:
            # Read all sheets
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names

            all_tables = []
            all_column_headers = []
            all_column_types = {}
            total_rows = 0
            all_numeric_stats = {}

            text_parts = [f"Excel File: {file_path.name}"]
            text_parts.append(f"Sheets: {', '.join(sheet_names)}")
            text_parts.append("")

            for sheet_name in sheet_names:
                try:
                    df = pd.read_excel(excel_file, sheet_name=sheet_name)

                    if df.empty:
                        text_parts.append(f"Sheet '{sheet_name}': Empty")
                        continue

                    # Extract data
                    column_headers = list(df.columns)
                    column_types = self._detect_column_types(df)
                    row_count = len(df)
                    total_rows += row_count

                    # Sample rows
                    sample_rows = df.head(self.MAX_SAMPLE_ROWS).values.tolist()

                    # Create table
                    all_tables.append(
                        TableData(
                            headers=column_headers,
                            rows=sample_rows,
                            title=f"Sheet: {sheet_name}",
                            sheet_name=sheet_name,
                        )
                    )

                    # Aggregate columns
                    all_column_headers.extend(column_headers)
                    for col, dtype in column_types.items():
                        all_column_types[f"{sheet_name}.{col}"] = dtype

                    # Calculate stats
                    stats = self._calculate_stats(df)
                    for col, col_stats in stats.items():
                        all_numeric_stats[f"{sheet_name}.{col}"] = col_stats

                    # Add text representation
                    text_parts.append(f"--- Sheet: {sheet_name} ---")
                    text_parts.append(f"Rows: {row_count}")
                    text_parts.append(f"Columns: {', '.join(column_headers)}")
                    text_parts.append("")
                    text_parts.append(self._describe_sheet(df, sheet_name))
                    text_parts.append("")

                except Exception as e:
                    logger.warning(f"Failed to parse sheet {sheet_name}: {e}")
                    text_parts.append(f"Sheet '{sheet_name}': Error - {e}")

            # Metadata
            metadata = {
                "file_name": file_path.name,
                "file_type": self.get_file_type(file_path),
                "sheet_count": len(sheet_names),
                "total_rows": total_rows,
            }

            return ParseResult(
                text="\n".join(text_parts),
                tables=all_tables,
                metadata=metadata,
                column_headers=list(set(all_column_headers)),
                column_types=all_column_types,
                row_count=total_rows,
                sheet_names=sheet_names,
                numeric_stats=all_numeric_stats,
            )

        except Exception as e:
            logger.error(f"Failed to parse Excel {file_path}: {e}")
            return ParseResult(
                text=f"[Excel parsing failed: {e}]",
                metadata={
                    "file_name": file_path.name,
                    "file_type": self.get_file_type(file_path),
                    "error": str(e),
                },
            )

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
                type_map[col] = "text"
        return type_map

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

    def _describe_sheet(self, df: pd.DataFrame, sheet_name: str) -> str:
        """Create a text description of a sheet."""
        lines = []

        # Column descriptions
        lines.append("Column Details:")
        for col in df.columns:
            unique_count = df[col].nunique()
            null_count = df[col].isnull().sum()
            dtype = df[col].dtype

            type_desc = self._get_type_description(df[col])
            lines.append(f"  - {col}: {type_desc} ({unique_count} unique)")

            # Add sample values for low-cardinality columns
            if unique_count <= 10:
                sample_vals = df[col].dropna().unique()[:5].tolist()
                if sample_vals:
                    lines.append(f"    Values: {', '.join(str(v) for v in sample_vals)}")

        # Numeric summaries
        numeric_cols = df.select_dtypes(include=["number"]).columns
        if len(numeric_cols) > 0:
            lines.append("")
            lines.append("Numeric Summaries:")
            for col in numeric_cols:
                try:
                    total = df[col].sum()
                    avg = df[col].mean()
                    min_val = df[col].min()
                    max_val = df[col].max()
                    lines.append(
                        f"  - {col}: Total={total:,.2f}, Avg={avg:,.2f}, "
                        f"Range=[{min_val:,.2f} to {max_val:,.2f}]"
                    )
                except Exception:
                    pass

        # Sample rows as natural language
        lines.append("")
        lines.append("Sample Records:")
        for idx, row in df.head(3).iterrows():
            row_parts = []
            for col, val in row.items():
                if pd.notna(val):
                    row_parts.append(f"{col}={val}")
            if row_parts:
                lines.append(f"  Record: {', '.join(row_parts[:5])}")

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
            return "true/false"
        else:
            return "text"


# Create instance
excel_parser = ExcelParser()
