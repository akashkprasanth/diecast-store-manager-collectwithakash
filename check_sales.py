from db import get_connection

connection = get_connection()
cursor = connection.cursor()

cursor.execute("""
    SELECT
        id,
        car_id,
        quantity,
        source,
        city,
        order_date,
        unit_price,
        unit_cost
    FROM orders
""")

sales = cursor.fetchall()

print("\n===== SALES RECORDS =====")

for sale in sales:
    print(sale)

connection.close()