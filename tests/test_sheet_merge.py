import pandas as pd

from sheet_merge import (
    dedupe,
    drop_empty_rows,
    lowercase_emails,
    normalize_column_name,
    normalize_columns,
    normalize_dates,
    parse_date,
)


def test_normalize_column_name_basic():
    assert normalize_column_name("  Full Name  ") == "name"
    assert normalize_column_name("Order Date") == "date"


def test_normalize_column_name_aliases():
    assert normalize_column_name("E-mail") == "email"
    assert normalize_column_name("mail") == "email"
    assert normalize_column_name("Phone Number") == "phone"
    assert normalize_column_name("tel") == "phone"


def test_normalize_columns_on_dataframe():
    df = pd.DataFrame(columns=["Order ID", "E-mail", "Phone Number"])
    df = normalize_columns(df)
    assert list(df.columns) == ["order_id", "email", "phone"]


def test_drop_empty_rows():
    df = pd.DataFrame(
        {
            "name": ["Alice", None, "  "],
            "email": ["alice@example.com", None, ""],
        }
    )
    cleaned, dropped = drop_empty_rows(df)
    assert dropped == 2
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["name"] == "Alice"


def test_lowercase_emails():
    df = pd.DataFrame({"email": [" Alice@Example.com ", "BOB@EXAMPLE.COM"]})
    df["email"] = df["email"].str.strip()
    df = lowercase_emails(df)
    assert list(df["email"]) == ["alice@example.com", "bob@example.com"]


def test_parse_date_formats():
    assert parse_date("2024-03-05") == "2024-03-05"
    assert parse_date("03/05/2024") == "2024-03-05"
    assert parse_date("March 5, 2024") == "2024-03-05"
    assert parse_date("5 March 2024") == "2024-03-05"


def test_parse_date_empty():
    assert parse_date("") is None
    assert parse_date(None) is None


def test_normalize_dates_column():
    df = pd.DataFrame({"date": ["03/05/2024", "March 6, 2024"]})
    df = normalize_dates(df)
    assert list(df["date"]) == ["2024-03-05", "2024-03-06"]


def test_dedupe_default_keeps_first():
    df = pd.DataFrame(
        {
            "email": ["a@example.com", "a@example.com", "b@example.com"],
            "name": ["A", "A", "B"],
            "source_file": ["f1.csv", "f1.csv", "f1.csv"],
        }
    )
    cleaned, removed = dedupe(df)
    assert removed == 1
    assert len(cleaned) == 2


def test_dedupe_on_subset():
    df = pd.DataFrame(
        {
            "email": ["a@example.com", "a@example.com", "b@example.com"],
            "name": ["A", "A2", "B"],
        }
    )
    cleaned, removed = dedupe(df, subset=["email"])
    assert removed == 1
    assert list(cleaned["name"]) == ["A", "B"]
