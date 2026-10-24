from fastmcp import FastMCP

from expense_tracker_mcp_server import repository as expenses
from expense_tracker_mcp_server.database import db
import os
import json

mcp = FastMCP(name="Expense Tracker")

CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

@mcp.tool
def add_expense(date: str, amount: float, category: str, subcategory: str = "", note: str = "") -> int:
    """Adds a new expense to the database."""
    return expenses.add_expense(date, amount, category, subcategory, note)

@mcp.tool
def get_expense(expense_id: int):
    """Retrieves an expense by its ID."""
    return expenses.get_expense_by_id(expense_id)

@mcp.tool
def list_expenses(start_date: str = None, end_date: str = None):
    """Lists all expenses."""
    return expenses.list_expenses(start_date, end_date)

@mcp.tool
def update_expense(expense_id: int, date: str = None, amount: float = None, category: str = None, subcategory: str = None, note: str = None) -> int:
    """Updates an existing expense."""
    return expenses.update_expense(expense_id, date, amount, category, subcategory, note)

@mcp.tool
def summarize_expenses(start_date: str = None, end_date: str = None, category: str = None):
    """Summarizes expenses by category and subcategory."""
    return expenses.summarize_expenses(start_date, end_date, category)

@mcp.resource("expense://categories", mime_type="application/json")
def get_categories():
    """Returns a list of all unique categories and subcategories."""
    with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return f.read()

@mcp.resource("info://server")
def get_server_info():
    """Returns basic information about the server."""
    info = {
        "name": "Expense Tracker MCP Server",
        "version": "1.0.0",
        "description": "A simple expense tracker server using FastMCP.",
        "tools": [tool.name for tool in mcp.tools.values()],\
        "resources": [resource.name for resource in mcp.resources.values()],
        "author": "Rishi Goyal"
    }
    return json.dumps(info, indent=4)

def main() -> None:
    try:
        expenses.create_expenses_table()
        mcp.run(transport="http", host="0.0.0.0", port=8000)
    finally:
        db.close()


if __name__ == "__main__":
    main()
