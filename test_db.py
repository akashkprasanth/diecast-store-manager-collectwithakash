import pytest
import db


@pytest.fixture
def temporary_database(tmp_path, monkeypatch):
    """Use an isolated SQLite database for each test."""
    database_path = tmp_path / "test_store.db"
    monkeypatch.setattr(db, "DB_NAME", str(database_path))

    db.init_db()
    db.update_orders_table()
    db.init_purchases_table()

    return database_path


def add_test_car(stock=5, price=100.0, cost=60.0):
    """Create a car in the isolated test database."""
    return db.add_car(
        brand="Test Brand",
        model="Test Model",
        price=price,
        cost=cost,
        stock=stock,
        condition="New",
    )


def test_add_car_returns_id(temporary_database):
    car_id = add_test_car()

    assert car_id > 0


def test_inventory_value(temporary_database):
    add_test_car(stock=5, price=100.0, cost=60.0)

    cost_value, sales_value, gross_profit = db.calculate_inventory_value()

    assert cost_value == pytest.approx(300.0)
    assert sales_value == pytest.approx(500.0)
    assert gross_profit == pytest.approx(200.0)


def test_low_stock_detection(temporary_database):
    add_test_car(stock=2)

    low_stock_cars = db.check_low_stock(threshold=3)

    assert len(low_stock_cars) == 1
    assert low_stock_cars[0][3] == 2


def test_purchase_increases_stock(temporary_database):
    car_id = add_test_car(stock=2)

    purchase_id = db.record_purchase(
        car_id=car_id,
        quantity=3,
        unit_cost=50.0,
        supplier="Test Supplier",
    )

    assert purchase_id > 0

    connection = db.get_connection()
    try:
        result = connection.execute(
            "SELECT stock FROM cars WHERE id = ?",
            (car_id,),
        ).fetchone()
    finally:
        connection.close()

    assert result[0] == 5


def test_sale_reduces_stock(temporary_database):
    car_id = add_test_car(stock=5)

    db.log_order(car_id, quantity=2)

    connection = db.get_connection()
    try:
        result = connection.execute(
            "SELECT stock FROM cars WHERE id = ?",
            (car_id,),
        ).fetchone()
    finally:
        connection.close()

    assert result[0] == 3


def test_sale_rejects_overselling(temporary_database):
    car_id = add_test_car(stock=2)

    with pytest.raises(ValueError, match="Only 2 car"):
        db.log_order(car_id, quantity=3)

    connection = db.get_connection()
    try:
        stock = connection.execute(
            "SELECT stock FROM cars WHERE id = ?",
            (car_id,),
        ).fetchone()[0]

        order_count = connection.execute(
            "SELECT COUNT(*) FROM orders"
        ).fetchone()[0]
    finally:
        connection.close()

    assert stock == 2
    assert order_count == 0


def test_sale_rejects_zero_quantity(temporary_database):
    car_id = add_test_car()

    with pytest.raises(ValueError, match="greater than zero"):
        db.log_order(car_id, quantity=0)


def test_purchase_rejects_invalid_quantity(temporary_database):
    car_id = add_test_car()

    with pytest.raises(ValueError, match="positive whole number"):
        db.record_purchase(
            car_id=car_id,
            quantity=0,
            unit_cost=50.0,
        )
