from db import get_connection


def get_sales_analytics():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            COALESCE(SUM(quantity * unit_price), 0),
            COALESCE(SUM(quantity * unit_cost), 0),
            COALESCE(SUM(quantity * (unit_price - unit_cost)), 0)
        FROM orders
        WHERE unit_price IS NOT NULL
          AND unit_cost IS NOT NULL
    """)

    revenue, cost, profit = cursor.fetchone()

    connection.close()

    return revenue, cost, profit