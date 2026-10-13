"""Storefront logic shared by the Manager (app.py) and the public API (storefront_api.py).

Design: a website order first RESERVES stock (status Pending). Available stock shown on the
website = cars.stock - pending reservations, so nothing can be oversold. When you confirm an
order in the Manager, your existing log_order() records the sale and reduces real stock.
"""
import os
import time
from datetime import datetime
from pathlib import Path

from db import get_connection, log_order

MEDIA_DIR = Path(os.environ.get("MEDIA_DIR", "media"))
MEDIA_DIR.mkdir(exist_ok=True)
LOW_STOCK = 2


class OrderError(Exception):
    pass


def init_web_tables():
    with get_connection() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS car_extras(
            car_id INTEGER PRIMARY KEY, scale TEXT DEFAULT '1:64', image TEXT, listed INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS web_orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, name TEXT, phone TEXT,
            city TEXT, status TEXT DEFAULT 'Pending', total REAL);
        CREATE TABLE IF NOT EXISTS web_order_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER, car_id INTEGER,
            brand TEXT, model TEXT, qty INTEGER, unit_price REAL);
        """)


def _reserved(conn):
    rows = conn.execute("""SELECT i.car_id, SUM(i.qty) FROM web_order_items i
                           JOIN web_orders o ON o.id = i.order_id
                           WHERE o.status = 'Pending' GROUP BY i.car_id""").fetchall()
    return {r[0]: int(r[1]) for r in rows}


def get_extras(car_id):
    with get_connection() as c:
        r = c.execute("SELECT scale, image, listed FROM car_extras WHERE car_id=?", (car_id,)).fetchone()
    return (r[0] or "1:64", r[1], bool(r[2])) if r else ("1:64", None, True)


def save_extras(car_id, scale, listed, image_bytes=None, filename=None):
    _, image, _ = get_extras(car_id)
    if image_bytes:
        ext = Path(filename or "").suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp") or len(image_bytes) > 5_000_000:
            raise ValueError("Use a JPG, PNG or WEBP image under 5 MB.")
        image = f"{car_id}-{int(time.time())}{ext}"
        (MEDIA_DIR / image).write_bytes(image_bytes)
    with get_connection() as c:
        c.execute("""INSERT INTO car_extras(car_id, scale, image, listed) VALUES(?,?,?,?)
                     ON CONFLICT(car_id) DO UPDATE SET scale=excluded.scale,
                     image=excluded.image, listed=excluded.listed""",
                  (car_id, scale.strip() or "1:64", image, int(listed)))


def public_cars():
    """Only public fields. Cost price is never returned."""
    conn = get_connection()
    try:
        res = _reserved(conn)
        ex = {r[0]: r for r in conn.execute("SELECT car_id, scale, image, listed FROM car_extras")}
        out = []
        for c in conn.execute("SELECT * FROM cars"):
            e = ex.get(c[0])
            if e and not e[3]:
                continue
            avail = max(0, int(c[5]) - res.get(c[0], 0))
            out.append({
                "id": c[0], "brand": c[1], "model": c[2], "price": float(c[3]),
                "condition": c[6], "scale": (e[1] if e else None) or "1:64",
                "image": f"/media/{e[2]}" if e and e[2] else None,
                "available": avail,
                "status": "Sold out" if avail == 0 else "Low stock" if avail <= LOW_STOCK else "In stock",
            })
        return out
    finally:
        conn.close()


def create_order(name, phone, city, items):
    """items: list of (car_id, qty). Atomic: either every line is reserved or none is."""
    want = {}
    for car_id, qty in items:
        want[int(car_id)] = want.get(int(car_id), 0) + int(qty)
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        res = _reserved(conn)
        lines, total = [], 0.0
        for car_id, qty in want.items():
            c = conn.execute("SELECT * FROM cars WHERE id=?", (car_id,)).fetchone()
            e = conn.execute("SELECT listed FROM car_extras WHERE car_id=?", (car_id,)).fetchone()
            if not c or (e and not e[0]):
                raise OrderError("A car in your cart is no longer available.")
            avail = int(c[5]) - res.get(car_id, 0)
            if qty < 1 or qty > avail:
                raise OrderError(f"Only {max(avail, 0)} left of {c[1]} {c[2]}.")
            lines.append((car_id, c[1], c[2], qty, float(c[3])))
            total += qty * float(c[3])
        cur = conn.execute("INSERT INTO web_orders(created_at, name, phone, city, status, total) VALUES(?,?,?,?,?,?)",
                           (datetime.now().strftime("%Y-%m-%d %H:%M"), name, phone, city, "Pending", total))
        oid = cur.lastrowid
        conn.executemany("INSERT INTO web_order_items(order_id, car_id, brand, model, qty, unit_price) VALUES(?,?,?,?,?,?)",
                         [(oid,) + l for l in lines])
        conn.commit()
        return {"id": oid, "total": total, "lines": lines}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def confirm_order(order_id):
    """Records the sale with your existing log_order() (reduces real stock, source = Website)."""
    conn = get_connection()
    try:
        o = conn.execute("SELECT status, city FROM web_orders WHERE id=?", (order_id,)).fetchone()
        items = conn.execute("SELECT car_id, qty, brand, model FROM web_order_items WHERE order_id=?", (order_id,)).fetchall()
        if not o or o[0] != "Pending":
            raise OrderError("This order is not pending.")
        for car_id, qty, brand, model in items:
            s = conn.execute("SELECT stock FROM cars WHERE id=?", (car_id,)).fetchone()
            if not s or int(s[0]) < qty:
                raise OrderError(f"Not enough real stock for {brand} {model}.")
    finally:
        conn.close()
    for car_id, qty, _, _ in items:
        log_order(int(car_id), int(qty), "Website", o[1] or "")
    with get_connection() as c:
        c.execute("UPDATE web_orders SET status='Confirmed' WHERE id=?", (order_id,))


def cancel_order(order_id):
    with get_connection() as c:
        c.execute("UPDATE web_orders SET status='Cancelled' WHERE id=? AND status='Pending'", (order_id,))


def pending_count():
    with get_connection() as c:
        return c.execute("SELECT COUNT(*) FROM web_orders WHERE status='Pending'").fetchone()[0]


def list_orders():
    conn = get_connection()
    try:
        out = []
        for o in conn.execute("SELECT id, created_at, name, phone, city, status, total FROM web_orders ORDER BY id DESC"):
            items = conn.execute("SELECT brand, model, qty, unit_price FROM web_order_items WHERE order_id=?", (o[0],)).fetchall()
            out.append({"id": o[0], "created_at": o[1], "name": o[2], "phone": o[3], "city": o[4],
                        "status": o[5], "total": o[6],
                        "items": [{"brand": i[0], "model": i[1], "qty": i[2], "price": i[3]} for i in items]})
        return out
    finally:
        conn.close()