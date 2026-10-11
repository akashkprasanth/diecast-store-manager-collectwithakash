import sqlite3
from db import get_connection

def get_best_sellers():
    connection = get_connection()

    query = """
    SELECT
        cars.brand,
        cars.model,
        SUM(orders.quantity) AS total_sold
    FROM orders
    LEFT JOIN cars ON orders.car_id = cars.id
    GROUP BY cars.brand, cars.model
    ORDER BY total_sold DESC;
"""

    cursor = connection.cursor()
    cursor.execute(query)

    results = cursor.fetchall()

    connection.close()

    return results

if __name__ == "__main__":
    best_sellers = get_best_sellers()

    print("\n===== BEST-SELLING CARS =====")

    if not best_sellers:
        print("No sales recorded yet.")
    else:
        for car in best_sellers:
            brand, model, total_sold = car

            print(f"Brand: {brand}")
            print(f"Model: {model}")
            print(f"Total Sold: {total_sold}")
            print("-" * 30)