import sqlite3
from db import get_connection


def update_car(car_id, brand, model, price, cost, stock, condition):
    """Update an existing car without changing its sales history."""

    if not brand.strip():
        raise ValueError("Brand cannot be empty.")

    if not model.strip():
        raise ValueError("Model cannot be empty.")

    if price <= 0:
        raise ValueError("Selling price must be greater than zero.")

    if cost < 0:
        raise ValueError("Cost price cannot be negative.")

    if stock < 0:
        raise ValueError("Stock cannot be negative.")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE cars
            SET brand = ?, model = ?, price = ?, cost = ?,
                stock = ?, condition = ?
            WHERE id = ?
            """,
            (
                brand.strip(),
                model.strip(),
                price,
                cost,
                stock,
                condition,
                car_id,
            ),
        )

        if cursor.rowcount == 0:
            raise ValueError("Car not found.")

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def delete_car(car_id):
    """Delete a car only if it has no sales history."""

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT id FROM cars WHERE id = ?",
            (car_id,),
        )

        if cursor.fetchone() is None:
            raise ValueError("Car not found.")

        cursor.execute(
            "SELECT COUNT(*) FROM orders WHERE car_id = ?",
            (car_id,),
        )

        sales_count = cursor.fetchone()[0]

        if sales_count > 0:
            raise ValueError(
                "This car has sales history and cannot be deleted."
            )

        cursor.execute(
            "DELETE FROM cars WHERE id = ?",
            (car_id,),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
