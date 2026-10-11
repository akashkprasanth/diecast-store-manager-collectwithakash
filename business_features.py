"""Database support for CollectWithAkash business features."""

import sqlite3
from db import get_connection


def init_business_tables():
    """Create new business tables without altering existing records."""
    connection = get_connection()

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        connection.executescript("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                address TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_date TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL CHECK (amount >= 0),
                payment_method TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT NOT NULL UNIQUE,
                order_id INTEGER NOT NULL,
                customer_name TEXT NOT NULL DEFAULT '',
                customer_phone TEXT NOT NULL DEFAULT '',
                customer_email TEXT NOT NULL DEFAULT '',
                customer_address TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            );

            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                car_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                unit_price REAL NOT NULL CHECK (unit_price >= 0),
                FOREIGN KEY (invoice_id) REFERENCES invoices(id),
                FOREIGN KEY (car_id) REFERENCES cars(id)
            );

            CREATE INDEX IF NOT EXISTS idx_expenses_date
                ON expenses(expense_date);

            CREATE INDEX IF NOT EXISTS idx_invoices_order
                ON invoices(order_id);
        """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def add_supplier(name, phone="", email="", address="", notes=""):
    """Add a supplier and return its ID."""
    name = (name or "").strip()

    if not name:
        raise ValueError("Supplier name is required.")

    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO suppliers (name, phone, email, address, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (
            name,
            (phone or "").strip(),
            (email or "").strip(),
            (address or "").strip(),
            (notes or "").strip()
        ))

        return cursor.lastrowid


def add_expense(
    expense_date,
    category,
    description,
    amount,
    payment_method="",
    notes=""
):
    """Record an operating expense and return its ID."""
    import math

    category = (category or "").strip()
    description = (description or "").strip()

    if not category:
        raise ValueError("Expense category is required.")

    if not description:
        raise ValueError("Expense description is required.")

    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise ValueError("Expense amount must be a number.")

    if not math.isfinite(amount) or amount < 0:
        raise ValueError("Expense amount must be finite and non-negative.")

    if hasattr(expense_date, "isoformat"):
        expense_date = expense_date.isoformat()
    else:
        expense_date = str(expense_date or "").strip()

    if not expense_date:
        raise ValueError("Expense date is required.")

    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO expenses (
                expense_date, category, description, amount,
                payment_method, notes
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            expense_date,
            category,
            description,
            float(amount),
            (payment_method or "").strip(),
            (notes or "").strip()
        ))

        return cursor.lastrowid


def get_expenses(start_date=None, end_date=None):
    """Return expenses, optionally filtered by date."""
    query = """
        SELECT id, expense_date, category, description,
               amount, payment_method, notes
        FROM expenses
        WHERE 1 = 1
    """
    parameters = []

    if start_date:
        start_date = (
            start_date.isoformat()
            if hasattr(start_date, "isoformat")
            else str(start_date)
        )
        query += " AND expense_date >= ?"
        parameters.append(start_date)

    if end_date:
        end_date = (
            end_date.isoformat()
            if hasattr(end_date, "isoformat")
            else str(end_date)
        )
        query += " AND expense_date <= ?"
        parameters.append(end_date)

    query += " ORDER BY expense_date DESC, id DESC"

    with get_connection() as connection:
        return connection.execute(query, parameters).fetchall()


def get_supplier_spending():
    """Summarize historical purchases by their recorded supplier name."""
    with get_connection() as connection:
        return connection.execute("""
            SELECT
                COALESCE(NULLIF(TRIM(supplier), ''), 'Unspecified') AS supplier,
                COUNT(*) AS purchase_count,
                COALESCE(SUM(quantity * unit_cost), 0) AS total_spending
            FROM purchases
            GROUP BY COALESCE(NULLIF(TRIM(supplier), ''), 'Unspecified')
            ORDER BY total_spending DESC
        """).fetchall()


def create_invoice(order_id, invoice_number, customer_name="",
                   customer_phone="", customer_email="",
                   customer_address=""):
    """Create an invoice from an existing sale."""
    invoice_number = (invoice_number or "").strip()

    if not invoice_number:
        raise ValueError("Invoice number is required.")

    connection = get_connection()

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        order = connection.execute("""
            SELECT car_id, quantity, unit_price
            FROM orders
            WHERE id = ?
        """, (order_id,)).fetchone()

        if order is None:
            raise ValueError("The selected sale does not exist.")

        car_id, quantity, unit_price = order

        if unit_price is None:
            raise ValueError("This sale has no saved unit price.")

        car = connection.execute("""
            SELECT brand, model
            FROM cars
            WHERE id = ?
        """, (car_id,)).fetchone()

        if car is None:
            raise ValueError("The car associated with this sale was not found.")

        cursor = connection.execute("""
            INSERT INTO invoices (
                invoice_number, order_id, customer_name,
                customer_phone, customer_email, customer_address
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            invoice_number,
            order_id,
            (customer_name or "").strip(),
            (customer_phone or "").strip(),
            (customer_email or "").strip(),
            (customer_address or "").strip()
        ))

        invoice_id = cursor.lastrowid

        connection.execute("""
            INSERT INTO invoice_items (
                invoice_id, car_id, description, quantity, unit_price
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            invoice_id,
            car_id,
            f"{car[0]} {car[1]}",
            quantity,
            unit_price
        ))

        connection.commit()
        return invoice_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
def get_financial_summary(start_date=None, end_date=None):
    """Calculate sales revenue, COGS, gross profit, expenses, and net operating profit."""
    conn = get_connection()

    try:
        sales_query = """
            SELECT
                COALESCE(SUM(quantity * unit_price), 0) AS total_revenue,
                COALESCE(SUM(quantity * unit_cost), 0) AS total_cogs,
                COUNT(*) AS total_orders,
                COALESCE(SUM(quantity), 0) AS units_sold
            FROM orders
            WHERE unit_price IS NOT NULL
        """
        sales_params = []

        if start_date:
            sales_query += " AND date(order_date) >= date(?)"
            sales_params.append(str(start_date))

        if end_date:
            sales_query += " AND date(order_date) <= date(?)"
            sales_params.append(str(end_date))

        sales = conn.execute(sales_query, sales_params).fetchone()
        sales = {
    "total_revenue": sales[0],
    "total_cogs": sales[1],
    "total_orders": sales[2],
    "units_sold": sales[3],
}

        expense_query = """
            SELECT COALESCE(SUM(amount), 0)
            FROM expenses
            WHERE 1=1
        """
        expense_params = []

        if start_date:
            expense_query += " AND date(expense_date) >= date(?)"
            expense_params.append(str(start_date))

        if end_date:
            expense_query += " AND date(expense_date) <= date(?)"
            expense_params.append(str(end_date))

        total_expenses = conn.execute(
            expense_query, expense_params
        ).fetchone()[0]

        revenue = float(sales["total_revenue"] or 0)
        cogs = float(sales["total_cogs"] or 0)
        gross_profit = revenue - cogs
        total_expenses = float(total_expenses or 0)

        return {
            "total_revenue": revenue,
            "total_cogs": cogs,
            "gross_profit": gross_profit,
            "operating_expenses": total_expenses,
            "net_operating_profit": gross_profit - total_expenses,
            "total_orders": int(sales["total_orders"] or 0),
            "units_sold": int(sales["units_sold"] or 0),
        }
    finally:
        conn.close()


def get_financial_details(start_date=None, end_date=None):
    """Return detailed sales, stock purchase, and expense records for Excel reports."""
    import pandas as pd

    conn = get_connection()

    try:
        sales_query = """
            SELECT
                o.id AS order_id,
                o.order_date,
                c.brand,
                c.model,
                o.quantity,
                o.source,
                o.city,
                o.unit_price,
                o.unit_cost,
                (o.quantity * o.unit_price) AS revenue,
                (o.quantity * o.unit_cost) AS cogs,
                (o.quantity * (o.unit_price - o.unit_cost)) AS gross_profit
            FROM orders o
            LEFT JOIN cars c ON c.id = o.car_id
            WHERE o.unit_price IS NOT NULL
        """
        sales_params = []

        if start_date:
            sales_query += " AND date(o.order_date) >= date(?)"
            sales_params.append(str(start_date))

        if end_date:
            sales_query += " AND date(o.order_date) <= date(?)"
            sales_params.append(str(end_date))

        sales_query += " ORDER BY o.order_date DESC"

        purchases_query = """
            SELECT
                p.id AS purchase_id,
                p.purchase_date,
                p.supplier,
                c.brand,
                c.model,
                p.quantity,
                p.unit_cost,
                (p.quantity * p.unit_cost) AS purchase_total,
                p.notes
            FROM purchases p
            LEFT JOIN cars c ON c.id = p.car_id
            WHERE 1=1
        """
        purchase_params = []

        if start_date:
            purchases_query += " AND date(p.purchase_date) >= date(?)"
            purchase_params.append(str(start_date))

        if end_date:
            purchases_query += " AND date(p.purchase_date) <= date(?)"
            purchase_params.append(str(end_date))

        purchases_query += " ORDER BY p.purchase_date DESC"

        expenses_query = """
            SELECT
                id AS expense_id,
                expense_date,
                category,
                description,
                amount,
                payment_method,
                notes
            FROM expenses
            WHERE 1=1
        """
        expense_params = []

        if start_date:
            expenses_query += " AND date(expense_date) >= date(?)"
            expense_params.append(str(start_date))

        if end_date:
            expenses_query += " AND date(expense_date) <= date(?)"
            expense_params.append(str(end_date))

        expenses_query += " ORDER BY expense_date DESC"

        sales_df = pd.read_sql_query(sales_query, conn, params=sales_params)
        purchases_df = pd.read_sql_query(
            purchases_query, conn, params=purchase_params
        )
        expenses_df = pd.read_sql_query(
            expenses_query, conn, params=expense_params
        )

        return sales_df, purchases_df, expenses_df
    finally:
        conn.close()
def get_invoiceable_sales():
    """Retrieve existing sales for invoice generation without modifying data."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                o.id AS order_id,
                o.order_date,
                o.quantity,
                o.unit_price,
                c.brand,
                c.model
            FROM orders o
            LEFT JOIN cars c ON c.id = o.car_id
            WHERE o.unit_price IS NOT NULL
            ORDER BY o.id DESC
        """).fetchall()

        return [
            {
                "order_id": row[0],
                "order_date": row[1],
                "quantity": row[2],
                "unit_price": row[3],
                "brand": row[4],
                "model": row[5],
            }
            for row in rows
        ]
    finally:
        conn.close()
