from db import check_low_stock


def display_low_stock_report():
    low_stock_cars = check_low_stock()

    print("\n===== LOW-STOCK REPORT =====")

    if not low_stock_cars:
        print("All cars have sufficient stock.")
    else:
        for car in low_stock_cars:
            car_id, brand, model, stock = car

            print(
                f"ID: {car_id} | "
                f"Brand: {brand} | "
                f"Model: {model} | "
                f"Remaining stock: {stock} | "
                f"Status: LOW STOCK"
            )


if __name__ == "__main__":
    display_low_stock_report()