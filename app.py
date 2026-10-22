import hmac
import os
import re
from urllib.parse import quote
from datetime import date, timedelta
from io import BytesIO

import pandas as pd
import streamlit as st

from db import (
    get_connection, add_car, log_order, calculate_inventory_value,
    record_purchase, init_purchases_table,
)
from inventory_management import update_car, delete_car
from sales_analytics import get_sales_analytics
from best_sellers import get_best_sellers
from business_features import (
    init_business_tables, add_supplier, add_expense, get_expenses,
    get_supplier_spending, get_financial_summary, get_financial_details,
    get_invoiceable_sales,
)
from invoice_generator import generate_invoice_pdf

st.set_page_config(page_title="Diecast Store Manager", page_icon="🏎️",
                   layout="wide", initial_sidebar_state="expanded")
init_purchases_table()
init_business_tables()
import web_orders as wo
wo.init_web_tables()

BRANDS = ["Hot Wheels", "Mini GT", "Majorette", "Matchbox", "Other"]
SOURCES = ["Instagram", "Telegram", "Website", "Other"]
CONDITIONS = ["New", "Used"]
EXPENSE_CATS = ["Packaging", "Shipping", "Advertising", "Storage", "Utilities", "Office Supplies", "Other"]
PAYMENTS = ["Cash", "Bank Transfer", "UPI", "Card", "Other"]
RS = "\u20b9{:,.2f}"

