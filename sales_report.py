from db import get_connection


def calculate_sales_summary():
    """Calculate total sales revenue and gross profit."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            SUM(quantity * unit_price),
            SUM(quantity * unit_cost)
        FROM orders
        WHERE unit_price IS NOT NULL
          AND unit_cost IS NOT NULL
    """)

    result = cursor.fetchone()

    connection.close()

    total_revenue = result[0] or 0
    total_cost = result[1] or 0

    gross_profit = total_revenue - total_cost

    print("\n===== SALES SUMMARY =====")
    print(f"Total Revenue: ₹{total_revenue:.2f}")
    print(f"Total Cost: ₹{total_cost:.2f}")
    print(f"Gross Profit: ₹{gross_profit:.2f}")


if __name__ == "__main__":
    calculate_sales_summary()