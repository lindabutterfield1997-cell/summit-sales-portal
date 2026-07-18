#!/usr/bin/env python3
"""Export historical Supabase customer_orders payload.items to a CSV file.

Usage:
  SUPABASE_URL="https://xxx.supabase.co" SUPABASE_SERVICE_KEY="..." \
    python3 supabase/export_customer_order_items_csv.py

Optional:
  python3 supabase/export_customer_order_items_csv.py --output output/customer_order_items.csv
  python3 supabase/export_customer_order_items_csv.py --order-number O-20260715-...
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import error as url_error, parse, request as url_request

APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = APP_DIR / "output" / "customer_order_items_export.csv"
ORDER_SELECT = "id,customer_id,order_number,quote_number,order_date,salesperson,subtotal,discount,tax,installation,shipping,total,payload"
CSV_FIELDS = [
    "order_id", "customer_id", "order_number", "quote_number", "order_date", "salesperson",
    "line_index", "line_id", "product_id", "product_name", "section", "category",
    "quantity", "width", "height", "area_sqft", "direction", "glass", "frame", "color", "notes",
    "unit_price", "original_unit_price", "line_subtotal", "order_discount_allocated", "line_total_after_discount",
    "price_adjusted", "price_adjustment_mode", "inventory_deducted", "inventory_deducted_quantity",
    "inventory_short_quantity", "production_required", "order_subtotal", "order_discount", "order_tax",
    "order_shipping", "order_installation", "order_total",
]


def env(name: str) -> str:
    return str(os.environ.get(name, "")).strip()


def supabase_base_url() -> str:
    raw_url = env("SUPABASE_URL").rstrip("/")
    if raw_url.endswith("/rest/v1"):
        raw_url = raw_url[: -len("/rest/v1")]
    parsed = parse.urlsplit(raw_url)
    if parsed.scheme and parsed.netloc and parsed.netloc.endswith(".supabase.co"):
        return f"{parsed.scheme}://{parsed.netloc}"
    return raw_url


def supabase_key() -> str:
    return env("SUPABASE_SERVICE_KEY") or env("SUPABASE_KEY")


def supabase_request(table: str, query: str = "") -> Any:
    base_url = supabase_base_url()
    key = supabase_key()
    if not base_url or not key:
        raise RuntimeError("Missing SUPABASE_URL and SUPABASE_SERVICE_KEY/SUPABASE_KEY environment variables.")
    url = f"{base_url}/rest/v1/{table}"
    if query:
        url += f"?{query}"
    req = url_request.Request(
        url,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with url_request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
    except url_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase GET {table} failed: {exc.code} {detail}") from exc
    return json.loads(body) if body else []


def to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def order_payload(order: dict[str, Any]) -> dict[str, Any]:
    payload = order.get("payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload or "{}")
        except (TypeError, ValueError):
            payload = {}
    return payload if isinstance(payload, dict) else {}


def export_rows_for_order(order: dict[str, Any]) -> list[dict[str, Any]]:
    payload = order_payload(order)
    items = payload.get("items", [])
    if not isinstance(items, list):
        return []
    subtotal = to_float(order.get("subtotal") or payload.get("subtotal"))
    discount = to_float(order.get("discount") or payload.get("discount"))
    discount_factor = (discount / subtotal) if subtotal > 0 else 0.0
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        quantity = max(to_int(item.get("quantity"), 1), 1)
        width = to_float(item.get("width"))
        height = to_float(item.get("height"))
        line_subtotal = max(to_float(item.get("line_total")), 0.0)
        allocated_discount = min(line_subtotal, line_subtotal * discount_factor)
        unit_price = to_float(item.get("unit_price")) or (line_subtotal / quantity if quantity else 0.0)
        original_unit_price = to_float(item.get("original_unit_price")) or unit_price
        area_sqft = to_float(item.get("area_sqft")) or ((width * height / 144) if width and height else 0.0)
        rows.append({
            "order_id": order.get("id") or "",
            "customer_id": order.get("customer_id") or "",
            "order_number": order.get("order_number") or "",
            "quote_number": order.get("quote_number") or "",
            "order_date": order.get("order_date") or "",
            "salesperson": order.get("salesperson") or "",
            "line_index": index,
            "line_id": item.get("line_id") or "",
            "product_id": item.get("product_id") or "",
            "product_name": item.get("name") or item.get("product_name") or item.get("product_id") or "Product",
            "section": item.get("section") or "",
            "category": item.get("category") or "",
            "quantity": quantity,
            "width": width,
            "height": height,
            "area_sqft": area_sqft,
            "direction": item.get("direction") or "",
            "glass": item.get("glass") or "",
            "frame": item.get("frame") or "",
            "color": item.get("color") or "",
            "notes": item.get("notes") or "",
            "unit_price": unit_price,
            "original_unit_price": original_unit_price,
            "line_subtotal": line_subtotal,
            "order_discount_allocated": allocated_discount,
            "line_total_after_discount": max(line_subtotal - allocated_discount, 0.0),
            "price_adjusted": bool(item.get("price_adjusted", False)),
            "price_adjustment_mode": item.get("price_adjustment_mode") or "",
            "inventory_deducted": bool(item.get("inventory_deducted", False)),
            "inventory_deducted_quantity": to_int(item.get("inventory_deducted_quantity")),
            "inventory_short_quantity": to_int(item.get("inventory_short_quantity")),
            "production_required": bool(item.get("production_required", False)),
            "order_subtotal": subtotal,
            "order_discount": discount,
            "order_tax": to_float(order.get("tax") or payload.get("tax")),
            "order_shipping": to_float(order.get("shipping") or payload.get("shipping_fee")),
            "order_installation": to_float(order.get("installation") or payload.get("installation_fee")),
            "order_total": to_float(order.get("total") or payload.get("total")),
        })
    return rows


def fetch_orders(order_number: str = "") -> list[dict[str, Any]]:
    base_params = {"select": ORDER_SELECT, "order": "id.asc"}
    if order_number:
        base_params["order_number"] = f"eq.{order_number}"
    orders: list[dict[str, Any]] = []
    offset = 0
    while True:
        params = dict(base_params)
        params["limit"] = "1000"
        params["offset"] = str(offset)
        rows = supabase_request("customer_orders", parse.urlencode(params))
        if not rows:
            break
        orders.extend(rows)
        if len(rows) < 1000:
            break
        offset += 1000
    return orders


def main() -> int:
    parser = argparse.ArgumentParser(description="Export historical customer order items to CSV.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="CSV output path.")
    parser.add_argument("--order-number", default="", help="Only export one order number.")
    args = parser.parse_args()
    try:
        orders = fetch_orders(args.order_number.strip())
        rows = []
        skipped = 0
        for order in orders:
            item_rows = export_rows_for_order(order)
            if not item_rows:
                skipped += 1
            rows.extend(item_rows)
        output = Path(args.output).expanduser()
        if not output.is_absolute():
            output = APP_DIR / output
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Exported {len(rows)} item row(s) from {len(orders)} order(s). Skipped {skipped} order(s) without payload.items.")
        print(f"CSV: {output}")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