# ---------- Style ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Condensed:wght@600;700&display=swap');
:root { --asphalt:#1B1F24; --line:#DADDE1; --paper:#F2F3F5; --yellow:#FFC400; --red:#D7263D; --green:#1E8E5A; }
html, body, [class*="css"] { font-family:'Barlow',sans-serif; }
.stApp { background:var(--paper); }
h1,h2,h3 { font-family:'Barlow Condensed',sans-serif !important; color:var(--asphalt); }
h1 { font-size:2.8rem !important; margin-bottom:0; }
section[data-testid="stSidebar"] { background:var(--asphalt); }
section[data-testid="stSidebar"] * { color:#E8EAED !important; }
section[data-testid="stSidebar"] .stRadio label { padding:.35rem .2rem; font-size:1.05rem; }
.brand { font-family:'Barlow Condensed'; font-size:1.8rem; font-weight:700; color:var(--yellow) !important; }
.kpi { background:#fff; border:1px solid var(--line); border-top:4px solid var(--asphalt); border-radius:6px; padding:14px 16px; }
.kpi.y { border-top-color:var(--yellow); } .kpi.g { border-top-color:var(--green); } .kpi.r { border-top-color:var(--red); }
.kpi .l { color:#5B636D; font-size:.9rem; }
.kpi .v { font-family:'Barlow Condensed'; font-size:2.1rem; font-weight:700; color:var(--asphalt); line-height:1.1; }
.kpi .s { color:#5B636D; font-size:.82rem; }
div[data-testid="stForm"] { background:#fff; border:1px solid var(--line); border-radius:6px; }
.stButton>button, .stFormSubmitButton>button, .stDownloadButton>button { background:var(--asphalt); color:#fff; border:0; border-radius:4px; font-weight:600; }
.stButton>button:hover, .stFormSubmitButton>button:hover, .stDownloadButton>button:hover { background:var(--yellow); color:var(--asphalt); }
#MainMenu, footer { visibility:hidden; }
</style>
""", unsafe_allow_html=True)


# ---------- Helpers ----------
def kpi(label, value, sub="", tone=""):
    st.markdown(f'<div class="kpi {tone}"><div class="l">{label}</div><div class="v">{value}</div>'
                f'<div class="s">{sub or "&nbsp;"}</div></div>', unsafe_allow_html=True)


def get_inventory():
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM cars").fetchall()
    finally:
        conn.close()


def low_stock(threshold):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id, brand, model, stock FROM cars WHERE stock <= ? ORDER BY stock, brand, model",
            (int(threshold),)).fetchall()
    finally:
        conn.close()


CAR_COLS = ["ID", "Brand", "Model", "Selling Price", "Cost Price", "Stock", "Condition", "Notes"]


# ---------- Pages ----------
def page_dashboard():
    cars = get_inventory()
    st.title("Dashboard")
    st.caption("Your stock, sales and profit at a glance.")

    # ---- Period filter ----
    today = date.today()
    period = st.radio("Period", ["This month", "Last 30 days", "This year", "All time"],
                      horizontal=True, label_visibility="collapsed", key="dash_period")
    start = {"This month": today.replace(day=1), "Last 30 days": today - timedelta(days=30),
             "This year": date(today.year, 1, 1), "All time": date(2000, 1, 1)}[period]
    f = get_financial_summary(start, today)
    revenue, gross = f["total_revenue"], f["gross_profit"]
    expenses, net = f["operating_expenses"], f["net_operating_profit"]
    margin = (gross / revenue * 100) if revenue else 0

    c = st.columns(4)
    with c[0]: kpi("Revenue", RS.format(revenue), f"{f['units_sold']} units · {f['total_orders']} orders", "y")
    with c[1]: kpi("Gross profit", RS.format(gross), f"Margin {margin:.1f}%", "g" if gross >= 0 else "r")
    with c[2]: kpi("Expenses", RS.format(expenses), "Packaging, shipping, ads and more", "r")
    with c[3]: kpi("Net profit", RS.format(net), "Gross profit minus expenses", "g" if net >= 0 else "r")

    st.write("")
    inv_cost, pot_sales, pot_profit = calculate_inventory_value()
    units = sum(c[5] for c in cars)
    c = st.columns(4)
    with c[0]: kpi("Units in stock", f"{units:,}", f"{len(cars)} models")
    with c[1]: kpi("Inventory cost value", RS.format(inv_cost), "What your stock cost")
    with c[2]: kpi("Potential sales value", RS.format(pot_sales), "If everything sells")
    with c[3]: kpi("Potential profit", RS.format(pot_profit), "On current stock", "g")

    # ---- Sales rows (date trimmed to YYYY-MM-DD) ----
    rows = get_invoiceable_sales()
    sales = pd.DataFrame([{
        "id": r["order_id"], "date": str(r["order_date"])[:10],
        "brand": r["brand"] or "", "model": r["model"] or "",
        "qty": int(r["quantity"]), "price": float(r["unit_price"]),
    } for r in rows]) if rows else pd.DataFrame(columns=["id", "date", "brand", "model", "qty", "price"])
    if not sales.empty:
        sales["revenue"] = sales.qty * sales.price
        in_range = sales[(sales.date >= str(start)) & (sales.date <= str(today))]
    else:
        in_range = sales

    st.write("")
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Revenue by day")
        if in_range.empty:
            st.info("No sales in this period.")
        else:
            st.bar_chart(in_range.groupby("date").revenue.sum(), color="#FFC400")
    with right:
        st.subheader("Needs restocking")
        limit = st.number_input("Alert at or below", 0, 100, 3, key="low_stock_threshold")
        low = low_stock(limit)
        if low:
            st.warning(f"{len(low)} model(s) need attention.")
            st.dataframe(pd.DataFrame(low, columns=["ID", "Brand", "Model", "Left"]),
                         hide_index=True, width="stretch")
        else:
            st.success("Nothing is running low.")

    a, b = st.columns(2)
    with a:
        st.subheader("Recent sales")
        if sales.empty:
            st.info("No sales recorded yet.")
        else:
            recent = sales.sort_values("id", ascending=False).head(5)
            st.dataframe(pd.DataFrame({
                "Date": recent.date, "Car": (recent.brand + " " + recent.model).str.strip(),
                "Qty": recent.qty, "Total ₹": recent.revenue}),
                hide_index=True, width="stretch")
    with b:
        st.subheader("Best sellers")
        best = get_best_sellers()
        if best:
            st.dataframe(pd.DataFrame(best, columns=["Brand", "Model", "Units Sold"]),
                         hide_index=True, width="stretch")
        else:
            st.info("Best sellers appear after your first sale.")

    a, b = st.columns(2)
    with a:
        st.subheader("Stock by brand")
        if cars:
            by_brand = pd.DataFrame(cars, columns=CAR_COLS).groupby("Brand").Stock.sum()
            st.bar_chart(by_brand, color="#1B1F24")
        else:
            st.info("Your inventory is empty.")
    with b:
        st.subheader("Not sold yet")
        sold = set(zip(sales.brand, sales.model)) if not sales.empty else set()
        idle = [(c[1], c[2], c[5]) for c in cars if c[5] > 0 and (c[1], c[2]) not in sold]
        if idle:
            st.dataframe(pd.DataFrame(idle, columns=["Brand", "Model", "In stock"]),
                         hide_index=True, width="stretch")
        else:
            st.success("Every car in stock has sold at least once.")


def page_inventory():
    cars = get_inventory()
    st.title("Inventory")
    t1, t2, t3 = st.tabs(["All cars", "Add car", "Edit or delete"])

    with t1:
        term = st.text_input("Search", placeholder="Brand or model, e.g. Ferrari or Hot Wheels")
        shown = [c for c in cars if term.lower() in c[1].lower() or term.lower() in c[2].lower()] if term else cars
        if shown:
            st.dataframe(pd.DataFrame(shown, columns=CAR_COLS), hide_index=True, width="stretch")
        else:
            st.info("No cars found.")

    with t2:
        with st.form("add_car_form", clear_on_submit=True):
            c = st.columns(2)
            brand = c[0].selectbox("Brand", BRANDS)
            model = c[1].text_input("Car model")
            c = st.columns(4)
            price = c[0].number_input("Selling price (₹)", min_value=0.0, step=1.0)
            cost = c[1].number_input("Cost price (₹)", min_value=0.0, step=1.0)
            stock = c[2].number_input("Stock quantity", min_value=0, step=1)
            condition = c[3].selectbox("Condition", CONDITIONS)
            if st.form_submit_button("Add car"):
                if not model.strip():
                    st.error("Enter the car model.")
                elif price <= 0:
                    st.error("Selling price must be greater than zero.")
                else:
                    try:
                        add_car(brand, model.strip(), price, cost, stock, condition)
                        st.success(f"{model} added.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not add car: {e}")

    with t3:
        if not cars:
            st.info("Add a car before managing inventory.")
            return
        opts = {f"ID {c[0]} - {c[1]} {c[2]}": c for c in cars}
        car = opts[st.selectbox("Choose a car", list(opts), key="manage_car_select")]
        with st.form("edit_car_form"):
            c = st.columns(2)
            brand = c[0].text_input("Brand", value=car[1])
            model = c[1].text_input("Model", value=car[2])
            c = st.columns(4)
            price = c[0].number_input("Selling price (₹)", min_value=0.01, value=max(float(car[3]), 0.01), step=1.0)
            cost = c[1].number_input("Cost price (₹)", min_value=0.0, value=max(float(car[4]), 0.0), step=1.0)
            stock = c[2].number_input("Stock", min_value=0, value=max(int(car[5]), 0), step=1)
            cond = c[3].selectbox("Condition", CONDITIONS, index=0 if car[6] == "New" else 1)
            if st.form_submit_button("Save changes"):
                try:
                    update_car(car[0], brand, model, price, cost, int(stock), cond)
                    st.success("Car updated.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not update car: {e}")
        with st.expander("Delete this car"):
            st.warning("Cars with existing sales history cannot be deleted.")
            ok = st.checkbox("I understand that deleting a car cannot be undone.", key="confirm_delete_car")
            if st.button("Delete selected car"):
                if not ok:
                    st.warning("Tick the box to confirm.")
                else:
                    try:
                        delete_car(car[0])
                        st.success("Car deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not delete car: {e}")


def page_sales():
    st.title("Sales")
    cars = get_inventory()
    opts = {f"{c[1]} - {c[2]} (Stock: {c[5]})": c[0] for c in cars if c[5] > 0}
    if not cars:
        st.info("Add a car before recording a sale.")
    elif not opts:
        st.info("No cars currently in stock.")
    else:
        with st.form("record_sale_form", clear_on_submit=True):
            sel = st.selectbox("Car", list(opts))
            c = st.columns(3)
            qty = c[0].number_input("Quantity sold", min_value=1, step=1)
            source = c[1].selectbox("Order source", SOURCES)
            city = c[2].text_input("Customer city")
            if st.form_submit_button("Record sale"):
                try:
                    log_order(opts[sel], int(qty), source, city.strip())
                    st.success("Sale recorded and stock updated.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not record sale: {e}")

    st.subheader("Recent sales")
    rows = get_invoiceable_sales()
    if rows:
        st.dataframe(pd.DataFrame([{
            "Order": r["order_id"], "Date": r["order_date"],
            "Car": f'{r["brand"] or ""} {r["model"] or ""}'.strip(),
            "Qty": r["quantity"], "Unit price ₹": float(r["unit_price"]),
        } for r in rows]), hide_index=True, width="stretch")
    else:
        st.info("No sales recorded yet.")


def page_purchases():
    st.title("Purchases")
    st.caption("Record new stock and track restocking costs.")
    conn = get_connection()
    try:
        pcars = conn.execute("SELECT id, brand, model, stock FROM cars ORDER BY brand, model").fetchall()
        hist = conn.execute("""
            SELECT p.id, p.purchase_date, c.brand, c.model, p.quantity, p.unit_cost,
                   p.quantity * p.unit_cost, p.supplier, p.notes
            FROM purchases p JOIN cars c ON c.id = p.car_id ORDER BY p.id DESC""").fetchall()
    finally:
        conn.close()

    if not pcars:
        st.info("Add a car to your inventory before recording a purchase.")
    else:
        opts = {f"ID {c[0]} - {c[1]} {c[2]} (Current stock: {c[3]})": c[0] for c in pcars}
        with st.form("stock_purchase_form", clear_on_submit=True):
            sel = st.selectbox("Diecast model", list(opts))
            c = st.columns(4)
            qty = c[0].number_input("Quantity", min_value=1, value=1, step=1)
            unit = c[1].number_input("Cost Price (₹)", min_value=0.0, step=10.0, format="%.2f")
            supplier = c[2].text_input("Supplier")
            when = c[3].date_input("Purchase date")
            notes = st.text_area("Notes (optional)", height=70)
            if st.form_submit_button("Record purchase and restock", type="primary"):
                try:
                    pid = record_purchase(car_id=int(opts[sel]), quantity=int(qty), unit_cost=float(unit),
                                          supplier=supplier, purchase_date=when, notes=notes)
                    st.success(f"Purchase #{pid} recorded. {int(qty)} unit(s) added to inventory.")
                    st.rerun()
                except (ValueError, TypeError) as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Could not record purchase: {e}")

    st.subheader("Purchase history")
    if hist:
        df = pd.DataFrame([tuple(r) for r in hist], columns=[
            "Purchase ID", "Date", "Brand", "Model", "Quantity",
            "Unit Cost (INR)", "Total Cost (INR)", "Supplier", "Notes"])
        kpi("Total recorded purchase cost", f"INR {df['Total Cost (INR)'].sum():,.2f}", "", "y")
        st.write("")
        st.dataframe(df, hide_index=True, width="stretch")
    else:
        st.info("No stock purchases recorded yet.")


def page_business():
    st.title("Suppliers and expenses")
    t1, t2, t3 = st.tabs(["Suppliers", "Expenses", "Expense summary"])

    with t1:
        with st.form("add_supplier_form", clear_on_submit=True):
            c = st.columns(3)
            name = c[0].text_input("Supplier name")
            phone = c[1].text_input("Phone number")
            email = c[2].text_input("Email address")
            c = st.columns(2)
            addr = c[0].text_area("Address", height=90)
            notes = c[1].text_area("Supplier notes", height=90)
            if st.form_submit_button("Add supplier"):
                try:
                    sid = add_supplier(name, phone, email, addr, notes)
                    st.success(f"Supplier added. ID: {sid}")
                    st.rerun()
                except (ValueError, TypeError) as e:
                    st.error(str(e))
        with get_connection() as conn:
            sups = conn.execute("SELECT id, name, phone, email, address, notes FROM suppliers ORDER BY name").fetchall()
        st.subheader("Supplier directory")
        if sups:
            st.dataframe(pd.DataFrame([tuple(r) for r in sups],
                         columns=["ID", "Supplier", "Phone", "Email", "Address", "Notes"]),
                         hide_index=True, width="stretch")
        else:
            st.info("No suppliers added yet.")
        st.subheader("Historical purchase spending")
        sp = get_supplier_spending()
        if sp:
            df = pd.DataFrame(sp, columns=["Supplier", "Purchase Count", "Total Spending"])
            df["Total Spending"] = df["Total Spending"].map(lambda a: f"INR {a:,.2f}")
            st.dataframe(df, hide_index=True, width="stretch")
        else:
            st.info("No purchase spending available.")

    with t2:
        with st.form("add_expense_form", clear_on_submit=True):
            c = st.columns(3)
            d = c[0].date_input("Expense date")
            cat = c[1].selectbox("Category", EXPENSE_CATS)
            pay = c[2].selectbox("Payment method", PAYMENTS)
            c = st.columns(2)
            desc = c[0].text_input("Description")
            amt = c[1].number_input("Amount (INR)", min_value=0.0, step=10.0, format="%.2f")
            notes = st.text_area("Notes (optional)", height=70)
            if st.form_submit_button("Save expense"):
                try:
                    eid = add_expense(d, cat, desc, amt, pay, notes)
                    st.success(f"Expense recorded. ID: {eid}")
                    st.rerun()
                except (ValueError, TypeError) as e:
                    st.error(str(e))
        st.subheader("Expense history")
        rows = get_expenses()
        if rows:
            st.dataframe(pd.DataFrame([tuple(r) for r in rows], columns=[
                "ID", "Date", "Category", "Description", "Amount (INR)", "Payment Method", "Notes"]),
                hide_index=True, width="stretch")
        else:
            st.info("No expenses recorded yet.")

    with t3:
        rows = get_expenses()
        if rows:
            df = pd.DataFrame([tuple(r) for r in rows], columns=[
                "ID", "Date", "Category", "Description", "Amount", "Payment Method", "Notes"])
            kpi("Total recorded expenses", f"INR {float(df['Amount'].sum()):,.2f}", "", "r")
            st.write("")
            by_cat = df.groupby("Category", as_index=False)["Amount"].sum().sort_values("Amount", ascending=False)
            a, b = st.columns(2)
            a.bar_chart(by_cat.set_index("Category"), color="#1B1F24")
            b.dataframe(by_cat, hide_index=True, width="stretch")
        else:
            st.info("Record expenses to see a summary by category.")


def page_reports():
    st.title("Reports and invoices")
    t1, t2 = st.tabs(["Financial report", "PDF invoice"])

    with t1:
        c = st.columns(2)
        start = c[0].date_input("Start date", value=date(date.today().year, 1, 1), key="financial_report_start")
        end = c[1].date_input("End date", value=date.today(), key="financial_report_end")
        if start > end:
            st.error("Start date must be on or before the end date.")
        else:
            f = get_financial_summary(start, end)
            sales_df, purchases_df, expenses_df = get_financial_details(start, end)
            c = st.columns(3)
            with c[0]: kpi("Sales revenue", f"INR {f['total_revenue']:,.2f}", "", "y")
            with c[1]: kpi("Cost of goods sold", f"INR {f['total_cogs']:,.2f}")
            with c[2]: kpi("Gross profit", f"INR {f['gross_profit']:,.2f}", "", "g")
            st.write("")
            c = st.columns(3)
            with c[0]: kpi("Operating expenses", f"INR {f['operating_expenses']:,.2f}", "", "r")
            with c[1]: kpi("Net operating profit", f"INR {f['net_operating_profit']:,.2f}", "", "g" if f["net_operating_profit"] >= 0 else "r")
            with c[2]: kpi("Units sold", f"{f['units_sold']}", f"{f['total_orders']} orders")
            st.caption("Profit uses historical sale prices and costs. Stock purchases are reported separately and not subtracted again.")

            purchase_total = purchases_df["purchase_total"].fillna(0).sum() if not purchases_df.empty else 0
            for title, df, empty in [("Stock purchases", purchases_df, "No stock purchases in this range."),
                                     ("Sales details", sales_df, "No sales in this range."),
                                     ("Operating expenses", expenses_df, "No expenses in this range.")]:
                with st.expander(title):
                    st.dataframe(df, width="stretch") if not df.empty else st.info(empty)

            summary = pd.DataFrame([
                ("Sales Revenue", f["total_revenue"]), ("Cost of Goods Sold", f["total_cogs"]),
                ("Gross Profit", f["gross_profit"]), ("Operating Expenses", f["operating_expenses"]),
                ("Net Operating Profit", f["net_operating_profit"]), ("Units Sold", f["units_sold"]),
                ("Total Stock Purchases (separate)", purchase_total)], columns=["Metric", "Amount (INR)"])
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                summary.to_excel(w, sheet_name="Financial Summary", index=False)
                sales_df.to_excel(w, sheet_name="Sales", index=False)
                purchases_df.to_excel(w, sheet_name="Stock Purchases", index=False)
                expenses_df.to_excel(w, sheet_name="Operating Expenses", index=False)
            st.download_button("Download Excel report", buf.getvalue(),
                               f"Financial_Report_{start}_{end}.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="download_financial_excel")

    with t2:
        rows = get_invoiceable_sales()
        if not rows:
            st.info("No recorded sales are available for invoicing yet.")
            return
        opts = {f"Order #{r['order_id']} | {r['brand'] or 'Unknown Brand'} {r['model'] or ''} | "
                f"{r['order_date']} | Qty: {r['quantity']} | INR {float(r['unit_price']):,.2f} each": r
                for r in rows}
        sale = opts[st.selectbox("Select a sale", list(opts), key="invoice_existing_sale")]
        total = int(sale["quantity"]) * float(sale["unit_price"])
        st.caption(f"{sale['brand'] or ''} {sale['model'] or ''} · {sale['order_date']} · "
                   f"Qty {sale['quantity']} · Total INR {total:,.2f}")
        with st.form("invoice_customer_form"):
            st.subheader("Customer details (optional)")
            c = st.columns(3)
            name, phone, email = c[0].text_input("Customer name"), c[1].text_input("Phone"), c[2].text_input("Email")
            addr = st.text_area("Billing address", height=80)
            go = st.form_submit_button("Generate PDF invoice")
        if go:
            try:
                oid = int(sale["order_id"])
                number = f"CWA-{date.today():%Y%m%d}-{oid:06d}"
                pdf = generate_invoice_pdf(
                    invoice_number=number, invoice_date=date.today().isoformat(),
                    customer_name=name.strip(), customer_phone=phone.strip(),
                    customer_email=email.strip(), customer_address=addr.strip(),
                    car_brand=sale["brand"] or "Diecast", car_model=sale["model"] or "Model",
                    quantity=sale["quantity"], unit_price=sale["unit_price"])
                st.success(f"Invoice {number} generated.")
                st.download_button("Download PDF invoice", pdf,
                                   f"{re.sub(r'[^A-Za-z0-9_-]', '_', number)}.pdf",
                                   "application/pdf", key=f"download_invoice_{oid}")
            except Exception as e:
                st.error(f"Could not generate invoice: {e}")


# ---------- Website (storefront) ----------
def page_website():
    st.title("Website")
    st.caption("Your storefront at collectwithakash.github.io. Changes here reach the site within seconds.")
    t1, t2 = st.tabs([f"Orders ({wo.pending_count()} pending)", "Listings"])

    with t1:
        orders = wo.list_orders()
        if not orders:
            st.info("No website orders yet.")
        for o in orders:
            with st.container(border=True):
                st.markdown(f"**Order #{o['id']}** · {o['created_at']} · **{o['status']}**")
                st.write(f"{o['name']} · {o['phone']} · {o['city'] or 'No city'}")
                st.write("; ".join(f"{i['qty']} × {i['brand']} {i['model']} @ {RS.format(i['price'])}" for i in o["items"])
                         + f" — **Total {RS.format(o['total'])}**")
                if o["status"] == "Pending":
                    a, b, _ = st.columns([1, 1, 4])
                    if a.button("Confirm sale", key=f"ok{o['id']}", type="primary"):
                        try:
                            wo.confirm_order(o["id"])
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                    if b.button("Cancel", key=f"no{o['id']}"):
                        wo.cancel_order(o["id"])
                        st.rerun()

    with t2:
        cars = get_inventory()
        if not cars:
            st.info("Add a car in Inventory and it appears on the website automatically.")
            return
        opts = {f"ID {c[0]} - {c[1]} {c[2]}": c[0] for c in cars}
        pick = opts[st.selectbox("Car", list(opts), key="web_car")]
        scale, image, listed = wo.get_extras(pick)
        with st.form(f"web_extras_{pick}"):
            c = st.columns(2)
            new_scale = c[0].text_input("Scale", value=scale)
            show = c[1].checkbox("Show on website", value=listed)
            pic = st.file_uploader("Photo (JPG, PNG or WEBP)", type=["jpg", "jpeg", "png", "webp"])
            if image:
                st.caption(f"Current photo: {image}")
            if st.form_submit_button("Save listing"):
                try:
                    wo.save_extras(pick, new_scale, show, pic.getvalue() if pic else None, pic.name if pic else None)
                    st.success("Saved. The website will show it on its next refresh.")
                except ValueError as e:
                    st.error(str(e))


# ---------- Public storefront (inside the same app) ----------
DEMO_CARS = [
    ("Hot Wheels", "Ferrari SF90 Stradale", 179, 167, 10, "New"),
    ("Hot Wheels", "Porsche 911 GT3 RS", 179, 167, 10, "New"),
    ("Mini GT", "Nissan Skyline GT-R (R34)", 599, 480, 4, "New"),
    ("Majorette", "Toyota Supra", 249, 190, 6, "New"),
    ("Matchbox", "Land Rover Defender", 199, 150, 3, "Used"),
]
DEMO_SALES = [(1, 1, "Instagram", "Kochi"), (3, 2, "Telegram", "Chennai"), (4, 1, "Website", "Bengaluru")]


def auto_confirm_enabled():
    """Secrets: auto_confirm = true (default) records each website order as a sale immediately."""
    try:
        return bool(st.secrets.get("auto_confirm", True))
    except Exception:
        return True


def try_confirm(order_id):
    try:
        wo.confirm_order(order_id)
        return True
    except Exception:
        return False  # stays Pending; confirm it manually in Website > Orders


def page_shop():
    st.title("Available Cars")
    st.caption("First come, first served. Choose your cars, then place your order.")
    if st.session_state.get("shop_done"):
        st.success(st.session_state.pop("shop_done"))
    cars = wo.public_cars()
    if not cars:
        st.info("Nothing is listed right now. Check back soon.")
        return
    qty = {}
    with st.form("shop_form"):
        cols = st.columns(3)
        for i, c in enumerate(cars):
            with cols[i % 3].container(border=True):
                img = wo.MEDIA_DIR / c["image"] if c["image"] else None
                if img and img.exists():
                    st.image(str(img), use_container_width=True)
                st.markdown(f"**{c['brand']}**  \n{c['model']}")
                st.markdown(f"### {RS.format(c['price'])}")
                st.caption(f"Scale {c['scale']} · {c['condition']} · {c['status']}")
                if c["available"] > 0:
                    qty[c["id"]] = st.number_input("Quantity", 0, int(c["available"]), 0, 1, key=f"shop_q{c['id']}")
                else:
                    st.error("Sold out")
        st.subheader("Your details")
        d = st.columns(3)
        name, phone, city = d[0].text_input("Name"), d[1].text_input("Phone"), d[2].text_input("City")
        go = st.form_submit_button("Place order", type="primary")
    if go:
        items = [(k, v) for k, v in qty.items() if v > 0]
        if not items:
            st.error("Choose a quantity on at least one car.")
        elif not name.strip():
            st.error("Enter your name.")
        elif not re.fullmatch(r"\+?[0-9 ]{7,15}", phone.strip()):
            st.error("Enter a valid phone number.")
        else:
            try:
                res = wo.create_order(name.strip(), phone.strip(), city.strip(), items)
                confirmed = auto_confirm_enabled() and try_confirm(res["id"])
                for k in [k for k in st.session_state if str(k).startswith("shop_q")]:
                    del st.session_state[k]
                st.session_state["shop_done"] = (
                    f"Order #{res['id']} confirmed ({RS.format(res['total'])}). Thank you!" if confirmed else
                    f"Order #{res['id']} placed ({RS.format(res['total'])}). "
                    "The seller will contact you to arrange payment and delivery.")
                st.rerun()
            except wo.OrderError as e:
                st.error(str(e))


# ---------- Access and navigation ----------
def admin_password():
    try:
        return st.secrets["admin_password"]
    except Exception:
        return os.environ.get("ADMIN_PASSWORD", "")


def maybe_seed():
    """Optional: fill a fresh database with sample data (set demo_seed = true in secrets)."""
    try:
        if not st.secrets.get("demo_seed", False):
            return
    except Exception:
        return
    try:
        if get_inventory():
            return
        for c in DEMO_CARS:
            add_car(*c)
        for s in DEMO_SALES:
            log_order(*s)
    except Exception as e:
        st.warning(f"Could not add demo data: {e}")


def login_box():
    pw = admin_password()
    with st.expander("Owner login"):
        if not pw:
            st.info("Set admin_password in .streamlit/secrets.toml to enable the Manager.")
            return
        entered = st.text_input("Password", type="password", key="admin_pw")
        if st.button("Log in"):
            if hmac.compare_digest(entered, pw):
                st.session_state["admin"] = True
                st.rerun()
            else:
                st.error("Wrong password.")


# ---------- Public website (rebuilt from index.html) ----------
SITE = "https://collectwithakash.github.io"  # images are loaded from your existing GitHub Pages site
CATEGORIES = ["HOT WHEELS", "MINI GT", "MATCHBOX", "MAJORETTE", "KAIDO HOUSE", "INNO64",
              "TARMAC WORKS", "TOMICA", "GREENLIGHT", "AUTO WORLD"]
STATS = [("100+", "Cars Collected"), ("1+", "Hotwheels Elite64"), ("10+", "Hotwheels Premiums"),
         ("4+", "Hotwheels Silver Series"), ("4+", "Mini GT"), ("2+", "Majorette"), ("4+", "Match Box")]
PUBLIC_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;500;700;900&display=swap');
html{scroll-behavior:smooth;}
header[data-testid="stHeader"],[data-testid="stToolbar"],section[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"]{display:none !important;}
.stApp{background:#050505;}
.block-container{padding:0 !important;max-width:100% !important;}
.stApp h1,.stApp h2,.stApp h3,.stApp p,.stApp label,.stApp button,.stApp input,.stApp a,[class^="cw-"]{font-family:'Montserrat',sans-serif;}
.stApp h1,.stApp h2,.stApp h3,.stApp [data-testid="stWidgetLabel"] p,.stApp [data-testid="stCaptionContainer"],
.stApp [data-testid="stMarkdownContainer"] p{color:#fff !important;}
div[data-testid="stForm"],[data-testid="stVerticalBlockBorderWrapper"]{background:#111 !important;border-color:#2a2a2a !important;}
.stButton>button,.stFormSubmitButton>button{background:#ff0000;color:#fff;border:0;font-weight:700;}
.stButton>button:hover,.stFormSubmitButton>button:hover{background:#cc0000;color:#fff;}
.stApp [data-testid="stAlert"] p{color:#111 !important;}
.cw-nav{position:fixed;top:0;left:0;right:0;z-index:1000;display:flex;justify-content:space-between;align-items:center;
padding:20px 50px;background:rgba(0,0,0,.85);backdrop-filter:blur(10px);}
.cw-logo{font-size:32px;font-weight:900;letter-spacing:2px;color:#fff !important;text-decoration:none;}
.cw-logo span{color:#f00;}
.cw-links{display:flex;align-items:center;gap:30px;}
.cw-link{color:#fff !important;text-decoration:none;font-weight:600;}
.cw-dsm{background:#f00;padding:8px 16px;border-radius:6px;font-weight:700;}
.cw-dsm:hover{background:#cc0000;}
.cw-hero{height:100vh;display:flex;align-items:center;padding:0 80px;background-size:cover;background-position:center;}
.stApp .cw-hero h1{font-size:90px;font-weight:900;line-height:1;margin:0;padding:0;}
.stApp .cw-hero p{margin-top:20px;font-size:20px;color:#d0d0d0 !important;max-width:700px;}
.cw-buttons{margin-top:30px;}
.cw-btn{display:inline-block;padding:15px 35px;margin-right:15px;background:#f00;color:#fff !important;text-decoration:none;border-radius:6px;font-weight:700;}
.cw-btn:hover{background:#cc0000;}
.cw-cats{display:flex;justify-content:center;gap:40px;padding:25px;background:#0d0d0d;overflow:auto;font-weight:700;white-space:nowrap;color:#fff;}
.cw-sec{padding:80px 8%;}
.stApp .cw-title{font-size:50px;font-weight:900;margin-bottom:40px;color:#fff !important;}
.cw-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:25px;}
.cw-card{background:#111;border-radius:15px;overflow:hidden;display:flex;flex-direction:column;text-decoration:none;transition:.3s;}
.cw-card:hover{transform:translateY(-10px);}
.cw-card img{width:100%;height:250px;object-fit:cover;display:block;}
.cw-gal{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;height:250px;}
.cw-gal img{height:100%;}
.cw-body{padding:20px;}
.stApp .cw-body h3{margin:0 0 10px;}
.stApp .cw-body p{margin:0;color:#bbb !important;}
.cw-stat{background:#111;padding:40px;text-align:center;border-radius:15px;color:#fff;}
.cw-stat b{display:block;font-size:50px;color:red;}
.stApp .cw-foot{padding:40px;text-align:center;background:#000;color:#888 !important;}
@media(max-width:768px){
.cw-nav{padding:15px;flex-direction:column;gap:10px;}.cw-logo{font-size:24px;}
.cw-hero{padding:20px;text-align:center;justify-content:center;}
.stApp .cw-hero h1{font-size:42px;}.stApp .cw-hero p{font-size:16px;}
.cw-btn{display:block;margin:0 0 10px;text-align:center;}
.stApp .cw-title{font-size:32px;text-align:center;}}
</style>
"""


def h(s):
    """Strip indentation and blank lines so Streamlit's markdown never turns HTML into a code block."""
    return "\n".join(l.strip() for l in s.splitlines() if l.strip())


def src(p):
    return p if p.startswith("http") else f"{SITE}/{quote(p)}"


def site_card(title, text, imgs=(), href=None):
    srcs = [src(p) for p in imgs]
    if not srcs:
        pics = ""
    elif len(srcs) == 1:
        pics = f'<img src="{srcs[0]}">'
    else:
        pics = '<div class="cw-gal">' + "".join(f'<img src="{s}">' for s in srcs) + "</div>"
    tag, attrs = ("a", f' href="{href}" target="_blank"') if href else ("div", "")
    return f'<{tag} class="cw-card"{attrs}>{pics}<div class="cw-body"><h3>{title}</h3><p>{text}</p></div></{tag}>'


def section(title, cards, sid="", extra=""):
    st.markdown(h(f'<div class="cw-sec" id="{sid}"><div class="cw-title">{title}</div>'
                  f'<div class="cw-grid">{"".join(cards)}</div>{extra}</div>'), unsafe_allow_html=True)


def site_header():
    st.markdown(h(f"""
        <div class="cw-nav"><a class="cw-logo" href="?" target="_self">COLLECT<span>WITHAKASH</span></a>
        <div class="cw-links">
        <a class="cw-link" href="https://www.instagram.com/collectwithakash/" target="_blank">Instagram</a>
        <a class="cw-link" href="https://www.threads.com/@collectwithakash" target="_blank">Threads</a>
        <a class="cw-link cw-dsm" href="?view=manager" target="_self">DSM</a></div></div>"""),
        unsafe_allow_html=True)


def site_footer():
    st.markdown('<div class="cw-foot">© 2026 CollectwithAkash | Diecast Collector</div>', unsafe_allow_html=True)


def page_home():
    bg = f"linear-gradient(to right,rgba(0,0,0,.9),rgba(0,0,0,.4)),url('{src('images/IMG_8621.JPG')}')"
    st.markdown(h(f"""
        <div class="cw-hero" style="background-image:{bg}"><div>
        <h1>COLLECT WITH AKASH</h1>
        <p>Premium Diecast Collection Showcase. Hot Wheels • Mini GT • Majorette • Matchbox •</p>
        <div class="cw-buttons"><a class="cw-btn" href="#collection">View Collection</a>
        <a class="cw-btn" href="?view=shop" target="_self">Sale</a></div>
        </div></div>"""), unsafe_allow_html=True)
    st.markdown('<div class="cw-cats">' + "".join(f"<div>{c}</div>" for c in CATEGORIES) + "</div>", unsafe_allow_html=True)
    st.markdown(h('<div class="cw-sec"><div class="cw-title">COLLECTION STATS</div><div class="cw-grid">'
                  + "".join(f'<div class="cw-stat"><b>{n}</b>{t}</div>' for n, t in STATS) + "</div></div>"),
                unsafe_allow_html=True)
    section("FEATURED COLLECTION", [
        site_card("Hotwheels Ferrari Collection", "Ferrari diecast models.",
                  ["Ferrari/IMG_8627 (1).JPG", "Ferrari/IMG_8624 (2).JPG", "Ferrari/IMG_8625 (3).JPG"], f"{SITE}/ferrari.html"),
        site_card("Mini GT Porsche Collection", "Detailed collector-grade models.",
                  ["https://images.unsplash.com/photo-1553440569-bcc63803a83d?q=80&w=1200"]),
        site_card("Bburago Ferrari Collection", "1:64 Ratio.",
                  ["https://images.unsplash.com/photo-1502877338535-766e1452684a?q=80&w=1200"]),
    ], sid="collection")
    section("MAGAZINE BY COLLECTWITHAKASH", [
        site_card("Metallic Marvels", "Featured diecast stories and showcases.", ["images/metallic_marvels.jpg"]),
        site_card("Flam3z_On", "Collector highlights and latest finds.",
                  ["Flam3z_On/1000398701.jpg.jpeg", "Flam3z_On/1000398661.jpg.jpeg", "Flam3z_On/1000398702.jpg.jpeg"]),
        site_card("Mr. Scleropages", "Magazine articles and collection features.", ["images/mr_scleropages.jpg"]),
    ])
    section("FOR SALE AT MRP", [
        site_card("Available Cars", "View all available stock.", href="?view=shop"),
        site_card("First Come First Serve", "Reply quickly before items are sold."),
    ], sid="sale")
    site_footer()


def page_login():
    st.markdown("<style>.block-container{padding:140px 8% 40px !important;}</style>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.title("Diecast Store Manager")
        pw = admin_password()
        if not pw:
            st.info("Owner login is not set up. Add admin_password to the app secrets.")
            return
        with st.form("login_form"):
            entered = st.text_input("Password", type="password")
            if st.form_submit_button("Log in", type="primary"):
                if hmac.compare_digest(entered, pw):
                    st.session_state["admin"] = True
                    st.rerun()
                else:
                    st.error("Wrong password.")


maybe_seed()
if not st.session_state.get("admin"):
    view = st.query_params.get("view", "home")
    st.markdown(PUBLIC_CSS, unsafe_allow_html=True)
    site_header()
    if view == "manager":
        page_login()
    elif view == "shop":
        st.markdown("<style>.block-container{padding:140px 8% 40px !important;}</style>", unsafe_allow_html=True)
        page_shop()
        site_footer()
    else:
        page_home()

else:
    PAGES = {"Dashboard": page_dashboard, "Inventory": page_inventory, "Sales": page_sales,
             "Purchases": page_purchases, "Suppliers & expenses": page_business,
             "Reports & invoices": page_reports, "Website": page_website, "Storefront preview": page_shop}
    with st.sidebar:
        st.markdown('<div class="brand">🏎️ Diecast Store</div>', unsafe_allow_html=True)
        st.caption("Inventory, sales and profit in one place.")
        if wo.pending_count():
            st.warning(f"{wo.pending_count()} website order(s) waiting")
        choice = st.radio("Go to", list(PAGES), label_visibility="collapsed")
        if st.button("Log out"):
            st.session_state["admin"] = False
            st.rerun()
    PAGES[choice]()