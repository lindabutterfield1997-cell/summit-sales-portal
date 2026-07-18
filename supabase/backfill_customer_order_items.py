#!/usr/bin/env python3
"""Backfill Supabase customer_order_items from existing customer_orders payload JSON.

Usage:
  python3 supabase/backfill_customer_order_items.py --dry-run
  python3 supabase/backfill_customer_order_items.py --apply
  python3 supabase/backfill_customer_order_items.py --apply --order-number O-20260715-...

Configuration:
  Reads SUPABASE_URL and SUPABASE_SERVICE_KEY/SUPABASE_KEY from environment.
  If not set, also tries .streamlit/secrets.toml top-level keys.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import error as url_error, parse, request as url_request

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None  # type: ignore[assignment]

APP_DIR = Path(__file__).resolve().parents[1]
SECRETS_PATH = APP_DIR / ".streamlit" / "secrets.toml"
ORDER_SELECT = "id,customer_id,order_number,subtotal,discount,payload"

ORDER_ITEM_COLUMNS = {
    "order_id",
    "customer_id",
    "order_number",
    "line_index",
    "line_id",
    "product_id",
    "product_name",
    "section",
    "category",
    "quantity",
    "width",
    "height",
    "area_sqft",
    "direction",
    "glass",
    "frame",
    "color",
    "notes",
    "unit_price",
    "original_unit_price",
    "line_subtotal",
    "order_discount_allocated",
    "line_total_after_discount",
    "price_adjusted",
    "price_adjustment_mode",
    "inventory_deducted",
    "inventory_deducted_quantity",
    "inventory_short_quantity",
    "production_required",
    "payload",
}


def load_secrets() -> dict[str, Any]:
    if not SECRETS_PATH.exists() or tomllib is None:
        return {}
    with SECRETS_PATH.open("rb") as handle:
        data = tomllib.load(handle)
    return data if isinstance(data, dict) else {}


SECRETS = load_secrets()


def secret_or_env(name: str) -> str:
    value = os.environ.get(name) or SECRETS.get(name) or ""
    return str(value).strip()


def supabase_base_url() -> str:
    raw_url = secret_or_env("SUPABASE_URL").rstrip("/")
    if raw_url.endswith("/rest/v1"):
        raw_url = raw_url[: -len("/rest/v1")]
    parsed = parse.urlsplit(raw_url)
    if parsed.scheme and parsed.netloc and parsed.netloc.endswith(".supabase.co"):
        return f"{parsed.scheme}://{parsed.netloc}"
    return raw_url


def supabase_api_key() -> str:
    return secret_or_env("SUPABASE_SERVICE_KEY") or secret_or_env("SUPABASE_KEY")


def supabase_request(method: str, table: str, query: str = "", payload: Any | None = None, prefer: str = "return=representation") -> Any:
    base_url = supabase_base_url()
    api_key = supabase_api_key()
    if not base_url or not api_key:
        raise RuntimeError("Missing SUPABASE_URL and SUPABASE_SERVICE_KEY/SUPABASE_KEY.")
    url = f"{base_url}/rest/v1/{table}"
    if query:
        url += f"?{query}"
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = url_request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with url_request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
    except url_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase {method} {table} failed: {exc.code} {detail}") from exc
    if not body:
        return []
    return json.loads(body)


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


def order_items(order: dict[str, Any]) -> list[dict[str, Any]]:
    payload = order.get("payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload or "{}")
        except (TypeError, ValueError):
            payload = {}
    items = payload.get("items", []) if isinstance(payload, dict) else []
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def build_item_payloads(order: dict[str, Any]) -> list[dict[str, Any]]:
    items = order_items(order)
    if not items:
        return []
    payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
    subtotal = to_float(order.get("subtotal") or payload.get("subtotal"))
    discount = to_float(order.get("discount") or payload.get("discount"))
    discount_factor = (discount / subtotal) if subtotal > 0 else 0.0
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        quantity = max(to_int(item.get("quantity"), 1), 1)
        width = to_float(item.get("width"))
        height = to_float(item.get("height"))
        line_subtotal = max(to_float(item.get("line_total")), 0.0)
        allocated_discount = min(line_subtotal, line_subtotal * discount_factor)
        line_total_after_discount = max(line_subtotal - allocated_discount, 0.0)
        unit_price = to_float(item.get("unit_price")) or (line_subtotal / quantity if quantity else 0.0)
        original_unit_price = to_float(item.get("original_unit_price")) or unit_price
        area_sqft = to_float(item.get("area_sqft")) or ((width * height / 144) if width and height else 0.0)
        row = {
            "order_id": to_int(order.get("id")),
            "customer_id": to_int(order.get("customer_id")),
            "order_number": str(order.get("order_number") or ""),
            "line_index": index,
            "line_id": str(item.get("line_id") or ""),
            "product_id": str(item.get("product_id") or ""),
            "product_name": str(item.get("name") or item.get("product_name") or item.get("product_id") or "Product"),
            "section": str(item.get("section") or ""),
            "category": str(item.get("category") or ""),
            "quantity": quantity,
            "width": width,
            "height": height,
            "area_sqft": area_sqft,
            "direction": str(item.get("direction") or ""),
            "glass": str(item.get("glass") or ""),
            "frame": str(item.get("frame") or ""),
            "color": str(item.get("color") or ""),
            "notes": str(item.get("notes") or ""),
            "unit_price": unit_price,
            "original_unit_price": original_unit_price,
            "line_subtotal": line_subtotal,
            "order_discount_allocated": allocated_discount,
            "line_total_after_discount": line_total_after_discount,
            "price_adjusted": bool(item.get("price_adjusted", False)),
            "price_adjustment_mode": str(item.get("price_adjustment_mode") or ""),
            "inventory_deducted": bool(item.get("inventory_deducted", False)),
            "inventory_deducted_quantity": to_int(item.get("inventory_deducted_quantity")),
            "inventory_short_quantity": to_int(item.get("inventory_short_quantity")),
            "production_required": bool(item.get("production_required", False)),
            "payload": item,
        }
        rows.append({key: value for key, value in row.items() if key in ORDER_ITEM_COLUMNS})
    return rows


def fetch_orders(limit: int | None = None, order_number: str = "") -> list[dict[str, Any]]:
    params = {"select": ORDER_SELECT, "order": "id.asc"}
    if order_number:
        params["order_number"] = f"eq.{order_number}"
    orders: list[dict[str, Any]] = []
    offset = 0
    page_size = 1000
    while True:
        page_params = dict(params)
        page_params["limit"] = str(page_size)
        page_params["offset"] = str(offset)
        rows = supabase_request("GET", "customer_orders", query=parse.urlencode(page_params), prefer="")
        if not rows:
            break
        orders.extend(rows)
        if limit and len(orders) >= limit:
            return orders[:limit]
        if len(rows) < page_size:
            break
        offset += page_size
    return orders


def backfill(apply: bool, limit: int | None, order_number: str) -> None:
    orders = fetch_orders(limit=limit, order_number=order_number)
    total_items = 0
    skipped = 0
    print(f"Found {len(orders)} order(s).")
    for order in orders:
        item_payloads = build_item_payloads(order)
        total_items += len(item_payloads)
        label = order.get("order_number") or f"order #{order.get('id')}"
        if not item_payloads:
            skipped += 1
            print(f"SKIP {label}: no payload.items")
            continue
        print(f"{'WRITE' if apply else 'DRY'} {label}: {len(item_payloads)} item row(s)")
        if apply:
            delete_query = parse.urlencode({"order_id": f"eq.{to_int(order.get('id'))}"})
            supabase_request("DELETE", "customer_order_items", query=delete_query, prefer="return=minimal")
            supabase_request("POST", "customer_order_items", payload=item_payloads, prefer="return=minimal")
    print(f"Done. {'Inserted' if apply else 'Would insert'} {total_items} item row(s). Skipped {skipped} order(s).")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill customer_order_items from customer_orders payload JSON.")
    parser.add_argument("--apply", action="store_true", help="Actually delete/reinsert customer_order_items rows.")
    parser.add_argument("--dry-run", action="store_true", help="Preview only. This is the default.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N orders.")
    parser.add_argument("--order-number", default="", help="Only process one order number.")
    args = parser.parse_args()
    apply = bool(args.apply)
    if not apply:
        print("Dry run mode. Add --apply to write to Supabase.")
    try:
        backfill(apply=apply, limit=args.limit, order_number=args.order_number.strip())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
