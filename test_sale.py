from db import get_connection, log_order

# Choose an existing car with available stock
car_id = 2

# Check the current stock before the test
connection = get_connection()
cursor = connection.cursor()

cursor.execute(
    "SELECT model, stock FROM cars WHERE id = ?",
    (car_id,)
)

car = cursor.fetchone()
connection.close()

if car is None:
    print("Car not found.")
elif car[1] < 1:
    print("This car is out of stock. Choose another car ID.")
else:
    print(f"Testing sale: {car[0]}")
    print(f"Stock before sale: {car[1]}")

    log_order(
        car_id=car_id,
        quantity=1,
        source="Test",
        city="Kochi"
    )