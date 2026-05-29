# Custom mapping table (PySide6)

A `QTableView` with a two-level header and a narrow arrow column between source and target device columns.

## Layout

Six model columns (Source × 3, Target × 3). A 64px gutter between them is not a column; arrows are painted there and target cells/headers are shifted right.

## Run

```bash
pip install -r requirements.txt
python main.py
```
