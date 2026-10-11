import streamlit as st
import pandas as pd
from db import get_connection, add_car, log_order, calculate_inventory_value, record_purchase, init_purchases_table
from inventory_management import update_car, delete_car
from sales_analytics import get_sales_analytics
from best_sellers import get_best_sellers
from business_features import (
    init_business_tables,
    add_supplier,
    add_expense,
    get_expenses,
    get_supplier_spending,
    create_invoice,
    get_financial_summary,
    get_financial_details,
    get_invoiceable_sales,
)

from invoice_generator import generate_invoice_pdf


# Get inventory from the database
def get_inventory():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM cars")
    cars = cursor.fetchall()

    connection.close()
    return cars


# Dashboard title
# Ensure the stock purchases table exists.
init_purchases_table()
init_business_tables()

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

# Stock Purchases & Restocking
st.divider()
st.header("Stock Purchases & Restocking")
st.write("Record new stock purchases and track your restocking costs.")

connection = get_connection()
try:
    purchase_cars = connection.execute(
        "SELECT id, brand, model, stock FROM cars ORDER BY brand, model"
    ).fetchall()

    purchase_history = connection.execute("""
        SELECT
            p.id AS Purchase_ID,
            p.purchase_date AS Purchase_Date,
            c.brand AS Brand,
            c.model AS Model,
            p.quantity AS Quantity,
            p.unit_cost AS Unit_Cost,
            p.quantity * p.unit_cost AS Total_Cost,
            p.supplier AS Supplier,
            p.notes AS Notes
        FROM purchases p
        JOIN cars c ON c.id = p.car_id
        ORDER BY p.id DESC
    """).fetchall()
finally:
    connection.close()

if not purchase_cars:
    st.info("Add a car to your inventory before recording a stock purchase.")
else:
    car_options = {
        f"ID {car[0]} - {car[1]} {car[2]} (Current stock: {car[3]})": car[0]
        for car in purchase_cars
    }

    with st.form("stock_purchase_form"):
        selected_car = st.selectbox(
            "Select diecast model",
            options=list(car_options.keys())
        )
        purchase_quantity = st.number_input(
            "Quantity purchased",
            min_value=1,
            value=1,
            step=1
        )
        purchase_unit_cost = st.number_input(
            "Cost per unit (\u20b9)",
            min_value=0.0,
            value=0.0,
            step=10.0,
            format="%.2f"
        )
        purchase_supplier = st.text_input("Supplier")
        purchase_date = st.date_input("Purchase date")
        purchase_notes = st.text_area("Notes (optional)")

        purchase_submitted = st.form_submit_button(
            "Record Purchase & Restock",
            type="primary"
        )

    if purchase_submitted:
        try:
            purchase_id = record_purchase(
                car_id=int(car_options[selected_car]),
                quantity=int(purchase_quantity),
                unit_cost=float(purchase_unit_cost),
                supplier=purchase_supplier,
                purchase_date=purchase_date,
                notes=purchase_notes
            )
            st.success(
                f"Purchase #{purchase_id} recorded. "
                f"{int(purchase_quantity)} unit(s) added to inventory."
            )
            st.rerun()
        except (ValueError, TypeError) as error:
            st.error(str(error))
        except Exception as error:
            st.error(f"Could not record purchase: {error}")

st.subheader("Purchase History")

if purchase_history:
    purchase_df = pd.DataFrame(
        [tuple(row) for row in purchase_history],
        columns=[
            "Purchase ID",
            "Date",
            "Brand",
            "Model",
            "Quantity",
            "Unit Cost (INR)",
            "Total Cost (INR)",
            "Supplier",
            "Notes"
        ]
    )
    st.dataframe(
        purchase_df,
        use_container_width=True,
        hide_index=True
    )
    st.metric(
        "Total Recorded Purchase Cost",
        f"INR {purchase_df['Total Cost (INR)'].sum():,.2f}"
    )
else:
    st.info("No stock purchases have been recorded yet.")


# Business Management
st.divider()
st.header("Business Management")

