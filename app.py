import streamlit as st
import pandas as pd
from db import get_connection, add_car, log_order, calculate_inventory_value
from inventory_management import update_car, delete_car
from sales_analytics import get_sales_analytics
from best_sellers import get_best_sellers


# Get inventory from the database
def get_inventory():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM cars")
    cars = cursor.fetchall()

    connection.close()
    return cars


# Dashboard title
st.title("CollectWithAkash - Diecast Store Manager")

st.write("Manage your diecast inventory, sales, and profits in one place.")


# Low-Stock Alerts
st.header("Low-Stock Alerts")

low_stock_threshold = st.number_input(
    "Alert when stock is at or below",
    min_value=0,
    max_value=100,
    value=3,
    step=1,
    key="low_stock_threshold",
)

low_stock_connection = get_connection()
try:
    low_stock_cursor = low_stock_connection.cursor()
    low_stock_cursor.execute("""
        SELECT id, brand, model, stock
        FROM cars
        WHERE stock <= ?
        ORDER BY stock ASC, brand ASC, model ASC
    """, (int(low_stock_threshold),))
    low_stock_cars = low_stock_cursor.fetchall()
finally:
    low_stock_connection.close()

if low_stock_cars:
    low_stock_df = pd.DataFrame(
        low_stock_cars,
        columns=["ID", "Brand", "Model", "Units Remaining"],
    )
    st.warning(f"{len(low_stock_cars)} car model(s) need attention.")
    st.dataframe(low_stock_df, use_container_width=True, hide_index=True)
else:
    st.success("No low-stock alerts. Your inventory is above the selected threshold.")

# Stock Overview
st.header("Stock Overview")

