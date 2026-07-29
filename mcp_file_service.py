import csv
import re
import uuid
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("File Service", port=8000)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

_SAFE_ID = re.compile(r"[^a-zA-Z0-9_-]")


def _path(session_id: str) -> Path:
    safe_id = _SAFE_ID.sub("", session_id) or "default"
    return DATA_DIR / f"{safe_id}.csv"


@mcp.tool()
def read_csv(session_id: str) -> list[dict]:
    """Read every row of the CSV file currently uploaded for this session.
    Returns an empty list if the user hasn't uploaded a CSV yet."""
    path = _path(session_id)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@mcp.tool()
def add_row(session_id: str, name: str, qty: int) -> dict:
    """Add a row with a name and quantity. Only works if the uploaded CSV has
    (or will have) 'name' and 'qty' columns - not all uploaded CSVs match this shape."""
    path = _path(session_id)
    rows = read_csv(session_id)
    if rows and not {"name", "qty"}.issubset(rows[0].keys()):
        raise ValueError(
            "The uploaded CSV doesn't have 'name'/'qty' columns, so rows can't be added with this tool."
        )
    row = {"id": uuid.uuid4().hex[:6], "name": name, "qty": str(qty)}
    is_new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "qty"])
        if is_new:
            writer.writeheader()
        writer.writerow(row)
    return row


@mcp.tool()
def update_qty(session_id: str, row_id: str, qty: int) -> str:
    """Update the 'qty' column for the row matching 'id' == row_id.
    Only works on CSVs with 'id' and 'qty' columns."""
    rows = read_csv(session_id)
    if rows and not {"id", "qty"}.issubset(rows[0].keys()):
        raise ValueError("The uploaded CSV doesn't have 'id'/'qty' columns.")
    for r in rows:
        if r["id"] == row_id:
            r["qty"] = str(qty)
    path = _path(session_id)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else ["id", "name", "qty"])
        w.writeheader()
        w.writerows(rows)
    return "ok"


@mcp.tool()
def delete_row(session_id: str, row_id: str) -> str:
    """Delete the row matching 'id' == row_id. Only works on CSVs with an 'id' column."""
    rows = read_csv(session_id)
    if rows and "id" not in rows[0]:
        raise ValueError("The uploaded CSV doesn't have an 'id' column.")
    rows = [r for r in rows if r["id"] != row_id]
    path = _path(session_id)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else ["id", "name", "qty"])
        w.writeheader()
        w.writerows(rows)
    return "ok"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