supplier_tab, expense_tab, expense_report_tab = st.tabs([
    "Suppliers",
    "Expenses",
    "Expense Summary"
])

with supplier_tab:
    st.subheader("Add Supplier")

    with st.form("add_supplier_form"):
        supplier_name = st.text_input("Supplier name")
        supplier_phone = st.text_input("Phone number")
        supplier_email = st.text_input("Email address")
        supplier_address = st.text_area("Address")
        supplier_notes = st.text_area("Supplier notes")

        supplier_submitted = st.form_submit_button("Add Supplier")

    if supplier_submitted:
        try:
            supplier_id = add_supplier(
                supplier_name,
                supplier_phone,
                supplier_email,
                supplier_address,
                supplier_notes
            )
            st.success(f"Supplier added successfully. ID: {supplier_id}")
            st.rerun()
        except (ValueError, TypeError) as error:
            st.error(str(error))

    with get_connection() as connection:
        suppliers = connection.execute("""
            SELECT id, name, phone, email, address, notes
            FROM suppliers
            ORDER BY name
        """).fetchall()

    st.subheader("Supplier Directory")

    if suppliers:
        st.dataframe(
            pd.DataFrame(
                [tuple(row) for row in suppliers],
                columns=[
                    "ID", "Supplier", "Phone", "Email", "Address", "Notes"
                ]
            ),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No suppliers have been added yet.")

    st.subheader("Historical Purchase Spending")

    supplier_spending = get_supplier_spending()

    if supplier_spending:
        spending_df = pd.DataFrame(
            supplier_spending,
            columns=["Supplier", "Purchase Count", "Total Spending"]
        )
        spending_df["Total Spending"] = spending_df["Total Spending"].map(
            lambda amount: f"INR {amount:,.2f}"
        )
        st.dataframe(
            spending_df,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No purchase spending is available.")

with expense_tab:
    st.subheader("Record Business Expense")

    with st.form("add_expense_form"):
        expense_date = st.date_input("Expense date")
        expense_category = st.selectbox(
            "Category",
            [
                "Packaging",
                "Shipping",
                "Advertising",
                "Storage",
                "Utilities",
                "Office Supplies",
                "Other"
            ]
        )
        expense_description = st.text_input("Description")
        expense_amount = st.number_input(
            "Amount (INR)",
            min_value=0.0,
            value=0.0,
            step=10.0,
            format="%.2f"
        )
        expense_payment_method = st.selectbox(
            "Payment method",
            ["Cash", "Bank Transfer", "UPI", "Card", "Other"]
        )
        expense_notes = st.text_area("Notes (optional)")

        expense_submitted = st.form_submit_button("Save Expense")

    if expense_submitted:
        try:
            expense_id = add_expense(
                expense_date,
                expense_category,
                expense_description,
                expense_amount,
                expense_payment_method,
                expense_notes
            )
            st.success(f"Expense recorded successfully. ID: {expense_id}")
            st.rerun()
        except (ValueError, TypeError) as error:
            st.error(str(error))

    st.subheader("Expense History")

    expense_rows = get_expenses()

    if expense_rows:
        expense_df = pd.DataFrame(
            [tuple(row) for row in expense_rows],
            columns=[
                "ID", "Date", "Category", "Description",
                "Amount (INR)", "Payment Method", "Notes"
            ]
        )
        st.dataframe(
            expense_df,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No business expenses have been recorded yet.")

with expense_report_tab:
    st.subheader("Expense Summary")

    expense_rows = get_expenses()

    if expense_rows:
        summary_df = pd.DataFrame(
            [tuple(row) for row in expense_rows],
            columns=[
                "ID", "Date", "Category", "Description",
                "Amount", "Payment Method", "Notes"
            ]
        )

        total_expenses = float(summary_df["Amount"].sum())
        st.metric("Total Recorded Expenses", f"INR {total_expenses:,.2f}")

        category_summary = (
            summary_df.groupby("Category", as_index=False)["Amount"]
            .sum()
            .sort_values("Amount", ascending=False)
        )

        st.dataframe(
            category_summary,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Record expenses to see a summary by category.")

# =========================
# FINANCIAL REPORTS
# =========================

st.header("Financial Reports")

with st.expander("Financial Reports & Excel Export", expanded=False):
    from datetime import date
    from io import BytesIO
    import pandas as pd

    report_col1, report_col2 = st.columns(2)

    with report_col1:
        report_start_date = st.date_input(
            "Report Start Date",
            value=date(date.today().year, 1, 1),
            key="financial_report_start",
        )

    with report_col2:
        report_end_date = st.date_input(
            "Report End Date",
            value=date.today(),
            key="financial_report_end",
        )

    if report_start_date > report_end_date:
        st.error("Start date must be on or before the end date.")
    else:
        financial_data = get_financial_summary(
            report_start_date,
            report_end_date,
        )

        st.subheader("Profit & Loss Summary")

        metric1, metric2, metric3 = st.columns(3)

        metric1.metric(
            "Sales Revenue",
            f"INR {financial_data['total_revenue']:,.2f}",
        )
        metric2.metric(
            "Cost of Goods Sold",
            f"INR {financial_data['total_cogs']:,.2f}",
        )
        metric3.metric(
            "Gross Profit",
            f"INR {financial_data['gross_profit']:,.2f}",
        )

        metric4, metric5, metric6 = st.columns(3)

        metric4.metric(
            "Operating Expenses",
            f"INR {financial_data['operating_expenses']:,.2f}",
        )
        metric5.metric(
            "Net Operating Profit",
            f"INR {financial_data['net_operating_profit']:,.2f}",
        )
        metric6.metric(
            "Units Sold",
            financial_data["units_sold"],
        )

        st.caption(
            f"Recorded orders: {financial_data['total_orders']}. "
            "Profit calculations use historical sale prices and costs. "
            "Stock purchases are reported separately and are not "
            "subtracted again from profit."
        )

        sales_df, purchases_df, expenses_df = get_financial_details(
            report_start_date,
            report_end_date,
        )

        st.subheader("Stock Purchase Summary")

        if purchases_df.empty:
            st.info("No stock purchases found for this date range.")
        else:
            purchase_total = purchases_df["purchase_total"].fillna(0).sum()
            st.metric(
                "Total Stock Purchases",
                f"INR {purchase_total:,.2f}",
            )
            st.dataframe(purchases_df, use_container_width=True)

        st.subheader("Sales Details")
        if sales_df.empty:
            st.info("No sales found for this date range.")
        else:
            st.dataframe(sales_df, use_container_width=True)

        st.subheader("Operating Expense Details")
        if expenses_df.empty:
            st.info("No operating expenses found for this date range.")
        else:
            st.dataframe(expenses_df, use_container_width=True)

        st.subheader("Export Reports to Excel")

        if st.button("Prepare Excel Report", key="prepare_financial_excel"):
            try:
                excel_buffer = BytesIO()

                summary_df = pd.DataFrame(
                    [
                        {
                            "Metric": "Sales Revenue",
                            "Amount (INR)": financial_data["total_revenue"],
                        },
                        {
                            "Metric": "Cost of Goods Sold",
                            "Amount (INR)": financial_data["total_cogs"],
                        },
                        {
                            "Metric": "Gross Profit",
                            "Amount (INR)": financial_data["gross_profit"],
                        },
                        {
                            "Metric": "Operating Expenses",
                            "Amount (INR)": financial_data["operating_expenses"],
                        },
                        {
                            "Metric": "Net Operating Profit",
                            "Amount (INR)": financial_data[
                                "net_operating_profit"
                            ],
                        },
                        {
                            "Metric": "Units Sold",
                            "Amount (INR)": financial_data["units_sold"],
                        },
                        {
                            "Metric": "Total Stock Purchases (separate)",
                            "Amount (INR)": (
                                purchases_df["purchase_total"].fillna(0).sum()
                                if not purchases_df.empty
                                else 0
                            ),
                        },
                    ]
                )

                with pd.ExcelWriter(
                    excel_buffer,
                    engine="openpyxl",
                ) as writer:
                    summary_df.to_excel(
                        writer,
                        sheet_name="Financial Summary",
                        index=False,
                    )
                    sales_df.to_excel(
                        writer,
                        sheet_name="Sales",
                        index=False,
                    )
                    purchases_df.to_excel(
                        writer,
                        sheet_name="Stock Purchases",
                        index=False,
                    )
                    expenses_df.to_excel(
                        writer,
                        sheet_name="Operating Expenses",
                        index=False,
                    )

                excel_buffer.seek(0)

                st.download_button(
                    label="Download Excel Report",
                    data=excel_buffer.getvalue(),
                    file_name=(
                        f"CollectWithAkash_Financial_Report_"
                        f"{report_start_date}_{report_end_date}.xlsx"
                    ),
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    key="download_financial_excel",
                )

            except Exception as exc:
                st.error(f"Could not prepare Excel report: {exc}")


# =========================
# INVOICE & RECEIPT GENERATION
# =========================

st.header("Invoice & Receipt Generation")

with st.expander("Generate a PDF Invoice from an Existing Sale", expanded=False):
    invoice_sales = get_invoiceable_sales()

    if not invoice_sales:
        st.info("No recorded sales are available for invoicing yet.")
    else:
        sale_options = {
            (
                f"Order #{row['order_id']} | "
                f"{row['brand'] or 'Unknown Brand'} "
                f"{row['model'] or ''} | "
                f"{row['order_date']} | "
                f"Qty: {row['quantity']} | "
                f"INR {float(row['unit_price']):,.2f} each"
            ): row
            for row in invoice_sales
        }

        selected_sale_label = st.selectbox(
            "Select an existing sale",
            options=list(sale_options.keys()),
            key="invoice_existing_sale",
        )
        selected_sale = sale_options[selected_sale_label]

        st.write(
            f"**Car:** {selected_sale['brand'] or 'Unknown Brand'} "
            f"{selected_sale['model'] or ''}"
        )
        st.write(f"**Order date:** {selected_sale['order_date']}")
        st.write(f"**Quantity:** {selected_sale['quantity']}")
        st.write(
            f"**Unit price:** INR {float(selected_sale['unit_price']):,.2f}"
        )
        st.write(
            "**Sale total:** "
            f"INR {int(selected_sale['quantity']) * float(selected_sale['unit_price']):,.2f}"
        )

        with st.form("invoice_customer_form"):
            st.subheader("Customer Details (Optional)")
            customer_name = st.text_input("Customer name")
            customer_phone = st.text_input("Phone number")
            customer_email = st.text_input("Email address")
            customer_address = st.text_area("Billing address")

            generate_invoice = st.form_submit_button("Generate PDF Invoice")

        if generate_invoice:
            try:
                from datetime import date
                import re

                order_id = int(selected_sale["order_id"])
                invoice_number = f"CWA-{date.today():%Y%m%d}-{order_id:06d}"

                pdf_bytes = generate_invoice_pdf(
                    invoice_number=invoice_number,
                    invoice_date=date.today().isoformat(),
                    customer_name=customer_name.strip(),
                    customer_phone=customer_phone.strip(),
                    customer_email=customer_email.strip(),
                    customer_address=customer_address.strip(),
                    car_brand=selected_sale["brand"] or "Diecast",
                    car_model=selected_sale["model"] or "Model",
                    quantity=selected_sale["quantity"],
                    unit_price=selected_sale["unit_price"],
                )

                safe_invoice_number = re.sub(
                    r"[^A-Za-z0-9_-]", "_", invoice_number
                )

                st.success(f"PDF invoice {invoice_number} generated.")
                st.download_button(
                    "Download PDF Invoice",
                    data=pdf_bytes,
                    file_name=f"{safe_invoice_number}.pdf",
                    mime="application/pdf",
                    key=f"download_invoice_{order_id}",
                )

                st.caption(
                    "This PDF is generated from the selected existing sale. "
                    "No sale, stock, or database invoice record was created."
                )
            except Exception as exc:
                st.error(f"Could not generate invoice: {exc}")


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
