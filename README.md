# sheet-merge

Small CLI that merges the messy CSV/Excel exports different systems spit out
(different column names, inconsistent formatting, duplicate rows) into a
single clean spreadsheet with an optional summary of what it did.

If you get order exports from three shops and each one names the email
column something different, has stray whitespace, blank rows and the odd
duplicate, this glues them into one sheet you can actually work with.

## Before / after

`shop_a_orders.csv` (excerpt):

| Order ID | Full Name      | E-mail                    | Order Date |
|----------|----------------|---------------------------|------------|
| A-1002   | Bob Smith      | BOB.SMITH@example.com     | 03/05/2024 |
| A-1002   | Bob Smith      | BOB.SMITH@example.com     | 03/05/2024 |

`shop_c_orders.csv` (excerpt, different headers, different date format):

| OrderID | Name         | Email Address           | Purchase Date     |
|---------|--------------|--------------------------|-------------------|
| C-3001  | Isabel Costa | isabel.costa@example.com | March 8, 2024     |

After running `sheet_merge.py` on the folder:

| order_id | name          | email                     | date       | source_file        |
|----------|---------------|----------------------------|------------|---------------------|
| A-1002   | Bob Smith     | bob.smith@example.com     | 2024-03-05 | shop_a_orders.csv   |
| C-3001   | Isabel Costa  | isabel.costa@example.com  | 2024-03-08 | shop_c_orders.csv   |

Columns are aligned under one name, emails are lowercased, dates are ISO
(`YYYY-MM-DD`), the duplicate Bob Smith row is gone, and every row keeps
track of which file it came from.

## Install

Requires Python 3.9+.

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```
python sheet_merge.py examples/input -o merged.xlsx --report
```

This reads every `.csv` and `.xlsx` file in `examples/input/` (all sheets of
each workbook), cleans and merges them, and writes `merged.xlsx` with a
`Summary` sheet.

To dedupe on a specific column instead of the whole row:

```
python sheet_merge.py examples/input -o merged.xlsx --dedupe-on email --report
```

Output format is picked from the extension of `-o`: `.xlsx` or `.csv`.

## Options

| Option          | Description                                                        | Default        |
|-----------------|----------------------------------------------------------------------|----------------|
| `input_folder`  | Folder containing `.csv`/`.xlsx` files to merge                     | (required)     |
| `-o, --output`  | Output file path, `.xlsx` or `.csv`                                  | `merged.xlsx`  |
| `--dedupe-on`   | Comma-separated column name(s) to dedupe on, keeping the first row  | all columns    |
| `--report`      | Add a `Summary` sheet and print row/dedupe/column stats to the terminal | off        |

## What it cleans up

- Reads all `.csv` and `.xlsx` files in a folder (every sheet of a workbook),
  tagging each row with a `source_file` column.
- Normalizes column names: trims whitespace, lowercases, turns spaces/dashes
  into underscores, and maps common aliases (`e-mail`/`mail` -> `email`,
  `phone number`/`tel` -> `phone`, `order date`/`purchase date` -> `date`,
  etc.) so columns from different sources line up.
- Trims whitespace in every text cell.
- Drops rows that are completely empty.
- Lowercases email addresses.
- Normalizes date columns to ISO `YYYY-MM-DD`. Ambiguous numeric dates like
  `03/04/2024` are read as month/day/year (US-style); see `DATE_FORMATS` in
  `sheet_merge.py` if your data is day-first.
- Removes duplicate rows, keeping the first occurrence.

## Example

`examples/input/` has three small fake order exports (`shop_a_orders.csv`,
`shop_b_orders.xlsx`, `shop_c_orders.csv`) with mismatched headers,
duplicates and blank rows. `examples/output/merged.xlsx` is the result of
running the command above against them: 17 rows read across the three
files, 3 empty rows dropped, 2 duplicates removed, 12 rows in the final
output.

## Tests

```
pip install -r requirements-dev.txt
pytest
```

## License

MIT, see [LICENSE](LICENSE).
