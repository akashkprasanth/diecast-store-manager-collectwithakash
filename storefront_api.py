"""Public API for the GitHub Pages storefront.

Run:  uvicorn storefront_api:app --host 127.0.0.1 --port 8000
Settings come from environment variables (never put them in the website code):
  ALLOWED_ORIGIN      default https://collectwithakash.github.io
  AUTO_CONFIRM        1 = record the sale instantly; default 0 = you confirm in the Manager
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID   optional: get a message for every new order
"""
import json
import os
import time
import urllib.request
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import web_orders as wo

ORIGIN = os.environ.get("ALLOWED_ORIGIN", "https://collectwithakash.github.io")
AUTO_CONFIRM = os.environ.get("AUTO_CONFIRM", "0") == "1"

wo.init_web_tables()
app = FastAPI(title="Diecast storefront", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=[ORIGIN], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
app.mount("/media", StaticFiles(directory=wo.MEDIA_DIR), name="media")

hits = defaultdict(list)


class Item(BaseModel):
    car_id: int
    qty: int = Field(ge=1, le=50)


class OrderIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    phone: str = Field(pattern=r"^\+?[0-9 ]{7,15}$")
    city: str = Field(default="", max_length=60)
    items: list[Item] = Field(min_length=1, max_length=20)
    website: str = ""  # honeypot: real visitors leave this empty


def notify(text):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    try:
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                     json.dumps({"chat_id": chat, "text": text}).encode(),
                                     {"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


@app.get("/api/cars")
def cars():
    return wo.public_cars()


@app.post("/api/orders")
def place_order(order: OrderIn, request: Request):
    ip = request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "?")
    now = time.time()
    hits[ip] = [t for t in hits[ip] if now - t < 600]
    if len(hits[ip]) >= 5:
        raise HTTPException(429, "Too many orders. Please try again in a few minutes.")
    hits[ip].append(now)
    if order.website:
        return {"order_id": 0, "status": "Pending", "total": 0}
    try:
        res = wo.create_order(order.name.strip(), order.phone.strip(), order.city.strip(),
                              [(i.car_id, i.qty) for i in order.items])
    except wo.OrderError as e:
        raise HTTPException(409, str(e))
    status = "Pending"
    if AUTO_CONFIRM:
        try:
            wo.confirm_order(res["id"])
            status = "Confirmed"
        except wo.OrderError:
            pass
    lines = "\n".join(f"{l[3]} x {l[1]} {l[2]}" for l in res["lines"])
    notify(f"New website order #{res['id']} ({status})\n{order.name} · {order.phone} · {order.city}\n{lines}\nTotal ₹{res['total']:,.2f}")
    return {"order_id": res["id"], "status": status, "total": res["total"]}