from db import get_connection

def get_profit_analysis():
    connection = get_connection()

    query = """
        SELECT
            cars.brand,
            cars.model,
            SUM(orders.quantity) AS units_sold,
            SUM(orders.quantity * orders.unit_price) AS total_revenue,
            SUM(orders.quantity * orders.unit_cost) AS total_cost,
            SUM(orders.quantity * (orders.unit_price - orders.unit_cost)) AS gross_profit
        FROM orders
        JOIN cars ON orders.car_id = cars.id
        WHERE orders.unit_price IS NOT NULL
          AND orders.unit_cost IS NOT NULL
        GROUP BY cars.brand, cars.model
        ORDER BY gross_profit DESC;
    """

    cursor = connection.cursor()
    cursor.execute(query)

    results = cursor.fetchall()

    connection.close()

    return results

if __name__ == "__main__":
    profit_data = get_profit_analysis()

    print("\n===== PROFIT ANALYSIS BY CAR MODEL =====")

    if not profit_data:
        print("No sales data available for profit analysis.")
    else:
        for car in profit_data:
            brand, model, units_sold, revenue, cost, profit = car

            print(f"Brand: {brand}")
            print(f"Model: {model}")
            print(f"Units Sold: {units_sold}")
            print(f"Total Revenue: ₹{revenue:.2f}")
            print(f"Total Cost: ₹{cost:.2f}")
            print(f"Gross Profit: ₹{profit:.2f}")
            print("-" * 35)