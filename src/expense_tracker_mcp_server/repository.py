"""user_repository.py - example of another file reusing the shared connection."""

from .database import db


def create_users_table():
    db.execute(
        """
        IF OBJECT_ID('expenses', 'U') IS NULL
        CREATE TABLE expenses (
            id INT IDENTITY(1,1) PRIMARY KEY,
            date DATE NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            category NVARCHAR(100) NOT NULL,
            subcategory NVARCHAR(100) DEFAULT N'',
            note NVARCHAR(255) DEFAULT N''
        )
        """
    )


def add_expense(date: str, amount: float, category: str, subcategory: str = "", note: str = "") -> int:
    return db.execute(
        "INSERT INTO expenses (date, amount, category, subcategory, note) VALUES (?, ?, ?, ?, ?)",
        (date, amount, category, subcategory, note)
    )


def get_expense_by_id(expense_id: int):
    return db.fetch_one("SELECT * FROM expenses WHERE id = ?", (expense_id,))


def list_expenses(start_date: str = None, end_date: str = None):
    if start_date and end_date:
        return db.fetch_all("SELECT * FROM expenses WHERE date BETWEEN ? AND ? ORDER BY id", (start_date, end_date))
    elif start_date:
        return db.fetch_all("SELECT * FROM expenses WHERE date >= ? ORDER BY id", (start_date,))
    elif end_date:
        return db.fetch_all("SELECT * FROM expenses WHERE date <= ? ORDER BY id", (end_date,))
    else:
        return db.fetch_all("SELECT * FROM expenses ORDER BY id")


def update_expense(expense_id: int, date: str = None, amount: float = None, category: str = None, subcategory: str = None, note: str = None) -> int:
    # Build the UPDATE query dynamically based on provided parameters
    updates = []
    params = []

    if date is not None:
        updates.append("date = ?")
        params.append(date)

    if amount is not None:
        updates.append("amount = ?")
        params.append(amount)

    if category is not None:
        updates.append("category = ?")
        params.append(category)

    if subcategory is not None:
        updates.append("subcategory = ?")
        params.append(subcategory)

    if note is not None:
        updates.append("note = ?")
        params.append(note)

    if not updates:
        raise ValueError("At least one parameter must be provided for update")

    params.append(expense_id)  # WHERE id = ?

    query = f"UPDATE expenses SET {', '.join(updates)} WHERE id = ?"
    return db.execute(query, tuple(params))

def summarize_expenses(start_date: str = None, end_date: str = None, category: str = None):
    query = "SELECT category, subcategory, SUM(amount) as total_amount FROM expenses"
    conditions = []
    params = []

    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)

    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)

    if category:
        conditions.append("category = ?")
        params.append(category)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " GROUP BY category, subcategory ORDER BY category, subcategory"

    return db.fetch_all(query, tuple(params))