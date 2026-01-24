"""Tabular data processing for CSV and Excel files."""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


class TabularProcessor:
    """Process CSV and Excel files and generate markdown description."""

    def extract(self, file_path: Path) -> str:
        """Extract data description from a tabular file and convert to markdown.

        Args:
            file_path: Path to the CSV or Excel file

        Returns:
            Markdown-formatted description and sample data
        """
        file_type = file_path.suffix.lower().lstrip(".")
        logger.info(f"Processing tabular file: {file_path} (type: {file_type})")

        if file_type == "csv":
            return self._process_csv(file_path)
        elif file_type in ("xlsx", "xls"):
            return self._process_excel(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    def _process_csv(self, file_path: Path) -> str:
        """Process a CSV file.

        Args:
            file_path: Path to CSV file

        Returns:
            Markdown-formatted description
        """
        try:
            df = pd.read_csv(file_path, nrows=100)
        except Exception as e:
            logger.warning(f"Failed to read CSV with default encoding: {e}")
            # Try with different encodings
            for encoding in ["latin1", "cp1252", "utf-16"]:
                try:
                    df = pd.read_csv(file_path, nrows=100, encoding=encoding)
                    break
                except Exception:
                    continue
            else:
                raise ValueError(f"Could not read CSV file: {file_path}")

        return self._generate_markdown(df, file_path.name)

    def _process_excel(self, file_path: Path) -> str:
        """Process an Excel file.

        Args:
            file_path: Path to Excel file

        Returns:
            Markdown-formatted description
        """
        # Read Excel file to get sheet names
        xl = pd.ExcelFile(file_path)
        sheet_names = xl.sheet_names

        markdown_parts = []
        markdown_parts.append(f"# {file_path.name}")
        markdown_parts.append(f"\n**Sheets:** {', '.join(sheet_names)}")

        for sheet_name in sheet_names[:5]:  # Limit to first 5 sheets
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name, nrows=100)
                sheet_md = self._generate_markdown(df, sheet_name, is_sheet=True)
                markdown_parts.append(f"\n---\n\n## Sheet: {sheet_name}")
                markdown_parts.append(sheet_md)
            except Exception as e:
                logger.warning(f"Failed to process sheet {sheet_name}: {e}")
                continue

        return "\n\n".join(markdown_parts)

    def _generate_markdown(
        self,
        df: pd.DataFrame,
        name: str,
        is_sheet: bool = False,
    ) -> str:
        """Generate markdown description for a dataframe.

        Args:
            df: Pandas DataFrame
            name: Name of the file or sheet
            is_sheet: Whether this is an Excel sheet

        Returns:
            Markdown-formatted description
        """
        parts = []

        if not is_sheet:
            parts.append(f"# {name}")

        # Basic info
        parts.append(f"\n**Rows:** {len(df)} (showing first 100)")
        parts.append(f"**Columns:** {len(df.columns)}")

        # Column information
        parts.append("\n### Columns")
        for col in df.columns:
            dtype = str(df[col].dtype)
            non_null = df[col].notna().sum()
            sample = df[col].dropna().head(3).tolist()
            sample_str = ", ".join(str(s)[:30] for s in sample)
            parts.append(f"- **{col}** ({dtype}): {non_null} values. Sample: {sample_str}")

        # Sample data as table
        parts.append("\n### Sample Data (first 10 rows)")
        sample_df = df.head(10)

        # Create markdown table
        headers = "| " + " | ".join(str(c)[:20] for c in sample_df.columns) + " |"
        separator = "| " + " | ".join(["---"] * len(sample_df.columns)) + " |"

        rows = []
        for _, row in sample_df.iterrows():
            cells = [str(v)[:30].replace("|", "\\|").replace("\n", " ") for v in row]
            rows.append("| " + " | ".join(cells) + " |")

        parts.append(headers)
        parts.append(separator)
        parts.extend(rows)

        # Statistics for numeric columns
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if numeric_cols:
            parts.append("\n### Numeric Statistics")
            stats_df = df[numeric_cols].describe()
            for col in numeric_cols[:10]:  # Limit to first 10
                stats = stats_df[col]
                parts.append(f"- **{col}**: min={stats['min']:.2f}, max={stats['max']:.2f}, mean={stats['mean']:.2f}")

        return "\n".join(parts)


# Global instance
tabular_processor = TabularProcessor()
