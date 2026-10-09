"""
Diecast Store Manager
Database setup
"""

import sqlite3

# Database filename
DB_NAME = "diecast_store.db"


def get_connection():
    """Connect to the SQLite database."""
    return sqlite3.connect(DB_NAME)


def init_db():
    """Create the cars and orders tables."""

    connection = get_connection()
    cursor = connection.cursor()

    # Create the cars table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT NOT NULL,
            model TEXT NOT NULL,
            price REAL NOT NULL,
            cost REAL NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            condition TEXT NOT NULL,
            image_url TEXT
        )
    """)

    # Create the orders table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            source TEXT,
            city TEXT,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (car_id) REFERENCES cars(id)
        )
    """)

    connection.commit()
    connection.close()

    print("Database created successfully!")
    print("Cars and orders tables are ready.")


def add_car(brand, model, price, cost, stock, condition, image_url=""):
    """Add a new car to the inventory database."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO cars
        (brand, model, price, cost, stock, condition, image_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (brand, model, price, cost, stock, condition, image_url)
    )

    car_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return car_id

def log_order(car_id, quantity, source="", city=""):
    """Record a sale, save its price and cost, and reduce stock."""

    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    connection = get_connection()
    cursor = connection.cursor()

    try:
        # Get the car's current stock, price, and cost
        cursor.execute(
            """
            SELECT stock, price, cost
            FROM cars
            WHERE id = ?
            """,
            (car_id,)
        )

        car = cursor.fetchone()

        # Check whether the car exists
        if car is None:
            raise ValueError("Car not found.")

        current_stock, unit_price, unit_cost = car

        # Prevent overselling
        if quantity > current_stock:
            raise ValueError(
                f"Only {current_stock} car(s) available."
            )

        # Save the sale with its price and cost
        cursor.execute(
            """
            INSERT INTO orders
            (car_id, quantity, source, city, unit_price, unit_cost)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                car_id,
                quantity,
                source,
                city,
                unit_price,
                unit_cost
            )
        )

        # Reduce the available stock
        cursor.execute(
            """
            UPDATE cars
            SET stock = stock - ?
            WHERE id = ?
            """,
            (quantity, car_id)
        )

        connection.commit()

        print("Order recorded successfully!")
        print(f"Quantity sold: {quantity}")
        print(f"Sale price per car: ₹{unit_price:.2f}")
        print(f"Purchase cost per car: ₹{unit_cost:.2f}")
        print(f"Remaining stock: {current_stock - quantity}")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def update_orders_table():
    """Add price and cost columns to the orders table."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("PRAGMA table_info(orders)")
    columns = [column[1] for column in cursor.fetchall()]

    if "unit_price" not in columns:
        cursor.execute(
            "ALTER TABLE orders ADD COLUMN unit_price REAL"
        )

    if "unit_cost" not in columns:
        cursor.execute(
            "ALTER TABLE orders ADD COLUMN unit_cost REAL"
        )

    connection.commit()
    connection.close()

    print("Orders table updated successfully!")

def check_orders_columns():
    """Display the columns in the orders table."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("PRAGMA table_info(orders)")
    columns = cursor.fetchall()

    print("\n===== ORDERS TABLE COLUMNS =====")

    for column in columns:
        print(column[1])

    connection.close()

def calculate_inventory_value():
    """Calculate the value of the current inventory."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            SUM(cost * stock),
            SUM(price * stock),
            SUM((price - cost) * stock)
        FROM cars
    """)

    result = cursor.fetchone()

    connection.close()

    total_cost_value = result[0] or 0
    potential_sales_value = result[1] or 0
    potential_gross_profit = result[2] or 0

    print("\n===== INVENTORY VALUATION =====")
    print(f"Total cost value: ₹{total_cost_value:.2f}")
    print(f"Potential sales value: ₹{potential_sales_value:.2f}")
    print(f"Potential gross profit: ₹{potential_gross_profit:.2f}")

def check_low_stock(threshold=3):
    """Display cars with stock below the specified threshold."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, brand, model, stock
        FROM cars
        WHERE stock < ?
        ORDER BY stock ASC
        """,
        (threshold,)
    )

    low_stock_cars = cursor.fetchall()

    connection.close()

    print("\n===== LOW-STOCK ALERT =====")

    if not low_stock_cars:
        print("No cars are running low on stock.")
    else:
        for car in low_stock_cars:
            print(
                f"ID: {car[0]} | "
                f"Brand: {car[1]} | "
                f"Model: {car[2]} | "
                f"Remaining stock: {car[3]}"
            )

if __name__ == "__main__":
    init_db()
    update_orders_table()

    connection = get_connection()
    cursor = connection.cursor()

    # Display inventory
    cursor.execute("SELECT * FROM cars")
    cars = cursor.fetchall()

    print("\n===== CURRENT INVENTORY =====")

    for car in cars:
        print(car)

    # Display orders
    cursor.execute("SELECT * FROM orders")
    orders = cursor.fetchall()

    print("\n===== SALES HISTORY =====")

    for order in orders:
        print(order)

    connection.close()

    calculate_inventory_value()

    check_low_stock()

    