inventory_connection = get_connection()
try:
    inventory_cursor = inventory_connection.cursor()
    inventory_cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(stock), 0)
        FROM cars
    """)
    total_models, total_units = inventory_cursor.fetchone()
finally:
    inventory_connection.close()

inventory_cost, potential_sales, potential_profit = calculate_inventory_value()

metric1, metric2, metric3, metric4 = st.columns(4)
metric1.metric("Total Car Models", f"{total_models:,}")
metric2.metric("Total Units in Stock", f"{total_units:,}")
metric3.metric("Inventory Cost Value", f"\u20b9{inventory_cost:,.2f}")
metric4.metric("Potential Sales Value", f"\u20b9{potential_sales:,.2f}")

st.caption(f"Potential gross profit on current stock: \u20b9{potential_profit:,.2f}")


# Sidebar
st.sidebar.title("Navigation")
st.sidebar.write("Select a section to manage your store.")

# Retrieve inventory ONCE
cars = get_inventory()


# Sales Analytics
st.header("Sales Analytics")

revenue, cost, profit = get_sales_analytics()

col1, col2, col3 = st.columns(3)

col1.metric("Total Revenue", f"₹{revenue:,.2f}")
col2.metric("Total Cost", f"₹{cost:,.2f}")
col3.metric("Gross Profit", f"₹{profit:,.2f}")

# Best-Selling Cars
st.header("Best-Selling Cars")

best_sellers = get_best_sellers()

if best_sellers:
    import pandas as pd

    best_sellers_df = pd.DataFrame(
        best_sellers,
        columns=["Brand", "Model", "Units Sold"]
    )

    st.dataframe(
        best_sellers_df,
        hide_index=True,
        width="stretch"
    )
else:
    st.info("No sales recorded yet.")

# Inventory summary
st.subheader("Inventory Overview")

if cars:
    total_cars = len(cars)
    total_stock = sum(car[5] for car in cars)
    inventory_value = sum(car[4] * car[5] for car in cars)

    col1, col2, col3 = st.columns(3)

    col1.metric("Total Car Records", total_cars)
    col2.metric("Total Stock", total_stock)
    col3.metric("Inventory Cost Value", f"₹{inventory_value:.2f}")
else:
    st.info("Your inventory is empty.")

# Add a new car
st.header("Add New Car")

with st.form("add_car_form"):
    brand = st.selectbox(
        "Brand",
        ["Hot Wheels", "Mini GT", "Majorette", "Matchbox", "Other"]
    )

    model = st.text_input("Car Model")

    price = st.number_input(
        "Selling Price (₹)",
        min_value=0.0,
        step=1.0
    )

    cost = st.number_input(
        "Cost Price (₹)",
        min_value=0.0,
        step=1.0
    )

    stock = st.number_input(
        "Stock Quantity",
        min_value=0,
        step=1
    )

    condition = st.selectbox(
        "Condition",
        ["New", "Used"]
    )

    submitted = st.form_submit_button("Add Car")

    if submitted:
        if not model.strip():
            st.error("Please enter the car model.")

        elif price <= 0:
            st.error("Selling price must be greater than zero.")

        elif cost < 0:
            st.error("Cost price cannot be negative.")

        else:
            try:
                add_car(
                    brand,
                    model.strip(),
                    price,
                    cost,
                    stock,
                    condition
                )

                st.success(f"{model} added successfully!")
                st.rerun()

            except Exception as e:
                st.error(f"Could not add car: {e}")

# Record a sale
st.header("Record a Sale")

if cars:
    car_options = {
        f"{car[1]} - {car[2]} (Stock: {car[5]})": car[0]
        for car in cars
        if car[5] > 0
    }

    if car_options:
        with st.form("record_sale_form"):
            selected_car = st.selectbox(
                "Select Car",
                list(car_options.keys())
            )

            quantity = st.number_input(
                "Quantity Sold",
                min_value=1,
                step=1
            )

            source = st.selectbox(
                "Order Source",
                ["Instagram", "Telegram", "Website", "Other"]
            )

            city = st.text_input("Customer City")

            submitted_sale = st.form_submit_button("Record Sale")

            if submitted_sale:
                try:
                    car_id = car_options[selected_car]

                    log_order(
                        car_id,
                        int(quantity),
                        source,
                        city.strip()
                    )

                    st.success("Sale recorded and stock updated!")
                    st.rerun()

                except Exception as e:
                    st.error(f"Could not record sale: {e}")
    else:
        st.info("No cars currently in stock.")
else:
    st.info("Add a car before recording a sale.")

# Search and filter inventory
st.subheader("Search Inventory")

search_term = st.text_input(
    "Search by brand or model",
    placeholder="Example: Ferrari or Hot Wheels"
)

if search_term:
    filtered_cars = [
        car for car in cars
        if search_term.lower() in car[1].lower()
        or search_term.lower() in car[2].lower()
    ]
else:
    filtered_cars = cars

# Inventory table
st.header("Car Inventory")

if cars:
    column_names = [
        "ID",
        "Brand",
        "Model",
        "Selling Price",
        "Cost Price",
        "Stock",
        "Condition",
        "Notes"
    ]

    inventory_df = pd.DataFrame(filtered_cars, columns=column_names)

    st.dataframe(
        inventory_df,
        hide_index=True,
        width="stretch"
    )

# ==========================================
# EDIT AND DELETE INVENTORY
# ==========================================

st.divider()
st.header("Manage Existing Inventory")

if cars:
    edit_options = {
        f"ID {car[0]} - {car[1]} {car[2]}": car
        for car in cars
    }

    selected_label = st.selectbox(
        "Choose a car to manage",
        list(edit_options.keys()),
        key="manage_car_select",
    )

    selected_car = edit_options[selected_label]

    st.subheader("Edit Car Details")

    with st.form("edit_car_form"):
        edit_brand = st.text_input(
            "Brand",
            value=selected_car[1],
        )

        edit_model = st.text_input(
            "Model",
            value=selected_car[2],
        )

        edit_price = st.number_input(
            "Selling Price (INR)",
            min_value=0.01,
            value=max(float(selected_car[3]), 0.01),
            step=1.0,
        )

        edit_cost = st.number_input(
            "Cost Price (INR)",
            min_value=0.0,
            value=max(float(selected_car[4]), 0.0),
            step=1.0,
        )

        edit_stock = st.number_input(
            "Stock Quantity",
            min_value=0,
            value=max(int(selected_car[5]), 0),
            step=1,
        )

        edit_condition = st.selectbox(
            "Condition",
            ["New", "Used"],
            index=0 if selected_car[6] == "New" else 1,
        )

        save_changes = st.form_submit_button("Save Changes")

        if save_changes:
            try:
                update_car(
                    selected_car[0],
                    edit_brand,
                    edit_model,
                    edit_price,
                    edit_cost,
                    int(edit_stock),
                    edit_condition,
                )

                st.success("Car details updated successfully!")
                st.rerun()

            except Exception as error:
                st.error(f"Could not update car: {error}")

    st.divider()
    st.subheader("Delete Car")

    st.warning(
        "Cars with existing sales history cannot be deleted."
    )

    confirm_delete = st.checkbox(
        "I understand that deleting a car cannot be undone.",
        key="confirm_delete_car",
    )

    if st.button("Delete Selected Car", type="secondary"):
        if not confirm_delete:
            st.warning("Please confirm before deleting this car.")
        else:
            try:
                delete_car(selected_car[0])
                st.success("Car deleted successfully!")
                st.rerun()

            except Exception as error:
                st.error(f"Could not delete car: {error}")

else:
    st.info("Add a car before managing inventory.")
