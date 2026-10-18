#!/usr/bin/env python3
"""Merge and clean spreadsheet exports (csv/xlsx) from a folder into one file."""

import argparse
import os
import re
import sys
from datetime import datetime

import pandas as pd

# Column names that mean the same thing but get typed differently across
# spreadsheets. Keys are already lowercase with spaces/dashes turned into
# underscores, values are the canonical name we standardize on.
COLUMN_ALIASES = {
    "e_mail": "email",
    "mail": "email",
    "email_address": "email",
    "phone_number": "phone",
    "tel": "phone",
    "telephone": "phone",
    "full_name": "name",
    "customer_name": "name",
    "client_name": "name",
    "order_date": "date",
    "purchase_date": "date",
    "orderid": "order_id",
    "qty": "quantity",
    "unit_price": "price",
    "product_name": "product",
    "item": "product",
}

# Formats tried in order when parsing dates. Ambiguous strings like
# "03/04/2024" are treated as month/day/year (US style) since that's what
# most of these exports use. Adjust the order below if your data leans
# day-first.
DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%d-%m-%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
]


def normalize_column_name(name):
    name = str(name).strip().lower()
    name = re.sub(r"[\s\-]+", "_", name)
    name = re.sub(r"[^a-z0-9_]", "", name)
    return COLUMN_ALIASES.get(name, name)


def normalize_columns(df):
    df = df.copy()
    df.columns = [normalize_column_name(c) for c in df.columns]
    return df


def trim_whitespace(df):
    df = df.copy()
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].apply(lambda v: v.strip() if isinstance(v, str) else v)
    return df


def drop_empty_rows(df):
    """Drop rows where every cell is empty/NaN. Returns (df, rows_dropped)."""
    blank = df.apply(
        lambda row: all(
            pd.isna(v) or (isinstance(v, str) and v.strip() == "") for v in row
        ),
        axis=1,
    )
    dropped = int(blank.sum())
    return df.loc[~blank].reset_index(drop=True), dropped


def lowercase_emails(df):
    df = df.copy()
    if "email" in df.columns:
        df["email"] = df["email"].apply(
            lambda v: v.strip().lower() if isinstance(v, str) else v
        )
    return df


DAYFIRST_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"]


def parse_date(value, dayfirst=False):
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.date().isoformat()
    text = str(value).strip()
    if not text:
        return None
    formats = DATE_FORMATS[:2] + DAYFIRST_FORMATS + DATE_FORMATS[2:] if dayfirst else DATE_FORMATS
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=dayfirst)
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def normalize_dates(df, dayfirst_files=()):
    df = df.copy()
    date_cols = [c for c in df.columns if c == "date" or c.endswith("_date")]
    files = df["source_file"] if "source_file" in df.columns else [None] * len(df)
    flags = [f in dayfirst_files for f in files]
    for col in date_cols:
        df[col] = [parse_date(v, d) for v, d in zip(df[col], flags)]
    return df


def dedupe(df, subset=None):
    """Drop duplicate rows, keeping the first occurrence. Returns (df, rows_removed)."""
    if subset is None:
        subset = [c for c in df.columns if c != "source_file"]
    subset = [c for c in subset if c in df.columns]
    before = len(df)
    df = df.drop_duplicates(subset=subset or None, keep="first").reset_index(drop=True)
    return df, before - len(df)


def read_folder(folder):
    """Read every csv/xlsx in folder. Returns (merged_df, per_file_stats)."""
    frames = []
    stats = []

    files = sorted(
        f
        for f in os.listdir(folder)
        if f.lower().endswith(".csv") or f.lower().endswith(".xlsx")
    )

    for filename in files:
        path = os.path.join(folder, filename)

        if filename.lower().endswith(".csv"):
            sheets = {None: pd.read_csv(path)}
        else:
            sheets = pd.read_excel(path, sheet_name=None)

        for sheet_name, raw_df in sheets.items():
            df = normalize_columns(raw_df)
            df = trim_whitespace(df)
            rows_read = len(df)
            df, empty_dropped = drop_empty_rows(df)
            df["source_file"] = filename

            stats.append(
                {
                    "file": filename,
                    "sheet": sheet_name or "",
                    "rows_read": rows_read,
                    "empty_rows_dropped": empty_dropped,
                    "columns": ", ".join(c for c in df.columns if c != "source_file"),
                }
            )
            frames.append(df)

    if not frames:
        raise SystemExit(f"No .csv or .xlsx files found in {folder}")

    merged = pd.concat(frames, ignore_index=True, sort=False)
    return merged, stats


def build_summary(file_stats, dupes_removed, final_rows):
    per_file = pd.DataFrame(file_stats)
    totals = pd.DataFrame(
        [
            {"metric": "files_processed", "value": len(file_stats)},
            {"metric": "total_rows_read", "value": int(per_file["rows_read"].sum())},
            {
                "metric": "empty_rows_dropped",
                "value": int(per_file["empty_rows_dropped"].sum()),
            },
            {"metric": "duplicate_rows_removed", "value": dupes_removed},
            {"metric": "final_row_count", "value": final_rows},
        ]
    )
    return per_file, totals


def print_summary(per_file, totals):
    print("\nPer-file summary:")
    print(per_file.to_string(index=False))
    print("\nTotals:")
    print(totals.to_string(index=False))


def write_output(df, output_path, report=None):
    if output_path.lower().endswith(".csv"):
        df.to_csv(output_path, index=False)
        return

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Merged", index=False)
        if report is not None:
            per_file, totals = report
            per_file.to_excel(writer, sheet_name="Summary", index=False, startrow=0)
            start = len(per_file) + 3
            totals.to_excel(writer, sheet_name="Summary", index=False, startrow=start)


def main():
    parser = argparse.ArgumentParser(
        description="Merge and clean spreadsheet exports (csv/xlsx) from a folder."
    )
    parser.add_argument("input_folder", help="folder containing .csv/.xlsx files")
    parser.add_argument(
        "-o", "--output", default="merged.xlsx", help="output file (.xlsx or .csv)"
    )
    parser.add_argument(
        "--dedupe-on",
        help="comma-separated column names to dedupe on (default: all columns)",
    )
    parser.add_argument(
        "--dayfirst",
        nargs="+",
        default=[],
        metavar="FILE",
        help="files whose numeric dates are day/month/year (05/03/2024 = 5 March)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="add a Summary sheet to the output and print stats",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.input_folder):
        parser.error(f"{args.input_folder} is not a folder")

    merged, file_stats = read_folder(args.input_folder)
    merged = lowercase_emails(merged)
    merged = normalize_dates(merged, set(args.dayfirst))

    subset = args.dedupe_on.split(",") if args.dedupe_on else None
    if subset:
        subset = [normalize_column_name(c) for c in subset]
    merged, dupes_removed = dedupe(merged, subset)

    report = None
    if args.report:
        report = build_summary(file_stats, dupes_removed, len(merged))

    write_output(merged, args.output, report)

    print(f"Wrote {len(merged)} rows to {args.output}")
    if report is not None:
        print_summary(*report)


if __name__ == "__main__":
    main()
