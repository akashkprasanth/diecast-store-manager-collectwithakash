from db import get_connection


def get_sales_analytics():
    with get_connection() as connection:
        result = connection.execute("""
            SELECT
                COALESCE(SUM(quantity * unit_price), 0),
                COALESCE(SUM(quantity * unit_cost), 0),
                COALESCE(
                    SUM(quantity * (unit_price - unit_cost)),
                    0
                )
            FROM orders
            WHERE unit_price IS NOT NULL
              AND unit_cost IS NOT NULL
        """).fetchone()

    return result