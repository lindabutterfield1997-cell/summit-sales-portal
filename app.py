from __future__ import annotations

import base64
import csv
import hashlib
import html
import io
import json
import os
import re
import secrets
import smtplib
import sqlite3
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Sequence
from urllib import error as url_error, parse, request as url_request

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageFont, ImageOps
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


APP_DIR = Path(__file__).resolve().parent
ASSET_DIR = APP_DIR / "assets" / "products"
UPLOAD_DIR = ASSET_DIR / "uploads"
ORIGINAL_UPLOAD_DIR = ASSET_DIR / "originals"
DATA_DIR = APP_DIR / "data"
PRODUCT_FILE = DATA_DIR / "products.json"
IMAGE_MIGRATION_MARKER = DATA_DIR / ".image-ratio-3x2-v1"
PRODUCT_IMAGE_SIZE = (1500, 1000)
OUTPUT_DIR = APP_DIR / "output" / "pdf"
DB_PATH = APP_DIR / "quotes.db"
DB_TIMEOUT_SECONDS = 30


def db_connect(*, isolation_level: str | None = "DEFERRED") -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=DB_TIMEOUT_SECONDS, isolation_level=isolation_level)
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


OPENING_STYLE_DIR = APP_DIR / "assets" / "opening_styles"
OPENING_DIRECTION_DIR = APP_DIR / "assets" / "opening_directions"
BRANDING_DIR = APP_DIR / "assets" / "branding"
COMPANY_LOGO_PATH = BRANDING_DIR / "summit-logo.png"
COMPANY_NAME = "SUMMIT Windows & Doors"
BRAND_BLUE = "#252B60"
BRAND_SKY = "#22ADD7"
BRAND_LIGHT = "#EAF4FA"
BRAND_LINE = "#9FB7CC"
FIXED_SALES_TAX_RATE = 0.0775

st.set_page_config(
    page_title="FrameFlow | Doors & Windows",
    page_icon="▦",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@dataclass(frozen=True)
class Product:
    id: str
    section: str
    category: str
    name: str
    subtitle: str
    description: str
    base_rate: float
    minimum_price: float
    directions: tuple[str, ...]
    glass_colors: tuple[str, ...]
    frame_colors: tuple[str, ...]
    accent: str
    hero_image: str = ""
    detail_images: tuple[str, ...] = ()
    active: bool = True
    updated_at: str = ""
    color_options: tuple[str, ...] = ()
    color_information: str = ""
    stock_information: str = ""


DEFAULT_PRODUCTS = [
    Product("SD-100", "Doors", "Sliding Door", "Horizon Sliding Door", "Slim interlock profile", "A clean, contemporary slider designed for wide openings and smooth everyday operation.", 50.0, 0.0, ("Left opening", "Right opening", "Center opening"), ("Clear", "Low-E", "Grey", "Bronze", "Frosted"), ("Black", "White", "Charcoal", "Bronze"), "#64746a"),
    Product("HD-210", "Doors", "Hinge Door", "Axis Hinge Door", "Strong thermal frame", "A refined single or double hinge door with dependable seals and flexible hardware.", 45.0, 0.0, ("Left inswing", "Right inswing", "Left outswing", "Right outswing"), ("Clear", "Low-E", "Grey", "Bronze", "Frosted"), ("Black", "White", "Charcoal", "Bronze"), "#8d674f"),
    Product("BD-310", "Doors", "Bifold Door", "Vista Bifold Door", "Indoor-outdoor living", "Large folding panels stack neatly to one side, opening the room to the outdoors.", 50.0, 0.0, ("Stack left", "Stack right", "Split stack"), ("Clear", "Low-E", "Grey", "Bronze"), ("Black", "White", "Charcoal", "Bronze"), "#6d7d7b"),
    Product("WD-410", "Doors", "Wood Door", "Heritage Wood Door", "Natural timber character", "A warm architectural entry door with customizable stain, glass and handing.", 50.0, 0.0, ("Left inswing", "Right inswing", "Left outswing", "Right outswing"), ("No glass", "Clear", "Frosted", "Bronze"), ("Oak", "Walnut", "Mahogany", "Paint grade"), "#9b7047"),
    Product("GD-510", "Doors", "Garage Door", "Linea Garage Door", "Quiet sectional system", "A modern insulated garage door with horizontal detailing and optional vision panels.", 50.0, 0.0, ("Standard lift", "High lift"), ("No glass", "Clear", "Grey", "Frosted"), ("Black", "White", "Charcoal", "Bronze"), "#5d6262"),
    Product("PD-610", "Doors", "Pivot Door", "Monument Pivot Door", "Statement entrance", "An oversized pivot entry with balanced movement, concealed hardware and bold proportions.", 120.0, 0.0, ("Pivot left", "Pivot right"), ("No glass", "Clear", "Grey", "Bronze", "Frosted"), ("Black", "White", "Charcoal", "Bronze"), "#4d4e49"),
    Product("CW-110", "Windows", "Casement Window", "Breeze Casement Window", "Maximum ventilation", "A versatile outward-opening window with secure multi-point hardware and clean sightlines.", 96.0, 620.0, ("Hinge left", "Hinge right"), ("Clear", "Low-E", "Grey", "Bronze", "Frosted"), ("Black", "White", "Charcoal", "Bronze"), "#6f7f79"),
    Product("BW-220", "Windows", "Bifold Window", "Servery Bifold Window", "Open-air connection", "Folding window panels create a generous opening for kitchens, bars and entertaining spaces.", 148.0, 1700.0, ("Stack left", "Stack right", "Split stack"), ("Clear", "Low-E", "Grey", "Bronze"), ("Black", "White", "Charcoal", "Bronze"), "#7e8179"),
    Product("FW-330", "Windows", "Fixed Window", "Picture Fixed Window", "Uninterrupted views", "A non-opening picture window with excellent weather performance and minimal visual interruption.", 74.0, 480.0, ("Fixed",), ("Clear", "Low-E", "Grey", "Bronze", "Frosted"), ("Black", "White", "Charcoal", "Bronze"), "#78848b"),
    Product("BH-440", "Windows", "Bottom Hung Window", "Awning Bottom Hung", "Controlled airflow", "A compact window hinged along the bottom for secure, measured ventilation.", 104.0, 680.0, ("Handle left", "Handle right", "Top handle"), ("Clear", "Low-E", "Grey", "Bronze", "Frosted"), ("Black", "White", "Charcoal", "Bronze"), "#727f86"),
    Product("SW-550", "Windows", "Sliding Window", "Glide Sliding Window", "Simple horizontal movement", "A practical sliding window with removable sash and low-friction rollers.", 88.0, 560.0, ("Left opening", "Right opening", "Both sides"), ("Clear", "Low-E", "Grey", "Bronze", "Frosted"), ("Black", "White", "Charcoal", "Bronze"), "#5f746e"),
]
PRODUCTS: list[Product] = []

OPENING_STYLES = {
    "Doors": [
        {"label": "Sliding Door", "category": "Sliding Door", "icon": "door-sliding"},
        {"label": "Hinge Door", "category": "Hinge Door", "icon": "door-hinge"},
        {"label": "Bifold Door", "category": "Bifold Door", "icon": "door-bifold"},
        {"label": "Wood Door", "category": "Wood Door", "icon": "door-single"},
        {"label": "Garage Door", "category": "Garage Door", "icon": "door-garage"},
        {"label": "Pivot Door", "category": "Pivot Door", "icon": "door-pivot"},
    ],
    "Windows": [
        {"label": "Casement Window", "category": "Casement Window", "icon": "window-casement"},
        {"label": "Bifold Window", "category": "Bifold Window", "icon": "window-bifold"},
        {"label": "Single Hung Window", "category": "Single Hung Window", "icon": "window-single-hung"},
        {"label": "Awning Window", "category": "Awning Window", "icon": "window-awning"},
        {"label": "Tilt and Turn Window", "category": "Tilt and Turn Window", "icon": "window-tilt-turn"},
        {"label": "Fixed Window", "category": "Fixed Window", "icon": "window-fixed"},
        {"label": "Bottom Hung Window", "category": "Bottom Hung Window", "icon": "window-awning"},
        {"label": "Sliding Window", "category": "Sliding Window", "icon": "window-sliding"},
    ],
}


def css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700&display=swap');
        :root { --ink:#17201c; --muted:#69716d; --line:#dfe4e0; --paper:#f7f8f5; --sage:#dbe5dc; --dark:#1e2b25; }
        html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
        .stApp { background:#f7f8f5; color:var(--ink); }
        .block-container { padding-top:1.15rem; padding-bottom:5rem; max-width:1440px; }
        h1,h2,h3 { font-family:'Manrope',sans-serif; letter-spacing:-.035em; }
        [data-testid="stHeader"] { background:transparent; height:0; pointer-events:none; }
        [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display:none; }
        .brand { display:flex; align-items:center; gap:12px; font:700 20px 'Manrope'; }
        .mark { width:34px;height:34px;background:#23342c;color:white;border-radius:10px;display:grid;place-items:center;font-size:17px; }
        .topbar { display:flex; justify-content:space-between; align-items:center; padding:4px 2px 16px; border-bottom:1px solid var(--line); margin-bottom:18px; }
        .eyebrow { font-size:12px;text-transform:uppercase;letter-spacing:.14em;color:#68736d;font-weight:700; }
        .hero { background:#e5ebe5; border-radius:24px; padding:38px 42px; margin:8px 0 24px; border:1px solid #d8dfd9; }
        .hero h1 { font-size:48px;max-width:760px;margin:8px 0 12px;line-height:1.06; }
        .hero p { color:#59635e;max-width:650px;font-size:17px;margin:0; }
        .product-card { background:white;border:1px solid var(--line);border-radius:18px;padding:12px;margin-bottom:10px;min-height:222px; }
        .product-card h3 { font-size:18px;margin:11px 0 2px; }
        .product-card p { color:var(--muted);font-size:13px;margin:0 0 8px; }
        .product-card .price { font-size:13px;color:#33483e;font-weight:700; }
        .opening-heading { font:800 22px 'Manrope'; margin:6px 0 12px; letter-spacing:0; }
        .opening-card { background:#fff;border:1px solid #e4e7e3;border-radius:8px;padding:12px 10px 8px;text-align:center;min-height:132px;display:grid;place-items:center; }
        .opening-card.active { border:2px solid #23342c;background:#f2f5f1; }
        .opening-card-title { font:800 14px 'Manrope'; color:#111; margin-top:7px; min-height:32px; display:flex; align-items:center; justify-content:center; line-height:1.12; }
        .opening-card img { width:96px; height:76px; object-fit:contain; margin:0 auto; display:block; }
        .direction-visual { background:#fff;border:1px solid #dfe4e0;border-radius:14px;padding:12px 14px;margin:10px 0 14px;display:flex;gap:14px;align-items:center; }
        .direction-visual img { width:168px;max-width:42%;height:auto;object-fit:contain;border-radius:10px;background:#f8faf9; }
        .direction-visual-title { font:800 14px 'Manrope';color:#17201c;margin-bottom:3px; }
        .direction-visual-copy { color:#65706a;font-size:12.5px;line-height:1.35; }
        div[data-testid="stImage"] img { aspect-ratio:3/2; object-fit:cover; }
        .pill { display:inline-block;border:1px solid #cad4cd;border-radius:999px;padding:6px 11px;font-size:12px;margin:2px 5px 2px 0;background:#fff; }
        .summary-card { background:#202e27;color:white;border-radius:20px;padding:22px;position:sticky;top:70px; }
        .summary-card .muted { color:#b9c7bf;font-size:13px; }
        .summary-card .total { font:700 29px 'Manrope';margin-top:8px; }
        .empty { padding:34px;border:1px dashed #bdc8c0;border-radius:18px;text-align:center;color:#6c756f;background:#fbfcfa; }
        .quote-head { background:#25362e;color:white;padding:26px;border-radius:20px;margin-bottom:18px; }
        div[data-testid="stButton"] button { border-radius:10px;font-weight:650;min-height:42px; }
        div[data-testid="stFormSubmitButton"] button { background:#23342c;color:white;border:none; }
        div[data-testid="stDownloadButton"] button { width:100%;background:#dbe5dc;color:#203128;border:none; }
        [data-testid="stMetric"] { background:white;border:1px solid var(--line);padding:14px;border-radius:14px; }
        .thumb-note { color:#7a827e;font-size:12px;margin-top:-4px; }
        .footer { color:#818983;text-align:center;border-top:1px solid var(--line);padding-top:22px;margin-top:50px;font-size:12px; }
        @media(max-width:800px){ .hero{padding:25px}.hero h1{font-size:34px}.block-container{padding-left:1rem;padding-right:1rem} }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    defaults = {
        "cart": [],
        "page": "Catalog",
        "section": "Doors",
        "category": "All doors",
        "selected_product": None,
        "last_quote": None,
        "employee_authenticated": False,
        "employee_name": "",
        "admin_authenticated": False,
        "admin_editor_id": None,
        "customer_editor_id": None,
        "inline_customer_editor_id": None,
        "inventory_editor_id": None,
        "service_customer_id": None,
        "service_editor_id": None,
        "active_customer_id": None,
        "wishlist_draft": [],
        "quote_discount_type": "No discount",
        "quote_discount_value": 0.0,
        "quote_installation_fee": 0.0,
        "quote_shipping_fee": 0.0,
        "quote_shipping_enabled": False,
        "quote_sales_tax_enabled": False,
        "checkout_quote_adjustments": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def init_db() -> None:
    with db_connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quotes (
                quote_number TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                customer_email TEXT NOT NULL,
                customer_phone TEXT,
                customer_address TEXT,
                subtotal REAL NOT NULL,
                tax REAL NOT NULL,
                total REAL NOT NULL,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                customer_id INTEGER
            )
            """
        )
        quote_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(quotes)").fetchall()
        }
        if "customer_id" not in quote_columns:
            conn.execute("ALTER TABLE quotes ADD COLUMN customer_id INTEGER")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL,
                name TEXT NOT NULL,
                company TEXT,
                email TEXT,
                phone TEXT,
                address TEXT,
                products_interest TEXT,
                client_type TEXT,
                client_type_note TEXT,
                project_type TEXT,
                project_type_note TEXT,
                use_case TEXT,
                use_case_note TEXT,
                area_zip TEXT,
                area_zip_note TEXT,
                showroom_status TEXT,
                showroom_note TEXT,
                answer_status TEXT,
                answer_status_note TEXT,
                source TEXT,
                initial_contact_date TEXT,
                priority TEXT,
                budget REAL,
                assigned_to TEXT,
                notes TEXT,
                first_followup_date TEXT,
                next_followup_date TEXT,
                followup_stage TEXT,
                on_hold INTEGER DEFAULT 0,
                order_date TEXT,
                first_payment_date TEXT,
                first_payment_amount REAL DEFAULT 0,
                first_payment_paid INTEGER DEFAULT 0,
                second_payment_enabled INTEGER DEFAULT 1,
                second_payment_date TEXT,
                second_payment_amount REAL DEFAULT 0,
                second_payment_paid INTEGER DEFAULT 0,
                install_followup_date TEXT,
                install_status TEXT,
                lost_date TEXT,
                lost_reason TEXT,
                lost_notes TEXT,
                wishlist TEXT DEFAULT '[]'
            )
            """
        )
        existing_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(customers)").fetchall()
        }
        if "wishlist" not in existing_columns:
            conn.execute("ALTER TABLE customers ADD COLUMN wishlist TEXT DEFAULT '[]'")
        if "initial_contact_date" not in existing_columns:
            conn.execute("ALTER TABLE customers ADD COLUMN initial_contact_date TEXT")
            conn.execute(
                """
                UPDATE customers
                SET initial_contact_date = substr(created_at, 1, 10)
                WHERE initial_contact_date IS NULL OR initial_contact_date = ''
                """
            )
        profile_columns = {
            "client_type": "TEXT",
            "client_type_note": "TEXT",
            "project_type": "TEXT",
            "project_type_note": "TEXT",
            "use_case": "TEXT",
            "use_case_note": "TEXT",
            "area_zip": "TEXT",
            "area_zip_note": "TEXT",
            "showroom_status": "TEXT",
            "showroom_note": "TEXT",
            "answer_status": "TEXT",
            "answer_status_note": "TEXT",
        }
        for column, column_type in profile_columns.items():
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE customers ADD COLUMN {column} {column_type}")
        payment_columns = {
            "first_payment_paid": "INTEGER DEFAULT 0",
            "second_payment_enabled": "INTEGER DEFAULT 1",
            "second_payment_paid": "INTEGER DEFAULT 0",
        }
        existing_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(customers)").fetchall()
        }
        for column, column_type in payment_columns.items():
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE customers ADD COLUMN {column} {column_type}")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customer_carts (
                customer_id INTEGER PRIMARY KEY,
                updated_at TEXT NOT NULL,
                payload TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customer_timeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                event_date TEXT NOT NULL,
                title TEXT NOT NULL,
                notes TEXT,
                quote_number TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                product_id TEXT NOT NULL,
                sku TEXT,
                received_date TEXT NOT NULL,
                warehouse TEXT,
                location TEXT,
                width REAL DEFAULT 0,
                height REAL DEFAULT 0,
                color TEXT,
                glass TEXT,
                frame TEXT,
                direction TEXT,
                quantity INTEGER NOT NULL DEFAULT 0,
                reserved_quantity INTEGER NOT NULL DEFAULT 0,
                unit_cost REAL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Available',
                notes TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS service_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_number TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                customer_id INTEGER,
                customer_name TEXT NOT NULL,
                customer_email TEXT,
                customer_phone TEXT,
                project_address TEXT,
                quote_number TEXT,
                product_id TEXT,
                product_name TEXT NOT NULL,
                product_snapshot TEXT NOT NULL,
                damaged_part TEXT NOT NULL,
                damage_reason TEXT NOT NULL,
                issue_description TEXT NOT NULL,
                appointment_date TEXT,
                assigned_to TEXT,
                internal_notes TEXT,
                completed_at TEXT,
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS service_timeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_request_id INTEGER NOT NULL,
                event_date TEXT NOT NULL,
                status TEXT NOT NULL,
                title TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(service_request_id) REFERENCES service_requests(id)
            )
            """
        )
        normalize_legacy_database_labels(conn)
        default_owner = current_employee_name()
        if default_owner:
            conn.execute(
                """
                UPDATE customers
                SET assigned_to = ?
                WHERE assigned_to IS NULL OR assigned_to = ''
                """,
                (default_owner,),
            )


def product_to_dict(product: Product) -> dict[str, Any]:
    data = asdict(product)
    for key in ("directions", "glass_colors", "frame_colors", "color_options", "detail_images"):
        data[key] = list(data[key])
    return data


def product_from_dict(data: dict[str, Any]) -> Product:
    allowed = {field.name for field in fields(Product)}
    clean = {key: value for key, value in data.items() if key in allowed}
    for key in ("directions", "glass_colors", "frame_colors", "color_options", "detail_images"):
        clean[key] = tuple(clean.get(key, ()))
    if not clean.get("color_options"):
        clean["color_options"] = clean.get("frame_colors", ())
    return Product(**clean)


def uses_placeholder_product_image(product: Product) -> bool:
    return "normalized-0.webp" in product.hero_image


def hide_placeholder_products(products: list[Product]) -> list[Product]:
    cleaned: list[Product] = []
    for product in products:
        if uses_placeholder_product_image(product) and product.active:
            cleaned.append(Product(**{**asdict(product), "active": False}))
        else:
            cleaned.append(product)
    return cleaned


def is_pivot_door(product: Product) -> bool:
    return product.section == "Doors" and "pivot" in product.category.lower()


def is_hinge_door(product: Product) -> bool:
    return product.section == "Doors" and "hinge" in product.category.lower()


def door_priced_product(product: Product) -> Product:
    return product


def apply_door_pricing_policy(products: list[Product]) -> list[Product]:
    # Catalog pricing is admin-managed. Startup should never rewrite saved rates or minimums.
    return list(products)


def seed_product_images(product: Product) -> Product:
    hero = product.hero_image or f"{product.id.lower()}-hero.png"
    details = product.detail_images or (f"{product.id.lower()}-detail.png",)
    return Product(**{**asdict(product), "hero_image": hero, "detail_images": tuple(details)})


def save_products(products: list[Product]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    suffix = datetime.now().strftime("%Y%m%d%H%M%S%f")
    temporary = PRODUCT_FILE.with_name(f"{PRODUCT_FILE.name}.{os.getpid()}.{suffix}.tmp")
    try:
        temporary.write_text(
            json.dumps([product_to_dict(product) for product in products], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(PRODUCT_FILE)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_products() -> list[Product]:
    if not PRODUCT_FILE.exists():
        seeded = apply_door_pricing_policy([seed_product_images(product) for product in DEFAULT_PRODUCTS])
        save_products(seeded)
        return seeded
    try:
        data = json.loads(PRODUCT_FILE.read_text(encoding="utf-8"))
        loaded = [product_from_dict(item) for item in data]
        cleaned = hide_placeholder_products(apply_door_pricing_policy(loaded))
        if [product_to_dict(product) for product in cleaned] != [product_to_dict(product) for product in loaded]:
            save_products(cleaned)
        return cleaned
    except (OSError, ValueError, TypeError) as exc:
        st.error(f"Product catalog could not be loaded: {exc}")
        if PRODUCTS:
            return PRODUCTS
        st.stop()


def reload_products() -> None:
    global PRODUCTS
    PRODUCTS = load_products()


def image_path(product: Product, variant: str) -> Path:
    if variant == "hero":
        filename = product.hero_image or f"{product.id.lower()}-hero.png"
    else:
        filename = product.detail_images[0] if product.detail_images else f"{product.id.lower()}-detail.png"
    return ASSET_DIR / filename


def detail_image_paths(product: Product) -> list[Path]:
    filenames = product.detail_images or (f"{product.id.lower()}-detail.png",)
    return [ASSET_DIR / filename for filename in filenames if (ASSET_DIR / filename).exists()]


def make_product_image(product: Product, variant: str) -> None:
    path = image_path(product, variant)
    if path.exists():
        return
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    width, height = (1200, 760) if variant == "hero" else (1200, 760)
    image = Image.new("RGB", (width, height), product.accent)
    draw = ImageDraw.Draw(image)
    pale = "#e7ece8"
    dark = "#253029"
    glass = "#b7c8c8"
    # Abstract architectural room
    draw.rectangle((0, 0, width, 470), fill=pale)
    draw.rectangle((0, 470, width, height), fill="#c8bca9")
    draw.polygon([(0, 470), (width, 390), (width, height), (0, height)], fill="#bcae9b")
    if variant == "hero":
        x1, y1, x2, y2 = 350, 115, 920, 625
        draw.rectangle((x1, y1, x2, y2), fill=dark)
        draw.rectangle((x1 + 24, y1 + 24, x2 - 24, y2 - 24), fill=glass)
        panels = 4 if "Bifold" in product.category else 2
        for i in range(1, panels):
            x = x1 + (x2 - x1) * i // panels
            draw.line((x, y1, x, y2), fill=dark, width=14)
        draw.ellipse((120, 390, 290, 560), fill="#6f806f")
        draw.rectangle((178, 540, 234, 665), fill="#775d45")
    else:
        draw.rectangle((130, 100, 1070, 645), fill="#f4f5f2", outline=dark, width=18)
        draw.rectangle((210, 175, 990, 565), fill=glass, outline=dark, width=14)
        draw.line((600, 175, 600, 565), fill=dark, width=12)
        draw.rounded_rectangle((560, 350, 640, 378), 10, fill="#a08153")
        draw.line((210, 610, 990, 610), fill="#738078", width=3)
    try:
        font_big = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 38)
        font_small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
    except OSError:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()
    draw.rounded_rectangle((40, 35, 500, 130), 18, fill="#ffffffdd")
    draw.text((68, 52), product.name, fill=dark, font=font_big)
    draw.text((70, 98), "Room view" if variant == "hero" else "Product detail", fill="#59645e", font=font_small)
    image = ImageOps.fit(image, PRODUCT_IMAGE_SIZE, method=Image.Resampling.LANCZOS)
    image.save(path, quality=92)


def opening_style_path(icon_id: str) -> Path:
    return OPENING_STYLE_DIR / f"{icon_id}.png"


def opening_direction_path(icon_id: str) -> Path:
    return OPENING_DIRECTION_DIR / f"{icon_id}.png"


def make_opening_style_icon(icon_id: str) -> None:
    path = opening_style_path(icon_id)
    if path.exists():
        return
    OPENING_STYLE_DIR.mkdir(parents=True, exist_ok=True)
    width, height = 520, 360
    image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    frame = "#6f7674"
    shadow = "#b7c0bd"
    glass = "#eaf0f2"
    open_glass = "#f6f8f8"
    accent = "#9eb2bc"

    def rect(box: tuple[int, int, int, int], fill: str = glass, outline: str = frame, line: int = 7) -> None:
        draw.rectangle(box, fill=fill, outline=outline, width=line)

    def panel(box: tuple[int, int, int, int], fill: str = glass) -> None:
        rect(box, fill=fill)
        x1, y1, x2, y2 = box
        draw.rectangle((x1 + 18, y1 + 22, x2 - 18, y2 - 22), outline=shadow, width=4)

    if icon_id == "door-sliding":
        rect((115, 76, 405, 286), "#f8faf9")
        panel((140, 96, 260, 266))
        panel((260, 96, 380, 266))
        draw.line((258, 96, 258, 266), fill=frame, width=7)
    elif icon_id == "door-hinge":
        panel((170, 70, 340, 290))
        draw.arc((178, 84, 328, 234), 270, 360, fill=accent, width=5)
        draw.ellipse((306, 178, 318, 190), fill=frame)
    elif icon_id == "door-bifold":
        draw.polygon([(132, 88), (220, 66), (220, 284), (132, 262)], fill=open_glass, outline=frame)
        draw.polygon([(220, 66), (304, 92), (304, 260), (220, 284)], fill=glass, outline=frame)
        draw.polygon([(304, 92), (388, 72), (388, 278), (304, 260)], fill=open_glass, outline=frame)
        draw.line((220, 66, 220, 284), fill=frame, width=7)
        draw.line((304, 92, 304, 260), fill=frame, width=7)
    elif icon_id == "door-single":
        panel((195, 62, 325, 292), "#f2f0ea")
        for y in (105, 165, 225):
            draw.rectangle((218, y, 302, y + 32), outline=shadow, width=4)
        draw.ellipse((294, 178, 306, 190), fill=frame)
    elif icon_id == "door-garage":
        rect((108, 92, 412, 272), "#f5f6f4")
        for y in (132, 172, 212):
            draw.line((108, y, 412, y), fill=shadow, width=5)
        draw.rectangle((140, 112, 212, 152), outline=accent, width=4)
        draw.rectangle((308, 112, 380, 152), outline=accent, width=4)
    elif icon_id == "door-pivot":
        draw.rectangle((170, 70, 348, 292), outline=frame, width=7)
        draw.polygon([(220, 78), (356, 108), (356, 260), (220, 288)], fill=open_glass, outline=frame)
        draw.line((222, 78, 222, 288), fill=frame, width=7)
        draw.arc((170, 74, 368, 272), 285, 45, fill=accent, width=5)
    elif icon_id == "window-casement":
        rect((174, 74, 346, 286), "#f8faf9")
        draw.polygon([(194, 96), (326, 70), (326, 292), (194, 264)], fill=glass, outline=frame)
        draw.line((194, 96, 194, 264), fill=frame, width=7)
    elif icon_id == "window-bifold":
        rect((108, 98, 412, 260), "#f8faf9")
        for points in (
            [(132, 116), (200, 98), (200, 260), (132, 242)],
            [(200, 98), (260, 116), (260, 242), (200, 260)],
            [(260, 116), (320, 100), (320, 258), (260, 242)],
            [(320, 100), (388, 118), (388, 240), (320, 258)],
        ):
            draw.polygon(points, fill=glass, outline=frame)
    elif icon_id == "window-fixed":
        panel((150, 76, 370, 284))
    elif icon_id == "window-single-hung":
        rect((168, 56, 352, 304), "#f8faf9")
        panel((188, 76, 332, 178))
        panel((188, 178, 332, 284))
        draw.line((188, 178, 332, 178), fill=accent, width=8)
    elif icon_id == "window-awning":
        rect((136, 94, 384, 266), "#f8faf9")
        draw.polygon([(160, 112), (360, 112), (338, 250), (182, 250)], fill=glass, outline=frame)
        draw.arc((158, 102, 362, 292), 20, 160, fill=accent, width=5)
    elif icon_id == "window-tilt-turn":
        rect((150, 58, 370, 304), "#f8faf9")
        draw.polygon([(190, 92), (334, 72), (334, 284), (190, 270)], fill=open_glass, outline=frame)
        draw.line((190, 92, 190, 270), fill=frame, width=7)
        draw.arc((154, 72, 360, 286), 280, 35, fill=accent, width=5)
        draw.arc((186, 82, 344, 302), 205, 330, fill=accent, width=4)
        draw.ellipse((298, 176, 310, 188), fill=frame)
    elif icon_id == "window-sliding":
        rect((110, 100, 410, 260), "#f8faf9")
        panel((136, 118, 250, 242))
        panel((250, 118, 384, 242))
        draw.line((250, 118, 250, 242), fill=frame, width=7)

    image.save(path)


def make_opening_direction_icon(icon_id: str) -> None:
    path = opening_direction_path(icon_id)
    if path.exists():
        return
    OPENING_DIRECTION_DIR.mkdir(parents=True, exist_ok=True)
    base_width, base_height = 760, 430
    scale = 3
    width, height = base_width * scale, base_height * scale
    image = Image.new("RGBA", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)
    wall = "#111111"
    symbol = "#8D9291"
    light_symbol = "#C6CBC9"
    text = "#565F5A"
    blue = "#252B60"

    try:
        label_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 18 * scale)
        small_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 14 * scale)
        tiny_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 12 * scale)
    except OSError:
        label_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
        tiny_font = ImageFont.load_default()

    def n(value: float) -> int:
        return round(value * scale)

    def box(values: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
        return tuple(n(value) for value in values)  # type: ignore[return-value]

    def points(values: list[tuple[float, float]]) -> list[tuple[int, int]]:
        return [(n(x), n(y)) for x, y in values]

    def line_draw(values: tuple[float, float, float, float], fill: str, width_value: float, joint: str | None = None) -> None:
        kwargs = {"fill": fill, "width": n(width_value)}
        if joint:
            kwargs["joint"] = joint
        draw.line(box(values), **kwargs)

    def zone_labels() -> None:
        draw.text((n(326), n(78)), "INTERIOR", fill=text, font=small_font)
        draw.text((n(322), n(335)), "EXTERIOR", fill=text, font=small_font)

    def wall_segment(x1: float, y1: float, x2: float, y2: float) -> None:
        line_draw((x1, y1, x2, y2), wall, 8)

    def pivot_dot(x: float, y: float) -> None:
        draw.ellipse(box((x - 6, y - 6, x + 6, y + 6)), fill=wall)

    def draw_arrow(start: tuple[float, float], end: tuple[float, float]) -> None:
        line_draw((start[0], start[1], end[0], end[1]), blue, 3)
        sx, sy = start
        ex, ey = end
        arrow_points = [(ex, ey), (ex - 14 if ex > sx else ex + 14, ey - 8), (ex - 14 if ex > sx else ex + 14, ey + 8)]
        draw.polygon(points(arrow_points), fill=blue)

    def folding_stack(stack_side: str) -> None:
        zone_labels()
        y = 218
        wall_segment(95, y, 220, y)
        wall_segment(540, y, 665, y)
        draw.text((n(332), n(270)), "bifold door", fill=text, font=tiny_font)
        if stack_side == "left":
            hinge_points = [220, 270, 320, 370, 420]
            stack_text_x = 215
        else:
            hinge_points = [540, 490, 440, 390, 340]
            stack_text_x = 505
        for index in range(len(hinge_points) - 1):
            x1 = hinge_points[index]
            x2 = hinge_points[index + 1]
            peak_y = 165 if index % 2 == 0 else 218
            end_y = 218 if index % 2 == 0 else 165
            line_draw((x1, y, x2, peak_y), symbol, 3)
            if index == len(hinge_points) - 2:
                line_draw((x2, peak_y, x2 + (40 if stack_side == "left" else -40), end_y), symbol, 3)
        draw.text((n(stack_text_x), n(145)), "stack", fill=blue, font=tiny_font)
        if stack_side == "left":
            draw_arrow((510, 245), (250, 245))
        else:
            draw_arrow((250, 245), (510, 245))

    def folding_split() -> None:
        zone_labels()
        y = 218
        wall_segment(95, y, 230, y)
        wall_segment(530, y, 665, y)
        draw.text((n(332), n(270)), "bifold door", fill=text, font=tiny_font)
        for polyline in (
            [(230, y), (282, 166), (334, y)],
            [(530, y), (478, 166), (426, y)],
        ):
            draw.line(points(polyline), fill=symbol, width=n(3), joint="curve")
        draw_arrow((368, 245), (250, 245))
        draw_arrow((392, 245), (510, 245))

    def hinge_plan(side: str, swing: str) -> None:
        zone_labels()
        y = 218
        hinge_x = 245 if side == "left" else 515
        latch_x = 515 if side == "left" else 245
        if side == "left":
            wall_segment(95, y, hinge_x - 18, y)
            wall_segment(latch_x + 18, y, 665, y)
        else:
            wall_segment(95, y, latch_x - 18, y)
            wall_segment(hinge_x + 18, y, 665, y)
        line_draw((hinge_x, y, latch_x, y), light_symbol, 3)
        open_y = 130 if swing == "in" else 306
        open_x = hinge_x + (latch_x - hinge_x) * 0.62
        line_draw((hinge_x, y, open_x, open_y), symbol, 4)
        pivot_dot(hinge_x, y)
        arc_box = (
            min(hinge_x, latch_x, open_x) - 3,
            min(open_y, y) - 3,
            max(hinge_x, latch_x, open_x) + 3,
            max(open_y, y) + 3,
        )
        if side == "left" and swing == "in":
            start, end = 270, 330
        elif side == "left":
            start, end = 30, 90
        elif swing == "in":
            start, end = 210, 270
        else:
            start, end = 90, 150
        draw.arc(box(arc_box), start, end, fill=light_symbol, width=n(3))
        label = "door swing" if swing == "in" else "out swing"
        draw.text((n(333), n(270)), label, fill=text, font=tiny_font)

    if icon_id == "bifold-stack-left":
        folding_stack("left")
    elif icon_id == "bifold-stack-right":
        folding_stack("right")
    elif icon_id == "bifold-split-stack":
        folding_split()
    elif icon_id == "hinge-left-inswing":
        hinge_plan("left", "in")
    elif icon_id == "hinge-right-inswing":
        hinge_plan("right", "in")
    elif icon_id == "hinge-left-outswing":
        hinge_plan("left", "out")
    elif icon_id == "hinge-right-outswing":
        hinge_plan("right", "out")
    else:
        return

    image = image.resize((base_width, base_height), Image.Resampling.LANCZOS)
    image.save(path)


def ensure_opening_style_assets() -> None:
    for styles in OPENING_STYLES.values():
        for style in styles:
            make_opening_style_icon(style["icon"])


def ensure_opening_direction_assets() -> None:
    for icon_id in (
        "bifold-stack-left",
        "bifold-stack-right",
        "bifold-split-stack",
        "hinge-left-inswing",
        "hinge-right-inswing",
        "hinge-left-outswing",
        "hinge-right-outswing",
    ):
        make_opening_direction_icon(icon_id)


def ensure_assets() -> None:
    ensure_opening_style_assets()
    ensure_opening_direction_assets()


def split_options(value: str) -> tuple[str, ...]:
    return tuple(option.strip() for option in re.split(r"[,，\n]", value) if option.strip())


def safe_product_id(value: str) -> str:
    return re.sub(r"[^A-Z0-9-]", "", value.upper().replace(" ", "-"))[:30]


def save_uploaded_image(uploaded_file: Any, product_id: str, label: str) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ORIGINAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    original_bytes = uploaded_file.getvalue()
    original_suffix = Path(getattr(uploaded_file, "name", "")).suffix.lower()
    if original_suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        original_suffix = ".img"
    original_name = f"{product_id.lower()}-{label}-{stamp}{original_suffix}"
    (ORIGINAL_UPLOAD_DIR / original_name).write_bytes(original_bytes)
    image = Image.open(io.BytesIO(original_bytes))
    image = ImageOps.exif_transpose(image).convert("RGB")
    image = ImageOps.fit(
        image,
        PRODUCT_IMAGE_SIZE,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    filename = f"uploads/{product_id.lower()}-{label}-{stamp}.webp"
    image.save(ASSET_DIR / filename, "WEBP", quality=86, method=6)
    return filename


def normalize_existing_catalog_images() -> None:
    if IMAGE_MIGRATION_MARKER.exists():
        return
    ORIGINAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    changed_products: list[Product] = []
    for product in PRODUCTS:
        updated_files: dict[str, str] = {}
        source_names = [product.hero_image, *product.detail_images]
        for index, source_name in enumerate(source_names):
            source = ASSET_DIR / source_name
            if not source.exists():
                continue
            with Image.open(source) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
                if image.size == PRODUCT_IMAGE_SIZE:
                    updated_files[source_name] = source_name
                    continue
                backup = ORIGINAL_UPLOAD_DIR / f"pre-ratio-{product.id.lower()}-{index}{source.suffix.lower()}"
                if not backup.exists():
                    backup.write_bytes(source.read_bytes())
                normalized_name = f"uploads/{product.id.lower()}-normalized-{index}.webp"
                normalized = ImageOps.fit(
                    image,
                    PRODUCT_IMAGE_SIZE,
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5),
                )
                normalized.save(ASSET_DIR / normalized_name, "WEBP", quality=86, method=6)
                updated_files[source_name] = normalized_name
        changed_products.append(
            Product(
                **{
                    **asdict(product),
                    "hero_image": updated_files.get(product.hero_image, product.hero_image),
                    "detail_images": tuple(updated_files.get(name, name) for name in product.detail_images),
                }
            )
        )
    save_products(changed_products)
    reload_products()
    IMAGE_MIGRATION_MARKER.write_text("All catalog images normalized to 1500x1000 (3:2).\n", encoding="utf-8")


def admin_password() -> str:
    try:
        return str(st.secrets["ADMIN_PASSWORD"])
    except Exception:
        return os.getenv("ADMIN_PASSWORD", "frameflow-admin")


def employee_credentials() -> dict[str, str]:
    credentials: dict[str, str] = {}
    try:
        users = st.secrets["EMPLOYEE_USERS"]
        for username in users:
            credentials[str(username)] = str(users[username])
    except Exception:
        pass
    try:
        shared_password = str(st.secrets["EMPLOYEE_PASSWORD"])
    except Exception:
        shared_password = os.getenv("EMPLOYEE_PASSWORD", "")
    if shared_password:
        credentials.setdefault("team", shared_password)
    default_sales_accounts = {
        "Mia": "frameflow-mia",
        "Ethan": "frameflow-ethan",
        "Zane": "frameflow-zane",
        "Tony": "frameflow-tony",
        "Liyao": "frameflow-liyao",
        "Kevin": "frameflow-kevin",
    }
    if not credentials:
        credentials.update(default_sales_accounts)
    return credentials


def using_default_employee_login() -> bool:
    return employee_credentials() == {
        "Mia": "frameflow-mia",
        "Ethan": "frameflow-ethan",
        "Zane": "frameflow-zane",
        "Tony": "frameflow-tony",
        "Liyao": "frameflow-liyao",
        "Kevin": "frameflow-kevin",
    }


SALES_ACCOUNTS = ("Mia", "Ethan", "Zane", "Tony", "Liyao")


def manager_accounts() -> set[str]:
    try:
        configured = st.secrets["MANAGER_USERS"]
        if isinstance(configured, str):
            return {configured}
        return {str(username) for username in configured}
    except Exception:
        raw = os.getenv("MANAGER_USERS", "")
    if raw:
        return {username.strip() for username in re.split(r"[,;\n]", raw) if username.strip()}
    return {"Kevin"} if using_default_employee_login() else set()


def canonical_employee_name(username: str) -> str:
    lowered = username.strip().lower()
    for stored_username in employee_credentials():
        if stored_username.lower() == lowered:
            return stored_username
    return username.strip()


def current_employee_name() -> str:
    return canonical_employee_name(str(st.session_state.get("employee_name", "") or ""))


def is_manager_user(username: str | None = None) -> bool:
    name = canonical_employee_name(username or current_employee_name())
    return name in manager_accounts()


def customer_owner_filter() -> str:
    return "" if is_manager_user() else current_employee_name()


def customer_owner_options(current: str | None = "") -> tuple[str, ...]:
    current_value = (current or "").strip()
    options = list(SALES_ACCOUNTS)
    for manager_name in sorted(manager_accounts()):
        if manager_name and manager_name not in options:
            options.append(manager_name)
    if current_value and current_value not in options:
        options.append(current_value)
    return tuple(options)


def default_customer_owner() -> str:
    employee = current_employee_name()
    if employee:
        return employee
    return SALES_ACCOUNTS[-1] if SALES_ACCOUNTS else ""


def valid_employee_login(username: str, password: str) -> bool:
    credentials = employee_credentials()
    username = username.strip()
    if username in credentials:
        return secrets.compare_digest(password, credentials[username])
    lowered = username.lower()
    for stored_username, stored_password in credentials.items():
        if stored_username.lower() == lowered:
            return secrets.compare_digest(password, stored_password)
    return False


def employee_login_page() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="eyebrow">Employee access</div>
          <h1>Employee Login</h1>
          <p>Sign in to view customer records, quotes, inventory, and service records.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if using_default_employee_login():
        st.warning("Default sales accounts are active. Set EMPLOYEE_PASSWORD or [EMPLOYEE_USERS] in Secrets before publishing this website.")
    left, middle, right = st.columns([1, 1.15, 1])
    with middle:
        with st.form("employee-login"):
            username = st.text_input("Username", value="Liyao" if using_default_employee_login() else "")
            password = st.text_input("Password", type="password")
            login = st.form_submit_button("Sign in", type="primary", width="stretch")
            if login:
                if valid_employee_login(username, password):
                    st.session_state.employee_authenticated = True
                    st.session_state.employee_name = canonical_employee_name(username)
                    st.session_state.active_customer_id = None
                    st.session_state.cart = []
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")


def most_recent_product() -> Product | None:
    dated = [product for product in PRODUCTS if product.updated_at]
    if dated:
        return max(dated, key=lambda product: product.updated_at)
    candidates = []
    for product in PRODUCTS:
        path = image_path(product, "hero")
        if path.exists() and "uploads/" in product.hero_image:
            candidates.append((path.stat().st_mtime, product))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def money(value: float) -> str:
    return f"${value:,.2f}"


def phone_digits(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def format_us_phone(value: Any) -> str:
    raw = str(value or "").strip()
    digits = phone_digits(raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return raw


def is_valid_us_phone(value: Any) -> bool:
    digits = phone_digits(value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return len(digits) == 10


def phone_input_mask() -> None:
    components.html(
        """
        <script>
        (() => {
          const formatPhone = (raw) => {
            let digits = (raw || '').replace(/\\D/g, '');
            if (digits.length === 11 && digits.startsWith('1')) digits = digits.slice(1);
            digits = digits.slice(0, 10);
            if (digits.length <= 3) return digits ? `(${digits}` : '';
            if (digits.length <= 6) return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
            return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
          };

          const markPhoneInputs = () => {
            const doc = window.parent?.document || document;
            const labels = Array.from(doc.querySelectorAll('label'));
            labels.forEach((label) => {
              const text = (label.innerText || '').trim().toLowerCase();
              if (!text.startsWith('phone')) return;
              const wrapper = label.closest('[data-testid="stWidgetLabel"]')?.parentElement || label.parentElement;
              const input = wrapper?.querySelector('input');
              if (!input || input.dataset.phoneMaskAttached === '1') return;
              input.dataset.phoneMaskAttached = '1';
              input.placeholder = '(123) 456-7890';
              input.inputMode = 'numeric';
              input.addEventListener('input', () => {
                const formatted = formatPhone(input.value);
                if (input.value !== formatted) {
                  const cursorAtEnd = input.selectionStart === input.value.length;
                  input.value = formatted;
                  if (cursorAtEnd) {
                    input.setSelectionRange(input.value.length, input.value.length);
                  }
                }
              });
              input.addEventListener('blur', () => {
                const formatted = formatPhone(input.value);
                if (input.value !== formatted) input.value = formatted;
                input.dispatchEvent(new Event('change', { bubbles: true }));
              });
              if (input.value) {
                const formatted = formatPhone(input.value);
                if (formatted && input.value !== formatted) input.value = formatted;
              }
            });
          };

          markPhoneInputs();
          const doc = window.parent?.document || document;
          const observer = new MutationObserver(markPhoneInputs);
          observer.observe(doc.body, { childList: true, subtree: true });
          setInterval(markPhoneInputs, 1000);
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def product_price_label(product: Product) -> str:
    if product.base_rate <= 0 and product.minimum_price <= 0:
        return "Price TBD"
    if product.minimum_price <= 0:
        return f"{money(product.base_rate)}/sq ft"
    return f"From {money(product.minimum_price)} · {money(product.base_rate)}/sq ft"


STATUS_LABELS = {
    "Following": "Following",
    "Ordered": "Ordered",
    "Lost": "Lost",
}

CLIENT_TYPES = (
    "Contractor",
    "Homeowner",
    "Reseller",
    "Developer",
)

PROJECT_TYPES = (
    "New Build",
    "Remodel",
    "Replacement",
)

CUSTOMER_SOURCES = (
    "Facebook",
    "Instagram",
    "Website",
)

USE_CASES = (
    "Indoor-outdoor patio or backyard",
    "Standard window",
    "Front entry door",
    "Side or back door",
    "Other",
)

SHOWROOM_STATUSES = (
    "Invited",
    "Confirmed",
    "Visited",
    "Not needed",
)

ANSWER_STATUSES = (
    "Picked up and available",
    "Picked up, busy, callback scheduled",
    "No answer, voicemail left",
    "No answer, SMS sent",
    "First contact by SMS",
)

PRIORITY_LABELS = {
    "High": "High",
    "Medium": "Medium",
    "Low": "Low",
}

FOLLOWUP_STAGES = (
    "New lead",
    "Quoted",
    "Measuring",
    "Negotiating",
    "Waiting for customer reply",
    "On hold",
)

INSTALL_STATUSES = (
    "Not scheduled",
    "Measurement needed",
    "Production",
    "Ready to install",
    "Installed",
    "After-sales follow-up",
)

LOST_REASONS = (
    "Price",
    "Timeline",
    "Competitor",
    "No response",
    "Project cancelled",
    "Product mismatch",
    "Other",
)

INVENTORY_STATUSES = (
    "Available",
    "Reserved",
    "Sold",
    "Damaged",
)

SERVICE_STATUSES = (
    "New service request",
    "Reviewing",
    "Appointment scheduled",
    "Repairing",
    "Waiting for parts",
    "Repair completed",
    "Closed",
)

SERVICE_PRIORITIES = (
    "Urgent",
    "High",
    "Normal",
    "Low",
)

DAMAGED_PARTS = (
    "Glass",
    "Frame",
    "Hardware",
    "Track or roller",
    "Lock",
    "Screen",
    "Seal",
    "Paint or finish",
    "Other",
)

DAMAGE_REASONS = (
    "Installation issue",
    "Product defect",
    "Shipping damage",
    "Customer damage",
    "Weather or water",
    "Normal wear",
    "Unknown cause",
    "Other",
)


def today_iso() -> str:
    return date.today().isoformat()


def date_from_iso(value: str | None, fallback: date | None = None) -> date:
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return fallback or date.today()


def display_date(value: str | None) -> str:
    if not value:
        return "Not set"
    try:
        return date.fromisoformat(value).strftime("%b %d, %Y")
    except ValueError:
        return value


def row_value(row: sqlite3.Row | dict[str, Any] | None, key: str, default: Any = "") -> Any:
    if row is None:
        return default
    keys = row.keys() if hasattr(row, "keys") else []
    if key not in keys:
        return default
    value = row[key]
    return default if value is None else value


CUSTOMER_DEFAULTS: dict[str, Any] = {
    "id": None,
    "created_at": "",
    "updated_at": "",
    "status": "Following",
    "name": "",
    "company": "",
    "email": "",
    "phone": "",
    "address": "",
    "city": "",
    "zip_code": "",
    "products_interest": "",
    "client_type": "",
    "client_type_note": "",
    "project_type": "",
    "project_type_note": "",
    "use_case": "",
    "use_case_note": "",
    "area_zip": "",
    "area_zip_note": "",
    "showroom_status": "",
    "showroom_note": "",
    "answer_status": "",
    "answer_status_note": "",
    "source": "",
    "initial_contact_date": "",
    "priority": "Medium",
    "budget": 0.0,
    "assigned_to": "",
    "notes": "",
    "first_followup_date": "",
    "next_followup_date": "",
    "followup_stage": "New lead",
    "on_hold": 0,
    "order_date": "",
    "first_payment_date": "",
    "first_payment_amount": 0.0,
    "first_payment_paid": 0,
    "second_payment_enabled": 1,
    "second_payment_date": "",
    "second_payment_amount": 0.0,
    "second_payment_paid": 0,
    "install_followup_date": "",
    "install_status": "",
    "lost_date": "",
    "lost_reason": "",
    "lost_notes": "",
    "wishlist": "[]",
}

# Customer columns supported by the Supabase customers table.
# Keep this aligned with the ALTER TABLE SQL used in Supabase.
SUPABASE_CUSTOMER_COLUMNS = {
    "id",
    "created_at",
    "updated_at",
    "status",
    "name",
    "company",
    "email",
    "phone",
    "address",
    "city",
    "zip_code",
    "products_interest",
    "client_type",
    "client_type_note",
    "project_type",
    "project_type_note",
    "use_case",
    "use_case_note",
    "area_zip",
    "area_zip_note",
    "showroom_status",
    "showroom_note",
    "answer_status",
    "answer_status_note",
    "source",
    "initial_contact_date",
    "priority",
    "budget",
    "assigned_to",
    "notes",
    "first_followup_date",
    "next_followup_date",
    "followup_stage",
    "on_hold",
    "order_date",
    "first_payment_date",
    "first_payment_amount",
    "first_payment_paid",
    "second_payment_enabled",
    "second_payment_date",
    "second_payment_amount",
    "second_payment_paid",
    "install_followup_date",
    "install_status",
    "lost_date",
    "lost_reason",
    "lost_notes",
    "wishlist",
}
SUPABASE_DATE_COLUMNS = {
    "initial_contact_date",
    "first_followup_date",
    "next_followup_date",
    "order_date",
    "first_payment_date",
    "second_payment_date",
    "install_followup_date",
    "lost_date",
}


def secret_or_env(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.environ.get(name, default) or "").strip()


def supabase_customers_enabled() -> bool:
    return bool(secret_or_env("SUPABASE_URL") and (secret_or_env("SUPABASE_SERVICE_KEY") or secret_or_env("SUPABASE_KEY")))


def supabase_api_key() -> str:
    return secret_or_env("SUPABASE_SERVICE_KEY") or secret_or_env("SUPABASE_KEY")


def supabase_base_url() -> str:
    raw_url = secret_or_env("SUPABASE_URL").strip().rstrip("/")
    if raw_url.endswith("/rest/v1"):
        raw_url = raw_url[: -len("/rest/v1")]
    parsed = parse.urlsplit(raw_url)
    if parsed.scheme and parsed.netloc and parsed.netloc.endswith(".supabase.co"):
        return f"{parsed.scheme}://{parsed.netloc}"
    return raw_url


def supabase_request(method: str, table: str, query: str = "", payload: Any | None = None, prefer: str = "return=representation") -> Any:
    base_url = supabase_base_url()
    api_key = supabase_api_key()
    if not base_url or not api_key:
        raise RuntimeError("Supabase is not configured.")
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
        with url_request.urlopen(req, timeout=15) as response:
            body = response.read().decode("utf-8")
    except url_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase request failed: {exc.code} {detail}") from exc
    except url_error.URLError as exc:
        raise RuntimeError(
            "Supabase connection failed. Please check SUPABASE_URL in Streamlit Secrets. "
            "It should look like https://your-project-ref.supabase.co"
        ) from exc
    if not body:
        return []
    return json.loads(body)


def warn_supabase_fallback(message: str) -> None:
    if st.session_state.get("supabase_customer_warning_shown"):
        return
    st.session_state.supabase_customer_warning_shown = True
    st.warning(message)


def normalize_customer_row(data: dict[str, Any]) -> dict[str, Any]:
    row = dict(CUSTOMER_DEFAULTS)
    row.update(data or {})
    if row.get("zip_code") and not row.get("area_zip"):
        row["area_zip"] = row["zip_code"]
    if row.get("wishlist") is None:
        row["wishlist"] = "[]"
    elif isinstance(row.get("wishlist"), (list, dict)):
        row["wishlist"] = json.dumps(row["wishlist"], ensure_ascii=False)
    for key in ("budget", "first_payment_amount", "second_payment_amount"):
        try:
            row[key] = float(row.get(key) or 0.0)
        except (TypeError, ValueError):
            row[key] = 0.0
    for key in ("on_hold", "first_payment_paid", "second_payment_enabled", "second_payment_paid"):
        row[key] = int(bool(row.get(key))) if isinstance(row.get(key), bool) else int(row.get(key) or 0)
    if not row.get("updated_at"):
        row["updated_at"] = row.get("created_at") or ""
    return row


SQLITE_CUSTOMER_COLUMNS = (
    "id",
    "created_at",
    "updated_at",
    "status",
    "name",
    "company",
    "email",
    "phone",
    "address",
    "products_interest",
    "client_type",
    "client_type_note",
    "project_type",
    "project_type_note",
    "use_case",
    "use_case_note",
    "area_zip",
    "area_zip_note",
    "showroom_status",
    "showroom_note",
    "answer_status",
    "answer_status_note",
    "source",
    "initial_contact_date",
    "priority",
    "budget",
    "assigned_to",
    "notes",
    "first_followup_date",
    "next_followup_date",
    "followup_stage",
    "on_hold",
    "order_date",
    "first_payment_date",
    "first_payment_amount",
    "first_payment_paid",
    "second_payment_enabled",
    "second_payment_date",
    "second_payment_amount",
    "second_payment_paid",
    "install_followup_date",
    "install_status",
    "lost_date",
    "lost_reason",
    "lost_notes",
    "wishlist",
)


def mirror_customer_to_sqlite(customer_id: int | None, data: dict[str, Any] | None = None) -> None:
    if not customer_id:
        return
    row = normalize_customer_row({**(data or {}), "id": int(customer_id)})
    now = datetime.now().isoformat(timespec="seconds")
    if not row.get("created_at"):
        row["created_at"] = now
    if not row.get("updated_at"):
        row["updated_at"] = now
    if not row.get("name"):
        row["name"] = "Supabase Customer"
    values = [row_value(row, column, CUSTOMER_DEFAULTS.get(column, "")) for column in SQLITE_CUSTOMER_COLUMNS]
    columns = ", ".join(SQLITE_CUSTOMER_COLUMNS)
    placeholders = ", ".join("?" for _ in SQLITE_CUSTOMER_COLUMNS)
    updates = ", ".join(f"{column} = excluded.{column}" for column in SQLITE_CUSTOMER_COLUMNS if column != "id")
    with db_connect() as conn:
        conn.execute(
            f"INSERT INTO customers ({columns}) VALUES ({placeholders}) ON CONFLICT(id) DO UPDATE SET {updates}",
            values,
        )


def supabase_customer_rows_all() -> list[dict[str, Any]]:
    query = parse.urlencode({"select": "*", "order": "updated_at.desc"})
    rows = supabase_request("GET", "customers", query=query, prefer="")
    normalized_rows = [normalize_customer_row(row) for row in rows]
    for row in normalized_rows:
        mirror_customer_to_sqlite(int(row["id"]), row)
    return normalized_rows


def filtered_supabase_customer_rows(status: str | None = None, search: str = "", *, company_order: bool = False) -> list[dict[str, Any]]:
    rows = supabase_customer_rows_all()
    owner = customer_owner_filter()
    if owner:
        rows = [row for row in rows if str(row_value(row, "assigned_to", "")).lower() == owner.lower()]
    if status:
        rows = [row for row in rows if row_value(row, "status") == status]
    if search:
        query = search.strip().lower()
        rows = [row for row in rows if query in customer_search_blob(row)]
    if company_order:
        rows.sort(key=lambda row: (row_value(row, "order_date") or row_value(row, "updated_at") or "", row_value(row, "name")), reverse=True)
    else:
        priority_rank = {"High": 0, "Medium": 1, "Low": 2}
        rows.sort(
            key=lambda row: (
                priority_rank.get(row_value(row, "priority", "Medium"), 3),
                row_value(row, "next_followup_date") or row_value(row, "install_followup_date") or row_value(row, "order_date") or row_value(row, "updated_at") or "",
            )
        )
    return rows


def supabase_customer_payload(data: dict[str, Any], *, include_created_at: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in data.items():
        target_key = "zip_code" if key == "area_zip" else key
        if target_key not in SUPABASE_CUSTOMER_COLUMNS or target_key == "id":
            continue
        if target_key == "created_at" and not include_created_at:
            continue
        if target_key == "wishlist":
            if isinstance(value, str):
                try:
                    value = json.loads(value or "[]")
                except json.JSONDecodeError:
                    value = []
            elif value is None:
                value = []
        if target_key in SUPABASE_DATE_COLUMNS and not value:
            value = None
        payload[target_key] = value
    if "city" not in payload:
        city = city_from_address(str(data.get("address") or "")) or city_from_zip(str(data.get("zip_code") or data.get("area_zip") or data.get("address") or ""))
        if city:
            payload["city"] = city
    return payload


def supabase_save_customer(customer_id: int | None, data: dict[str, Any]) -> int:
    payload = supabase_customer_payload(data, include_created_at=not bool(customer_id))
    if customer_id:
        query = f"id=eq.{int(customer_id)}"
        rows = supabase_request("PATCH", "customers", query=query, payload=payload)
        return int(rows[0]["id"] if rows else customer_id)
    rows = supabase_request("POST", "customers", payload=payload)
    if not rows:
        raise RuntimeError("Supabase did not return the new customer id.")
    return int(rows[0]["id"])


def supabase_update_customer(customer_id: int, updates: dict[str, Any]) -> None:
    payload = supabase_customer_payload(updates)
    if not payload:
        return
    supabase_request("PATCH", "customers", query=f"id=eq.{int(customer_id)}", payload=payload, prefer="return=minimal")


def supabase_delete_customer(customer_id: int) -> None:
    supabase_request("DELETE", "customers", query=f"id=eq.{int(customer_id)}", payload=None, prefer="return=minimal")


def option_index(options: Sequence[str], value: str | None) -> int:
    return options.index(value) if value in options else 0


def customer_source_options(current: str | None = "") -> tuple[str, ...]:
    current_value = (current or "").strip()
    options = ["", *CUSTOMER_SOURCES]
    if current_value and current_value not in options:
        options.append(current_value)
    return tuple(options)


def due_label(value: str | None) -> tuple[str, str]:
    if not value:
        return "No reminder", "#68736d"
    target = date_from_iso(value)
    days = (target - date.today()).days
    if days < 0:
        return f"Overdue {abs(days)} day(s)", "#b42318"
    if days == 0:
        return "Due today", "#9a6700"
    if days <= 3:
        return f"Due in {days} day(s)", "#9a6700"
    return f"Due in {days} day(s)", "#2e6b45"


def inventory_rows(search: str = "", product_id: str = "") -> list[sqlite3.Row]:
    query = "SELECT * FROM inventory_items"
    clauses: list[str] = []
    params: list[Any] = []
    if product_id:
        clauses.append("product_id = ?")
        params.append(product_id)
    if search:
        like = f"%{search.lower()}%"
        clauses.append(
            "(lower(product_id) LIKE ? OR lower(sku) LIKE ? OR lower(warehouse) LIKE ? OR "
            "lower(location) LIKE ? OR lower(color) LIKE ? OR lower(glass) LIKE ? OR "
            "lower(frame) LIKE ? OR lower(direction) LIKE ? OR lower(notes) LIKE ?)"
        )
        params.extend([like] * 9)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY received_date DESC, updated_at DESC, id DESC"
    with db_connect() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(query, params).fetchall()


def inventory_item_by_id(item_id: int | None) -> sqlite3.Row | None:
    if not item_id:
        return None
    with db_connect() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM inventory_items WHERE id = ?", (item_id,)).fetchone()


def inventory_summary(product_id: str, color: str = "") -> dict[str, int]:
    query = """
        SELECT
            COALESCE(SUM(quantity), 0) AS total,
            COALESCE(SUM(reserved_quantity), 0) AS reserved
        FROM inventory_items
        WHERE product_id = ? AND status IN ('Available', 'Reserved')
    """
    params: list[Any] = [product_id]
    if color:
        query += " AND (color = ? OR color IS NULL OR color = '')"
        params.append(color)
    with db_connect() as conn:
        row = conn.execute(query, params).fetchone()
    total = int(row[0] or 0)
    reserved = int(row[1] or 0)
    return {"total": total, "reserved": reserved, "available": max(total - reserved, 0)}


def inventory_available_quantity(row: sqlite3.Row) -> int:
    return max(int(row["quantity"] or 0) - int(row["reserved_quantity"] or 0), 0)


def normalized_inventory_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def inventory_text_matches(stored: Any, selected: str) -> bool:
    stored_text = normalized_inventory_text(stored)
    selected_text = normalized_inventory_text(selected)
    if not stored_text:
        return True
    return stored_text == selected_text


def inventory_direction_code(value: Any) -> str:
    normalized = normalized_inventory_text(value)
    if not normalized:
        return ""
    swing = ""
    if "inswing" in normalized:
        swing = "IN"
    elif "outswing" in normalized:
        swing = "OUT"
    if "righttoleft" in normalized or normalized.endswith("r"):
        side = "R"
    elif "lefttoright" in normalized or normalized.endswith("l"):
        side = "L"
    elif "center" in normalized or normalized.startswith("c"):
        side = "C"
    elif "right" in normalized:
        side = "R"
    elif "left" in normalized:
        side = "L"
    else:
        return normalized
    return f"{side}-{swing}" if swing else side


def inventory_direction_matches(stored: Any, selected: str) -> bool:
    stored_code = inventory_direction_code(stored)
    if not stored_code:
        return True
    selected_code = inventory_direction_code(selected)
    if "-" in stored_code or "-" in selected_code:
        return stored_code == selected_code
    return stored_code == selected_code


def inventory_dimension_matches(stored: Any, selected: float) -> bool:
    try:
        stored_value = float(stored or 0)
    except (TypeError, ValueError):
        return True
    if stored_value <= 0:
        return True
    return abs(stored_value - float(selected)) <= 0.25


def inventory_match_score(row: sqlite3.Row, width: float, height: float, color: str, glass: str, frame: str, direction: str) -> int:
    score = 0
    for field, selected in (
        ("color", color),
        ("glass", glass),
        ("frame", frame),
        ("direction", direction),
    ):
        if field == "direction":
            matched = inventory_direction_matches(row[field], selected)
        else:
            matched = inventory_text_matches(row[field], selected)
        if normalized_inventory_text(row[field]) and matched:
            score += 1
    for field, selected in (("width", width), ("height", height)):
        try:
            stored_value = float(row[field] or 0)
        except (TypeError, ValueError):
            stored_value = 0
        if stored_value > 0 and inventory_dimension_matches(stored_value, selected):
            score += 1
    return score


def matching_inventory_rows(
    product_id: str,
    width: float,
    height: float,
    color: str,
    glass: str,
    frame: str,
    direction: str,
) -> list[sqlite3.Row]:
    with db_connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM inventory_items
            WHERE product_id = ?
              AND status IN ('Available', 'Reserved')
            ORDER BY received_date DESC, updated_at DESC, id DESC
            """,
            (product_id,),
        ).fetchall()
    matches = [
        row for row in rows
        if inventory_available_quantity(row) > 0
        and inventory_dimension_matches(row["width"], width)
        and inventory_dimension_matches(row["height"], height)
        and inventory_text_matches(row["color"], color)
        and inventory_text_matches(row["glass"], glass)
        and inventory_text_matches(row["frame"], frame)
        and inventory_direction_matches(row["direction"], direction)
    ]
    matches.sort(
        key=lambda row: (
            inventory_match_score(row, width, height, color, glass, frame, direction),
            inventory_available_quantity(row),
            row["received_date"] or "",
        ),
        reverse=True,
    )
    return matches


def matching_inventory_rows_from_conn(
    conn: sqlite3.Connection,
    product_id: str,
    width: float,
    height: float,
    color: str,
    glass: str,
    frame: str,
    direction: str,
) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT * FROM inventory_items
        WHERE product_id = ?
          AND status IN ('Available', 'Reserved')
        ORDER BY received_date DESC, updated_at DESC, id DESC
        """,
        (product_id,),
    ).fetchall()
    matches = [
        row for row in rows
        if inventory_available_quantity(row) > 0
        and inventory_dimension_matches(row["width"], width)
        and inventory_dimension_matches(row["height"], height)
        and inventory_text_matches(row["color"], color)
        and inventory_text_matches(row["glass"], glass)
        and inventory_text_matches(row["frame"], frame)
        and inventory_direction_matches(row["direction"], direction)
    ]
    matches.sort(
        key=lambda row: (
            inventory_match_score(row, width, height, color, glass, frame, direction),
            inventory_available_quantity(row),
            row["received_date"] or "",
        ),
        reverse=True,
    )
    return matches


def deduct_inventory_for_order_items(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    updated_items: list[dict[str, Any]] = []
    messages: list[str] = []
    now = datetime.now().isoformat(timespec="seconds")
    with db_connect(isolation_level=None) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN IMMEDIATE")
        for item in items:
            updated = dict(item)
            if updated.get("inventory_deducted"):
                updated_items.append(updated)
                continue
            requested = int(updated.get("quantity") or 1)
            remaining = requested
            deducted = 0
            product_id = str(updated.get("product_id") or "")
            if product_id and requested > 0:
                matches = matching_inventory_rows_from_conn(
                    conn,
                    product_id,
                    float(updated.get("width") or 0),
                    float(updated.get("height") or 0),
                    str(updated.get("color") or ""),
                    str(updated.get("glass") or ""),
                    str(updated.get("frame") or ""),
                    str(updated.get("direction") or ""),
                )
                for row in matches:
                    if remaining <= 0:
                        break
                    available = inventory_available_quantity(row)
                    if available <= 0:
                        continue
                    take = min(remaining, available)
                    result = conn.execute(
                        """
                        UPDATE inventory_items
                        SET
                            quantity = quantity - ?,
                            reserved_quantity = MIN(reserved_quantity, quantity - ?),
                            status = CASE
                                WHEN quantity - ? <= 0 THEN 'Sold'
                                WHEN MIN(reserved_quantity, quantity - ?) > 0 THEN 'Reserved'
                                ELSE 'Available'
                            END,
                            updated_at = ?
                        WHERE id = ? AND (quantity - reserved_quantity) >= ?
                        """,
                        (take, take, take, take, now, int(row["id"]), take),
                    )
                    if result.rowcount != 1:
                        continue
                    remaining -= take
                    deducted += take
            updated["inventory_deducted"] = True
            updated["inventory_deducted_at"] = now
            updated["inventory_deducted_quantity"] = deducted
            if remaining > 0:
                updated["inventory_short_quantity"] = remaining
                updated["production_required"] = True
                messages.append(f"{updated.get('name') or product_id or 'Product'}: deducted {deducted}, short {remaining}.")
            else:
                updated["inventory_short_quantity"] = 0
                updated["production_required"] = False
                messages.append(f"{updated.get('name') or product_id or 'Product'}: deducted {deducted} from inventory.")
            updated_items.append(updated)
        conn.commit()
    return updated_items, messages


def production_required_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in items if item.get("production_required") or int(item.get("inventory_short_quantity") or 0) > 0]


def inventory_status_text(product_id: str, requested: int = 1, color: str = "") -> tuple[str, str]:
    summary = inventory_summary(product_id, color)
    available = summary["available"]
    if available >= requested:
        return f"In stock: {available} available", "#2e6b45"
    if available > 0:
        return f"Low stock: {available} available, {requested} requested", "#9a6700"
    return "No available stock", "#b42318"


def save_inventory_item(item_id: int | None, data: dict[str, Any]) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    payload = {**data, "updated_at": now}
    with db_connect() as conn:
        if item_id:
            assignments = ", ".join(f"{key} = ?" for key in payload)
            conn.execute(
                f"UPDATE inventory_items SET {assignments} WHERE id = ?",
                [*payload.values(), item_id],
            )
            return item_id
        payload = {**payload, "created_at": now}
        columns = ", ".join(payload)
        placeholders = ", ".join("?" for _ in payload)
        cursor = conn.execute(
            f"INSERT INTO inventory_items ({columns}) VALUES ({placeholders})",
            list(payload.values()),
        )
        return int(cursor.lastrowid)


def delete_inventory_item(item_id: int) -> None:
    with db_connect() as conn:
        conn.execute("DELETE FROM inventory_items WHERE id = ?", (item_id,))


def customer_rows(status: str | None = None, search: str = "") -> list[sqlite3.Row | dict[str, Any]]:
    if supabase_customers_enabled():
        try:
            return filtered_supabase_customer_rows(status, search)
        except Exception as exc:
            warn_supabase_fallback(f"Supabase customer sync failed, showing local customers for now. {exc}")
    return sqlite_customer_rows(status, search)


def sqlite_customer_rows(status: str | None = None, search: str = "") -> list[sqlite3.Row]:
    query = "SELECT * FROM customers"
    clauses: list[str] = []
    params: list[Any] = []
    owner = customer_owner_filter()
    if owner:
        clauses.append("lower(assigned_to) = lower(?)")
        params.append(owner)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if search:
        like = f"%{search.lower()}%"
        clauses.append(
            "(lower(name) LIKE ? OR lower(company) LIKE ? OR lower(email) LIKE ? OR "
            "lower(phone) LIKE ? OR lower(address) LIKE ? OR lower(products_interest) LIKE ? OR "
            "lower(client_type) LIKE ? OR lower(project_type) LIKE ? OR lower(use_case) LIKE ? OR "
            "lower(area_zip) LIKE ? OR lower(showroom_status) LIKE ? OR lower(answer_status) LIKE ? OR "
            "lower(assigned_to) LIKE ? OR lower(wishlist) LIKE ?)"
        )
        params.extend([like] * 14)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += """
        ORDER BY
            CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END,
            COALESCE(next_followup_date, install_followup_date, order_date, lost_date, updated_at) ASC
    """
    with db_connect() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(query, params).fetchall()


def company_customer_rows(status: str | None = None, search: str = "") -> list[sqlite3.Row | dict[str, Any]]:
    if supabase_customers_enabled():
        try:
            return filtered_supabase_customer_rows(status, search, company_order=True)
        except Exception as exc:
            warn_supabase_fallback(f"Supabase customer sync failed, showing local customers for now. {exc}")
    return sqlite_company_customer_rows(status, search)


def sqlite_company_customer_rows(status: str | None = None, search: str = "") -> list[sqlite3.Row]:
    query = "SELECT * FROM customers"
    clauses: list[str] = []
    params: list[Any] = []
    owner = customer_owner_filter()
    if owner:
        clauses.append("lower(assigned_to) = lower(?)")
        params.append(owner)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if search:
        like = f"%{search.lower()}%"
        clauses.append(
            "(lower(name) LIKE ? OR lower(company) LIKE ? OR lower(email) LIKE ? OR "
            "lower(phone) LIKE ? OR lower(address) LIKE ? OR lower(products_interest) LIKE ? OR "
            "lower(assigned_to) LIKE ? OR lower(wishlist) LIKE ?)"
        )
        params.extend([like] * 8)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY COALESCE(order_date, updated_at) DESC, name ASC"
    with db_connect() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(query, params).fetchall()


def customer_by_id(customer_id: int) -> sqlite3.Row | dict[str, Any] | None:
    if supabase_customers_enabled():
        try:
            query = parse.urlencode({"select": "*", "id": f"eq.{int(customer_id)}", "limit": "1"})
            rows = supabase_request("GET", "customers", query=query, prefer="")
            if not rows:
                return None
            row = normalize_customer_row(rows[0])
            mirror_customer_to_sqlite(int(row["id"]), row)
            owner = customer_owner_filter()
            if owner and str(row_value(row, "assigned_to", "")).lower() != owner.lower():
                return None
            return row
        except Exception as exc:
            warn_supabase_fallback(f"Supabase customer sync failed, showing local customer data for now. {exc}")
    return sqlite_customer_by_id(customer_id)


def sqlite_customer_by_id(customer_id: int) -> sqlite3.Row | None:
    owner = customer_owner_filter()
    with db_connect() as conn:
        conn.row_factory = sqlite3.Row
        if owner:
            return conn.execute(
                "SELECT * FROM customers WHERE id = ? AND lower(assigned_to) = lower(?)",
                (customer_id, owner),
            ).fetchone()
        return conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()


def find_customer_by_contact(email: str, phone: str) -> sqlite3.Row | dict[str, Any] | None:
    if supabase_customers_enabled():
        try:
            rows = filtered_supabase_customer_rows()
            target_email = email.strip().lower()
            phone_values = {phone.strip(), format_us_phone(phone), re.sub(r"\D+", "", phone or "")}
            phone_values = {value for value in phone_values if value}
            if target_email:
                for row in rows:
                    if str(row_value(row, "email", "")).strip().lower() == target_email:
                        return row
            for row in rows:
                row_phone = str(row_value(row, "phone", ""))
                if row_phone in phone_values or re.sub(r"\D+", "", row_phone) in phone_values:
                    return row
            return None
        except Exception as exc:
            warn_supabase_fallback(f"Supabase customer sync failed, searching local customers for now. {exc}")
    return sqlite_find_customer_by_contact(email, phone)


def customer_matches_checkout_payload(existing: sqlite3.Row | dict[str, Any] | None, payload: dict[str, Any]) -> bool:
    if not existing:
        return False
    existing_email = str(row_value(existing, "email", "") or "").strip().lower()
    payload_email = str(payload.get("email") or "").strip().lower()
    existing_phone = re.sub(r"\D+", "", str(row_value(existing, "phone", "") or ""))
    payload_phone = re.sub(r"\D+", "", str(payload.get("phone") or ""))
    existing_name = re.sub(r"\s+", " ", str(row_value(existing, "name", "") or "").strip().lower())
    payload_name = re.sub(r"\s+", " ", str(payload.get("name") or "").strip().lower())
    if payload_email or payload_phone:
        return bool(payload_email and existing_email and payload_email == existing_email) or bool(payload_phone and existing_phone and payload_phone == existing_phone)
    return bool(payload_name and existing_name and payload_name == existing_name)


def sqlite_find_customer_by_contact(email: str, phone: str) -> sqlite3.Row | None:
    owner = customer_owner_filter()
    owner_clause = " AND lower(assigned_to) = lower(?)" if owner else ""
    with db_connect() as conn:
        conn.row_factory = sqlite3.Row
        if email.strip():
            row = conn.execute(
                f"SELECT * FROM customers WHERE lower(email) = lower(?) {owner_clause} ORDER BY updated_at DESC LIMIT 1",
                (email.strip(), owner) if owner else (email.strip(),),
            ).fetchone()
            if row:
                return row
        formatted_phone = format_us_phone(phone)
        phone_values = tuple(value for value in {phone.strip(), formatted_phone} if value)
        if phone_values:
            placeholders = ",".join("?" for _ in phone_values)
            params = (*phone_values, owner) if owner else phone_values
            return conn.execute(
                f"SELECT * FROM customers WHERE phone IN ({placeholders}) {owner_clause} ORDER BY updated_at DESC LIMIT 1",
                params,
            ).fetchone()
    return None


def add_customer_timeline_event(
    customer_id: int,
    event_date: date | str,
    title: str,
    notes: str = "",
    quote_number: str | None = None,
) -> None:
    event_value = event_date.isoformat() if isinstance(event_date, date) else event_date
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO customer_timeline
            (customer_id, event_date, title, notes, quote_number, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                customer_id,
                event_value,
                title,
                notes,
                quote_number,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def customer_timeline(customer_id: int) -> list[sqlite3.Row]:
    with db_connect() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """
            SELECT * FROM customer_timeline
            WHERE customer_id = ?
            ORDER BY event_date ASC, created_at ASC
            """,
            (customer_id,),
        ).fetchall()


def customer_display_name(customer_id: int | None) -> str:
    if not customer_id:
        return "No customer selected"
    row = customer_by_id(customer_id)
    return row["name"] if row else "Unknown customer"


def customer_search_blob(row: sqlite3.Row | dict[str, Any]) -> str:
    fields = (
        "name",
        "company",
        "email",
        "phone",
        "address",
        "city",
        "zip_code",
        "products_interest",
        "area_zip",
    )
    return " ".join(str(row_value(row, field, "")) for field in fields).lower()


def customer_match_score(row: sqlite3.Row, query: str) -> int:
    query = query.strip().lower()
    if not query:
        return 0
    name = str(row_value(row, "name", "")).lower()
    phone = str(row_value(row, "phone", "")).lower()
    email = str(row_value(row, "email", "")).lower()
    company = str(row_value(row, "company", "")).lower()
    if name == query:
        return 100
    if name.startswith(query):
        return 90
    if query in name:
        return 80
    if phone.startswith(query) or email.startswith(query):
        return 70
    if query in phone or query in email:
        return 60
    if query in company:
        return 50
    if query in customer_search_blob(row):
        return 40
    return 0


def customer_picker_label(row: sqlite3.Row, query: str = "") -> str:
    contact = row_value(row, "phone") or row_value(row, "email") or "No contact"
    company = row_value(row, "company")
    parts = [str(row_value(row, "name", "Unknown customer")), str(contact)]
    if company:
        parts.append(str(company))
    prefix = "[match] " if customer_match_score(row, query) > 0 else ""
    return prefix + " · ".join(parts)


def save_customer_cart(customer_id: int | None, cart: list[dict[str, Any]] | None = None) -> None:
    if not customer_id:
        return
    cart_payload = cart if cart is not None else st.session_state.cart
    payload = json.dumps(cart_payload, ensure_ascii=False)
    now = datetime.now().isoformat(timespec="seconds")
    with db_connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO customer_carts (customer_id, updated_at, payload)
            VALUES (?, ?, ?)
            """,
            (customer_id, now, payload),
        )
        conn.execute(
            "UPDATE customers SET wishlist = ?, updated_at = ? WHERE id = ?",
            (payload, now, int(customer_id)),
        )
    if supabase_customers_enabled():
        try:
            supabase_update_customer(int(customer_id), {"wishlist": cart_payload, "updated_at": now})
        except Exception as exc:
            warn_supabase_fallback(f"Supabase cart sync failed, saving cart locally for now. {exc}")


def save_customer_wishlist(customer_id: int | None, wishlist: list[dict[str, Any]] | None = None) -> None:
    if not customer_id:
        return
    wishlist_payload = wishlist if wishlist is not None else wishlist_from_cart()
    payload = json.dumps(wishlist_payload, ensure_ascii=False)
    now = datetime.now().isoformat(timespec="seconds")
    if supabase_customers_enabled():
        try:
            supabase_update_customer(int(customer_id), {"wishlist": wishlist_payload, "updated_at": now})
            return
        except Exception as exc:
            warn_supabase_fallback(f"Supabase wishlist sync failed, saving wishlist locally for now. {exc}")
    with db_connect() as conn:
        conn.execute(
            "UPDATE customers SET wishlist = ?, updated_at = ? WHERE id = ?",
            (payload, now, int(customer_id)),
        )


def load_customer_cart(customer_id: int | None) -> list[dict[str, Any]]:
    if not customer_id:
        return []
    with db_connect() as conn:
        row = conn.execute("SELECT payload FROM customer_carts WHERE customer_id = ?", (customer_id,)).fetchone()
    raw_payload = row[0] if row else None
    if not raw_payload:
        customer = customer_by_id(int(customer_id))
        raw_payload = row_value(customer, "wishlist") if customer else None
    try:
        data = json.loads(raw_payload) if raw_payload else []
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def reset_quote_adjustments() -> None:
    st.session_state.quote_discount_type = "No discount"
    st.session_state.quote_discount_value = 0.0
    st.session_state.quote_installation_fee = 0.0
    st.session_state.quote_shipping_fee = 0.0
    st.session_state.quote_shipping_enabled = False
    st.session_state.quote_sales_tax_enabled = False
    st.session_state.quote_discount_percent_value = 0.0
    st.session_state.quote_discount_amount_value = 0.0
    st.session_state.checkout_quote_adjustments = None


def set_active_customer(customer_id: int | None, load_cart: bool = True) -> None:
    if st.session_state.get("active_customer_id") != customer_id:
        reset_quote_adjustments()
    st.session_state.active_customer_id = customer_id
    if load_cart:
        st.session_state.cart = load_customer_cart(customer_id)


def customer_quotes(customer_id: int) -> list[sqlite3.Row]:
    with db_connect() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM quotes WHERE customer_id = ? ORDER BY created_at DESC",
            (customer_id,),
        ).fetchall()


def quote_payload(row: sqlite3.Row) -> dict[str, Any]:
    try:
        payload = json.loads(row["payload"])
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def latest_customer_quote(customer_id: int) -> sqlite3.Row | None:
    rows = customer_quotes(customer_id)
    return rows[0] if rows else None


def order_item_match_key(item: dict[str, Any]) -> tuple[Any, ...]:
    product_key = str(item.get("product_id") or item.get("name") or "").strip().lower()
    return (
        product_key,
        round(float(item.get("width") or 0), 2),
        round(float(item.get("height") or 0), 2),
        str(item.get("direction") or "").strip().lower(),
        str(item.get("glass") or "").strip().lower(),
        str(item.get("frame") or "").strip().lower(),
        str(item.get("color") or "").strip().lower(),
        int(item.get("quantity") or 1),
    )


def ordered_wishlist_items(wishlist: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = [item for item in wishlist if str(item.get("order_status") or "").lower() == "ordered"]
    return ordered or wishlist


def quote_items_match_ordered_products(payload: dict[str, Any], wishlist: list[dict[str, Any]]) -> bool:
    quote_items = payload.get("items")
    comparable_wishlist = [item for item in wishlist if bool(item.get("included_in_quote", True))]
    if not isinstance(quote_items, list) or len(quote_items) != len(comparable_wishlist):
        return False
    quote_keys = [order_item_match_key(item) for item in quote_items if isinstance(item, dict)]
    wishlist_keys = [order_item_match_key(item) for item in comparable_wishlist if isinstance(item, dict)]
    return len(quote_keys) == len(wishlist_keys) and sorted(quote_keys) == sorted(wishlist_keys)


def order_summary_from_ordered_products(wishlist: list[dict[str, Any]]) -> dict[str, float | str]:
    ordered_items = ordered_wishlist_items(wishlist)
    product_total = wishlist_total(ordered_items)
    tax = 0.0
    installation = 0.0
    shipping = 0.0
    return {
        "quote_number": "",
        "subtotal": product_total,
        "discount": 0.0,
        "tax": tax,
        "tax_rate": 0.0,
        "installation": installation,
        "shipping": shipping,
        "total": product_total + tax + installation + shipping,
        "product_total": product_total,
    }


def order_summary_from_quote(row: sqlite3.Row | None, wishlist: list[dict[str, Any]]) -> dict[str, float | str]:
    ordered_items = ordered_wishlist_items(wishlist)
    if row is not None:
        payload = quote_payload(row)
        if quote_items_match_ordered_products(payload, ordered_items):
            subtotal = float(payload.get("subtotal") or row["subtotal"] or 0)
            discount = float(payload.get("discount") or 0)
            tax = float(payload.get("tax") or row["tax"] or 0)
            tax_rate = float(payload.get("tax_rate") or 0)
            installation = float(payload.get("installation_fee") or 0)
            shipping = float(payload.get("shipping_fee") or 0)
            total = float(payload.get("total") or row["total"] or 0)
            product_total = max(subtotal - discount, 0)
            return {
                "quote_number": str(row["quote_number"]),
                "subtotal": subtotal,
                "discount": discount,
                "tax": tax,
                "tax_rate": tax_rate,
                "installation": installation,
                "shipping": shipping,
                "total": total,
                "product_total": product_total,
            }
    return order_summary_from_ordered_products(ordered_items)


def render_order_summary(summary: dict[str, float | str]) -> None:
    subtotal = float(summary["subtotal"])
    discount = float(summary["discount"])
    tax = float(summary["tax"])
    tax_rate = float(summary["tax_rate"])
    installation = float(summary["installation"])
    shipping = float(summary.get("shipping") or 0)
    total = float(summary["total"])
    st.markdown(
        f"""
        <div style="border:1px solid #dfe4e0;border-radius:8px;padding:14px 18px;background:#fbfcfa;margin:12px 0">
          <div style="font-weight:800;margin-bottom:10px">Order receipt</div>
          <div style="display:flex;justify-content:space-between;margin:5px 0"><span>Items subtotal</span><span>{money(subtotal)}</span></div>
          <div style="display:flex;justify-content:space-between;margin:5px 0"><span>Discount</span><span>{'-' + money(discount) if discount else money(0)}</span></div>
          <div style="display:flex;justify-content:space-between;margin:5px 0"><span>Sales tax ({tax_rate:.2f}%)</span><span>{money(tax)}</span></div>
          {f'<div style="display:flex;justify-content:space-between;margin:5px 0"><span>Shipping</span><span>{money(shipping)}</span></div>' if shipping else ''}
          <div style="display:flex;justify-content:space-between;margin:5px 0"><span>Installation</span><span>{money(installation)}</span></div>
          <div style="border-top:1px solid #dfe4e0;margin-top:9px;padding-top:9px;display:flex;justify-content:space-between;font-weight:800"><span>Order total</span><span>{money(total)}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def payment_schedule_values(customer: sqlite3.Row, order_total: float) -> dict[str, Any]:
    first_amount = float(customer["first_payment_amount"] or 0)
    second_enabled = bool(int(row_value(customer, "second_payment_enabled", 1) or 0))
    second_amount = float(customer["second_payment_amount"] or 0) if second_enabled else 0.0
    first_paid = bool(int(row_value(customer, "first_payment_paid", 0) or 0))
    second_paid = bool(int(row_value(customer, "second_payment_paid", 0) or 0)) if second_enabled else False
    paid_total = (first_amount if first_paid else 0.0) + (second_amount if second_paid else 0.0)
    balance = max(float(order_total) - paid_total, 0.0)
    first_date = customer["first_payment_date"] or ""
    second_date = (customer["second_payment_date"] or "") if second_enabled else ""
    next_due = ""
    if not first_paid and first_date:
        next_due = first_date
    elif second_enabled and not second_paid and second_date:
        next_due = second_date
    elif balance > 0:
        next_due = second_date or first_date
    return {
        "first_amount": first_amount,
        "second_amount": second_amount,
        "first_paid": first_paid,
        "second_enabled": second_enabled,
        "second_paid": second_paid,
        "paid_total": paid_total,
        "balance": balance,
        "first_date": first_date,
        "second_date": second_date,
        "next_due": next_due,
    }


def render_payment_receipt(customer: sqlite3.Row, order_total: float) -> dict[str, Any]:
    schedule = payment_schedule_values(customer, order_total)
    first_status = "Paid" if schedule["first_paid"] else "Unpaid"
    second_status = "Paid" if schedule["second_paid"] else "Unpaid"
    second_line = (
        f"""<div style="display:flex;justify-content:space-between;margin:5px 0"><span>Second payment · {display_date(schedule['second_date'])} · {second_status}</span><span>{money(schedule['second_amount'])}</span></div>"""
        if schedule["second_enabled"]
        else """<div style="display:flex;justify-content:space-between;margin:5px 0;color:#68736d"><span>Second payment</span><span>Not required</span></div>"""
    )
    next_due_line = (
        f"<div style='display:flex;justify-content:space-between;margin:5px 0'><span>Next payment due</span><span>{display_date(schedule['next_due'])}</span></div>"
        if schedule["balance"] > 0 and schedule["next_due"]
        else ""
    )
    st.markdown(
        f"""
        <div style="border:1px solid #dfe4e0;border-radius:8px;padding:14px 18px;background:#fff;margin:10px 0 14px">
          <div style="font-weight:800;margin-bottom:10px">Payment schedule</div>
          <div style="display:flex;justify-content:space-between;margin:5px 0"><span>First payment · {display_date(schedule['first_date'])} · {first_status}</span><span>{money(schedule['first_amount'])}</span></div>
          {second_line}
          <div style="border-top:1px solid #dfe4e0;margin-top:9px;padding-top:9px;display:flex;justify-content:space-between"><span>Paid total</span><span>{money(schedule['paid_total'])}</span></div>
          <div style="display:flex;justify-content:space-between;margin:5px 0;font-weight:800"><span>Balance due</span><span>{money(schedule['balance'])}</span></div>
          {next_due_line}
          <div style="color:#68736d;font-size:12px;margin-top:8px">Use the editor below to update payment dates, amounts, and balance.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return schedule


def render_payment_schedule_editor(customer: sqlite3.Row, order_total: float) -> None:
    schedule = payment_schedule_values(customer, order_total)
    customer_id = int(customer["id"])
    with st.expander("Edit payment schedule / 编辑付款方式", expanded=False):
        st.caption("You can manually update when each payment is due and how much has been paid.")
        first_col, second_col = st.columns(2)
        with first_col:
            first_date = st.date_input(
                "First payment date",
                value=date_from_iso(schedule["first_date"], date.today()),
                key=f"first-payment-date-{customer_id}",
            )
            first_amount = st.number_input(
                "First payment amount ($)",
                min_value=0.0,
                value=float(schedule["first_amount"]),
                step=100.0,
                key=f"first-payment-amount-{customer_id}",
            )
            first_paid = st.checkbox(
                "First payment paid / 第一笔已付款",
                value=bool(schedule["first_paid"]),
                key=f"first-payment-paid-{customer_id}",
            )
        with second_col:
            second_enabled = st.checkbox(
                "Use second payment / 需要第二笔付款",
                value=bool(schedule["second_enabled"]),
                key=f"second-payment-enabled-{customer_id}",
            )
            if second_enabled:
                second_date = st.date_input(
                    "Second payment date",
                    value=date_from_iso(schedule["second_date"], date.today()),
                    key=f"second-payment-date-{customer_id}",
                )
                second_amount = st.number_input(
                    "Second payment amount ($)",
                    min_value=0.0,
                    value=float(schedule["second_amount"]),
                    step=100.0,
                    key=f"second-payment-amount-{customer_id}",
                )
                second_paid = st.checkbox(
                    "Second payment paid / 第二笔已付款",
                    value=bool(schedule["second_paid"]),
                    key=f"second-payment-paid-{customer_id}",
                )
            else:
                second_date = date_from_iso(schedule["second_date"], date.today())
                second_amount = float(schedule["second_amount"])
                second_paid = bool(schedule["second_paid"])

        paid_total = (float(first_amount) if first_paid else 0.0) + (float(second_amount) if second_enabled and second_paid else 0.0)
        balance_due = max(float(order_total) - paid_total, 0.0)
        st.caption(
            f"Order total: {money(float(order_total))} · "
            f"Paid total: {money(paid_total)} · "
            f"Balance due: {money(balance_due)}"
        )
        if st.button("Save payment schedule", key=f"save-payment-schedule-{customer_id}", width="stretch"):
            update_customer_payment_schedule(
                customer_id,
                first_date,
                float(first_amount),
                bool(first_paid),
                bool(second_enabled),
                second_date,
                float(second_amount),
                bool(second_paid),
            )
            st.success("Payment schedule updated.")
            st.rerun()


def quote_product_choices(row: sqlite3.Row) -> list[dict[str, Any]]:
    payload = quote_payload(row)
    items = payload.get("items", [])
    if not isinstance(items, list):
        return []
    choices: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("product_id") or f"Product {index}")
            choices.append(
                {
                    "source": "quote",
                    "quote_number": row["quote_number"],
                    "item_index": index,
                    "product_id": str(item.get("product_id") or ""),
                    "name": name,
                    "snapshot": item,
                }
            )
    return choices


def customer_service_product_choices(customer_id: int) -> list[dict[str, Any]]:
    choices: list[dict[str, Any]] = []
    for quote_row in customer_quotes(customer_id):
        choices.extend(quote_product_choices(quote_row))
    if choices:
        return choices
    customer = customer_by_id(customer_id)
    if customer:
        for index, item in enumerate(parse_wishlist(customer["wishlist"]), start=1):
            name = str(item.get("name") or item.get("product_id") or f"Wishlist product {index}")
            choices.append(
                {
                    "source": "wishlist",
                    "quote_number": "",
                    "item_index": index,
                    "product_id": str(item.get("product_id") or ""),
                    "name": name,
                    "snapshot": item,
                }
            )
    return choices


def service_request_number() -> str:
    return f"SR-{datetime.now():%Y%m%d}-{datetime.now():%H%M%S}"


def add_service_timeline_event(
    service_request_id: int,
    event_date: date | str,
    status: str,
    title: str,
    notes: str = "",
) -> None:
    event_value = event_date.isoformat() if isinstance(event_date, date) else event_date
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO service_timeline
            (service_request_id, event_date, status, title, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                service_request_id,
                event_value,
                status,
                title,
                notes.strip(),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def service_timeline(service_request_id: int) -> list[sqlite3.Row]:
    with db_connect() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """
            SELECT * FROM service_timeline
            WHERE service_request_id = ?
            ORDER BY event_date ASC, created_at ASC
            """,
            (service_request_id,),
        ).fetchall()


def service_requests(search: str = "", status: str = "") -> list[sqlite3.Row]:
    query = """
        SELECT service_requests.*, customers.name AS linked_customer_name
        FROM service_requests
        LEFT JOIN customers ON customers.id = service_requests.customer_id
    """
    clauses: list[str] = []
    params: list[Any] = []
    owner = customer_owner_filter()
    if owner:
        clauses.append("(customers.id IS NULL OR lower(customers.assigned_to) = lower(?))")
        params.append(owner)
    if status:
        clauses.append("service_requests.status = ?")
        params.append(status)
    if search:
        like = f"%{search.lower()}%"
        clauses.append(
            "(lower(request_number) LIKE ? OR lower(customer_name) LIKE ? OR lower(customer_email) LIKE ? OR "
            "lower(customer_phone) LIKE ? OR lower(project_address) LIKE ? OR lower(quote_number) LIKE ? OR "
            "lower(product_name) LIKE ? OR lower(damaged_part) LIKE ? OR lower(damage_reason) LIKE ? OR "
            "lower(issue_description) LIKE ? OR lower(assigned_to) LIKE ?)"
        )
        params.extend([like] * 11)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += """
        ORDER BY
            CASE service_requests.priority
                WHEN 'Urgent' THEN 0
                WHEN 'High' THEN 1
                WHEN 'Normal' THEN 2
                ELSE 3
            END,
            service_requests.updated_at DESC,
            service_requests.id DESC
    """
    with db_connect() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(query, params).fetchall()


def service_request_by_id(request_id: int | None) -> sqlite3.Row | None:
    if not request_id:
        return None
    with db_connect() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM service_requests WHERE id = ?", (request_id,)).fetchone()


def save_service_request(data: dict[str, Any]) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    payload = {**data, "updated_at": now}
    with db_connect() as conn:
        payload = {**payload, "request_number": service_request_number(), "created_at": now}
        columns = ", ".join(payload)
        placeholders = ", ".join("?" for _ in payload)
        cursor = conn.execute(
            f"INSERT INTO service_requests ({columns}) VALUES ({placeholders})",
            list(payload.values()),
        )
        request_id = int(cursor.lastrowid)
    add_service_timeline_event(
        request_id,
        date.today(),
        data["status"],
        "After-sales request submitted",
        "New service request created and visible to leadership / after-sales team.",
    )
    if data.get("customer_id"):
        add_customer_timeline_event(
            int(data["customer_id"]),
            date.today(),
            "After-sales request submitted",
            f"{payload['request_number']} · {data['product_name']} · {data['damaged_part']}",
            data.get("quote_number") or None,
        )
    return request_id


def update_service_request(
    request_id: int,
    status: str,
    appointment_date: date | None,
    assigned_to: str,
    internal_notes: str,
    timeline_notes: str,
) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    completed_at = now if status in ("Repair completed", "Closed") else None
    updates = {
        "status": status,
        "appointment_date": appointment_date.isoformat() if appointment_date else "",
        "assigned_to": assigned_to.strip(),
        "internal_notes": internal_notes.strip(),
        "completed_at": completed_at,
        "updated_at": now,
    }
    with db_connect() as conn:
        assignments = ", ".join(f"{key} = ?" for key in updates)
        conn.execute(
            f"UPDATE service_requests SET {assignments} WHERE id = ?",
            [*updates.values(), request_id],
        )
    title = "Service status updated"
    if status == "Appointment scheduled":
        title = "Appointment scheduled"
    elif status == "Repairing":
        title = "Repair started"
    elif status == "Repair completed":
        title = "Repair completed"
    add_service_timeline_event(request_id, date.today(), status, title, timeline_notes)


def customer_payment_total(row: sqlite3.Row) -> float:
    first_paid = bool(int(row_value(row, "first_payment_paid", 0) or 0))
    second_enabled = bool(int(row_value(row, "second_payment_enabled", 1) or 0))
    second_paid = bool(int(row_value(row, "second_payment_paid", 0) or 0)) if second_enabled else False
    return (
        float(row["first_payment_amount"] or 0) if first_paid else 0.0
    ) + (
        float(row["second_payment_amount"] or 0) if second_paid else 0.0
    )


def period_bounds(period: str, anchor: date) -> tuple[date, date]:
    if period == "Month":
        start = anchor.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return start, next_month - timedelta(days=1)
    if period == "Quarter":
        quarter_month = ((anchor.month - 1) // 3) * 3 + 1
        start = date(anchor.year, quarter_month, 1)
        next_quarter_month = quarter_month + 3
        if next_quarter_month > 12:
            next_quarter = date(anchor.year + 1, 1, 1)
        else:
            next_quarter = date(anchor.year, next_quarter_month, 1)
        return start, next_quarter - timedelta(days=1)
    start = date(anchor.year, 1, 1)
    return start, date(anchor.year, 12, 31)


def in_date_range(value: str | None, start: date, end: date) -> bool:
    if not value:
        return False
    parsed = date_from_iso(value)
    return start <= parsed <= end


def finance_order_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for customer in company_customer_rows(status="Ordered"):
        wishlist = parse_wishlist(customer["wishlist"])
        summary = order_summary_from_quote(latest_customer_quote(int(customer["id"])), wishlist)
        order_total = float(summary["total"] or 0)
        schedule = payment_schedule_values(customer, order_total)
        records.append(
            {
                "customer_id": int(customer["id"]),
                "customer": customer["name"],
                "company": customer["company"] or "",
                "sales": customer["assigned_to"] or "Unassigned",
                "order_date": customer["order_date"] or "",
                "quote_number": summary.get("quote_number") or "",
                "order_total": order_total,
                "product_total": float(summary.get("product_total") or 0),
                "tax": float(summary.get("tax") or 0),
                "installation": float(summary.get("installation") or 0),
                "first_payment_date": schedule["first_date"],
                "first_payment_amount": float(schedule["first_amount"]),
                "first_payment_paid": bool(schedule["first_paid"]),
                "second_payment_enabled": bool(schedule["second_enabled"]),
                "second_payment_date": schedule["second_date"],
                "second_payment_amount": float(schedule["second_amount"]),
                "second_payment_paid": bool(schedule["second_paid"]),
                "paid_total": float(schedule["paid_total"]),
                "balance": float(schedule["balance"]),
            }
        )
    return records


def payment_amount_in_period(record: dict[str, Any], start: date, end: date) -> float:
    total = 0.0
    if record["first_payment_paid"] and in_date_range(record["first_payment_date"], start, end):
        total += float(record["first_payment_amount"])
    if record["second_payment_paid"] and in_date_range(record["second_payment_date"], start, end):
        total += float(record["second_payment_amount"])
    return total


def finance_csv(records: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "customer",
            "company",
            "sales",
            "order_date",
            "quote_number",
            "order_total",
            "paid_total",
            "balance",
            "first_payment_date",
            "first_payment_amount",
            "first_payment_paid",
            "second_payment_date",
            "second_payment_amount",
            "second_payment_paid",
        ],
    )
    writer.writeheader()
    for record in records:
        writer.writerow({key: record.get(key, "") for key in writer.fieldnames})
    return output.getvalue()


def parse_wishlist(value: str | None) -> list[dict[str, Any]]:
    if not value:
        return []
    try:
        items = json.loads(value)
    except (TypeError, ValueError):
        return []
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def wishlist_from_cart() -> list[dict[str, Any]]:
    wishlist: list[dict[str, Any]] = []
    for item in st.session_state.cart:
        wishlist.append(
            {
                "source": "cart",
                "product_id": item.get("product_id", ""),
                "name": item.get("name", ""),
                "category": item.get("category", ""),
                "direction": item.get("direction", ""),
                "glass": item.get("glass", ""),
                "frame": item.get("frame", ""),
                "color": item.get("color", ""),
                "width": item.get("width", 0),
                "height": item.get("height", 0),
                "quantity": item.get("quantity", 1),
                "unit_price": item.get("unit_price", 0),
                "line_total": item.get("line_total", 0),
                "included_in_quote": cart_item_included(item),
                "notes": item.get("notes", ""),
            }
        )
    return wishlist


def wishlist_from_products(product_ids: list[str]) -> list[dict[str, Any]]:
    wishlist: list[dict[str, Any]] = []
    for product_id in product_ids:
        product = next((item for item in PRODUCTS if item.id == product_id), None)
        if product:
            wishlist.append(
                {
                    "source": "product",
                    "product_id": product.id,
                    "name": product.name,
                    "category": product.category,
                    "quantity": 1,
                    "unit_price": product.minimum_price,
                    "line_total": product.minimum_price,
                    "notes": "",
                }
            )
    return wishlist


def wishlist_total(wishlist: list[dict[str, Any]]) -> float:
    return sum(float(item.get("line_total") or 0) for item in wishlist)


def wishlist_merge_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(item.get("product_id") or item.get("name") or "").strip().lower(),
        round(float(item.get("width") or 0), 3),
        round(float(item.get("height") or 0), 3),
        str(item.get("direction") or "").strip().lower(),
        str(item.get("glass") or "").strip().lower(),
        str(item.get("frame") or "").strip().lower(),
        str(item.get("color") or "").strip().lower(),
        str(item.get("notes") or "").strip().lower(),
        round(float(item.get("unit_price") or 0), 2),
        str(item.get("order_status") or "Wishlist").strip().lower(),
    )


def append_wishlist_items(existing_wishlist: list[dict[str, Any]], new_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = [dict(item) for item in existing_wishlist]
    for new_item_raw in new_items:
        new_item = dict(new_item_raw)
        new_item.setdefault("order_status", "Wishlist")
        match = next((item for item in merged if wishlist_merge_key(item) == wishlist_merge_key(new_item)), None)
        if match:
            match["quantity"] = int(match.get("quantity") or 1) + int(new_item.get("quantity") or 1)
            match["unit_price"] = float(match.get("unit_price") or new_item.get("unit_price") or 0.0)
            match["line_total"] = float(match.get("unit_price") or 0.0) * int(match["quantity"])
        else:
            merged.append(new_item)
    return merged


def append_cart_to_customer_wishlist(customer_id: int | None) -> tuple[int, int]:
    current_wishlist = wishlist_from_cart()
    if not customer_id:
        st.session_state.wishlist_draft = append_wishlist_items(st.session_state.get("wishlist_draft", []), current_wishlist)
        return len(st.session_state.wishlist_draft), len(current_wishlist)
    customer = customer_by_id(int(customer_id))
    existing_wishlist = parse_wishlist(row_value(customer, "wishlist") if customer else None)
    merged_wishlist = append_wishlist_items(existing_wishlist, current_wishlist)
    save_customer_wishlist(int(customer_id), merged_wishlist)
    return len(merged_wishlist), len(current_wishlist)


def item_color_label(item: dict[str, Any]) -> str:
    value = str(item.get("color") or "").strip()
    if not value:
        return ""
    if str(item.get("product_id") or "") == "AC-100" or str(item.get("name") or "").strip().lower() == "roller screen":
        return f"{value} stacking side"
    return f"{value} color"


def wishlist_product_ids(wishlist: list[dict[str, Any]]) -> list[str]:
    return [
        str(item.get("product_id"))
        for item in wishlist
        if item.get("source") != "cart" and item.get("product_id")
    ]


def option_tuple_with_current(options: Sequence[str], current: str | None) -> tuple[str, ...]:
    values = tuple(str(option) for option in options if str(option).strip())
    current_value = str(current or "").strip()
    if current_value and current_value not in values:
        return (*values, current_value)
    return values or (current_value or "",)


def updated_wishlist_item(
    item: dict[str, Any],
    product: Product | None,
    *,
    width: float,
    height: float,
    quantity: int,
    direction: str,
    glass: str,
    frame: str,
    color: str,
    unit_price: float,
    notes: str,
) -> dict[str, Any]:
    updated = dict(item)
    product_id = str(updated.get("product_id") or (product.id if product else ""))
    calculated_unit = float(updated.get("original_unit_price") or updated.get("unit_price") or unit_price or 0.0)
    area_sqft = float(width) * float(height) / 144
    base_rate = float(updated.get("base_rate") or (product.base_rate if product else 0.0) or 0.0)
    sales_base_rate = float(updated.get("sales_base_rate") or base_rate or 0.0)
    if product:
        calculated_unit, breakdown = price_product(product, float(width), float(height), glass, frame)
        area_sqft = float(breakdown.get("area_sqft") or area_sqft)
    unit_price = float(unit_price)
    quantity = int(quantity)
    updated.update(
        {
            "source": updated.get("source") or "cart",
            "product_id": product_id,
            "name": str(updated.get("name") or (product.name if product else "Product")),
            "category": str(updated.get("category") or (product.category if product else "")),
            "direction": direction,
            "glass": glass,
            "frame": frame,
            "color": color,
            "width": float(width),
            "height": float(height),
            "quantity": quantity,
            "area_sqft": area_sqft,
            "base_rate": base_rate,
            "sales_base_rate": sales_base_rate,
            "original_unit_price": calculated_unit,
            "unit_price": unit_price,
            "line_total": unit_price * quantity,
            "price_adjusted": abs(unit_price - calculated_unit) > 0.005,
            "price_adjustment_mode": "unit" if abs(unit_price - calculated_unit) > 0.005 else "",
            "notes": notes,
        }
    )
    return updated


def render_wishlist(wishlist: list[dict[str, Any]], selection_key: str = "", title: str = "Wishlist", editable_customer_id: int | None = None) -> list[int]:
    if not wishlist:
        st.caption("No wishlist saved yet.")
        return []
    st.markdown(f"**{title}**")
    selected_indexes: list[int] = []
    for index, item in enumerate(wishlist, start=1):
        name = item.get("name") or item.get("product_id") or "Product"
        quantity = int(item.get("quantity") or 1)
        product_id = str(item.get("product_id") or "")
        details = []
        if item.get("width") and item.get("height"):
            details.append(f"{float(item['width']):.1f}\" W x {float(item['height']):.1f}\" H")
        if item.get("direction"):
            details.append(str(item["direction"]))
        if item.get("glass"):
            details.append(f"{item['glass']} glass")
        if item.get("frame"):
            details.append(f"{item['frame']} frame")
        if item.get("color"):
            details.append(f"{item['color']} color")
        order_status = str(item.get("order_status") or "").strip()
        if order_status:
            details.append(f"Status: {order_status}")
        amount = float(item.get("line_total") or 0)
        line = f"{index}. **{name}** x {quantity}"
        if details:
            line += "  \n" + " · ".join(details)
        if amount:
            line += f"  \nEstimated: **{money(amount)}**"

        with st.container(border=True):
            can_edit = editable_customer_id is not None
            if selection_key and can_edit:
                image_col, info_col, edit_col, select_col = st.columns([0.55, 3.0, 0.9, 0.8], vertical_alignment="top")
            elif selection_key:
                image_col, info_col, select_col = st.columns([0.55, 3.45, 0.8], vertical_alignment="top")
                edit_col = None
            elif can_edit:
                image_col, info_col, edit_col = st.columns([0.55, 3.45, 1.0], vertical_alignment="top")
                select_col = None
            else:
                image_col, info_col = st.columns([0.55, 4], vertical_alignment="top")
                edit_col = None
                select_col = None
            with image_col:
                product = get_product_or_none(product_id) if product_id else None
                if product and image_path(product, "hero").exists():
                    st.image(str(image_path(product, "hero")), width="stretch")
            with info_col:
                st.markdown(line)
                if product_id:
                    stock_label, stock_color = inventory_status_text(
                        product_id,
                        requested=quantity,
                        color=str(item.get("color") or ""),
                    )
                    st.markdown(f"<span style='color:{stock_color};font-weight:700'>{stock_label}</span>", unsafe_allow_html=True)
                if item.get("notes"):
                    st.caption(str(item["notes"]))
            edit_state_key = f"wishlist-edit-open-{editable_customer_id}-{index - 1}"
            if edit_col is not None:
                with edit_col:
                    edit_label = "Close" if st.session_state.get(edit_state_key, False) else "Edit"
                    if st.button(edit_label, key=f"wishlist-edit-toggle-{editable_customer_id}-{index - 1}", width="stretch"):
                        st.session_state[edit_state_key] = not st.session_state.get(edit_state_key, False)
                        st.rerun()
            if st.session_state.get(edit_state_key, False) and editable_customer_id is not None:
                product = get_product_or_none(product_id) if product_id else None
                direction_options = option_tuple_with_current(product.directions if product else (), item.get("direction"))
                glass_options = option_tuple_with_current(product.glass_colors if product else (), item.get("glass"))
                frame_options = option_tuple_with_current(product.frame_colors if product else (), item.get("frame"))
                color_options = option_tuple_with_current((product.color_options or product.frame_colors) if product else (), item.get("color"))
                with st.form(f"wishlist-edit-form-{editable_customer_id}-{index - 1}"):
                    edit_cols = st.columns(3)
                    with edit_cols[0]:
                        new_width = st.number_input("Width (inches)", min_value=12.0, max_value=360.0, value=float(item.get("width") or 72.0), step=0.5, key=f"wishlist-width-{editable_customer_id}-{index - 1}")
                    with edit_cols[1]:
                        new_height = st.number_input("Height (inches)", min_value=12.0, max_value=240.0, value=float(item.get("height") or 96.0), step=0.5, key=f"wishlist-height-{editable_customer_id}-{index - 1}")
                    with edit_cols[2]:
                        new_quantity = st.number_input("Qty", min_value=1, max_value=99, value=int(item.get("quantity") or 1), step=1, key=f"wishlist-qty-{editable_customer_id}-{index - 1}")
                    option_cols = st.columns(4)
                    with option_cols[0]:
                        new_direction = st.selectbox("Opening / handing", direction_options, index=option_index(direction_options, str(item.get("direction") or "")), key=f"wishlist-direction-{editable_customer_id}-{index - 1}")
                    with option_cols[1]:
                        new_glass = st.selectbox("Glass", glass_options, index=option_index(glass_options, str(item.get("glass") or "")), key=f"wishlist-glass-{editable_customer_id}-{index - 1}")
                    with option_cols[2]:
                        new_frame = st.selectbox("Frame / finish", frame_options, index=option_index(frame_options, str(item.get("frame") or "")), key=f"wishlist-frame-{editable_customer_id}-{index - 1}")
                    with option_cols[3]:
                        new_color = st.selectbox("Color", color_options, index=option_index(color_options, str(item.get("color") or "")), key=f"wishlist-color-{editable_customer_id}-{index - 1}")
                    price_cols = st.columns([1, 2])
                    with price_cols[0]:
                        new_unit_price = st.number_input("Unit price", min_value=0.0, value=float(item.get("unit_price") or item.get("line_total") or 0.0) / max(int(item.get("quantity") or 1), 1), step=10.0, key=f"wishlist-unit-price-{editable_customer_id}-{index - 1}")
                    with price_cols[1]:
                        new_notes = st.text_input("Item notes", value=str(item.get("notes") or ""), key=f"wishlist-notes-{editable_customer_id}-{index - 1}")
                    save_col, cancel_col = st.columns([1, 1])
                    save_edit = save_col.form_submit_button("Save wishlist item", type="primary", width="stretch")
                    cancel_edit = cancel_col.form_submit_button("Cancel", width="stretch")
                    if save_edit:
                        updated_wishlist = [dict(entry) for entry in wishlist]
                        updated_wishlist[index - 1] = updated_wishlist_item(
                            item,
                            product,
                            width=float(new_width),
                            height=float(new_height),
                            quantity=int(new_quantity),
                            direction=str(new_direction),
                            glass=str(new_glass),
                            frame=str(new_frame),
                            color=str(new_color),
                            unit_price=float(new_unit_price),
                            notes=str(new_notes),
                        )
                        save_customer_wishlist(int(editable_customer_id), updated_wishlist)
                        st.session_state[edit_state_key] = False
                        st.success("Wishlist item updated.")
                        st.rerun()
                    if cancel_edit:
                        st.session_state[edit_state_key] = False
                        st.rerun()
            if select_col is not None:
                with select_col:
                    if st.checkbox(
                        "Order",
                        key=f"{selection_key}-{index - 1}",
                    ):
                        selected_indexes.append(index - 1)
    total = wishlist_total(wishlist)
    if total and title == "Wishlist":
        st.metric("Wishlist estimated total", money(total))
    return selected_indexes


def followup_progress(row: sqlite3.Row) -> float:
    if row["on_hold"]:
        return 0.0
    start = date_from_iso(row["first_followup_date"], date.today())
    end = date_from_iso(row["next_followup_date"], start + timedelta(days=7))
    total_days = max((end - start).days, 1)
    elapsed = (date.today() - start).days
    return min(max(elapsed / total_days, 0.0), 1.0)


def get_product(product_id: str) -> Product:
    return next(p for p in PRODUCTS if p.id == product_id)


def get_product_or_none(product_id: str) -> Product | None:
    return next((p for p in PRODUCTS if p.id == product_id), None)


def price_product_with_rate(product: Product, width_in: float, height_in: float, glass: str, frame: str, base_rate: float) -> tuple[float, dict[str, float]]:
    area_sqft = width_in * height_in / 144
    calculated = area_sqft * float(base_rate)
    unit_price = max(calculated, product.minimum_price)
    return unit_price, {
        "area_sqft": area_sqft,
        "base_rate": float(base_rate),
        "glass_factor": 1.0,
        "frame_factor": 1.0,
        "calculated": calculated,
    }


def price_product(product: Product, width_in: float, height_in: float, glass: str, frame: str) -> tuple[float, dict[str, float]]:
    return price_product_with_rate(product, width_in, height_in, glass, frame, product.base_rate)


def legacy_label_map() -> dict[str, str]:
    return {
        "Contractor / \u627f\u5305\u5546": "Contractor",
        "Homeowner / \u4e1a\u4e3b": "Homeowner",
        "Reseller / \u7ecf\u9500\u5546": "Reseller",
        "Developer / \u5f00\u53d1\u5546": "Developer",
        "New Build / \u65b0\u5efa": "New Build",
        "Remodel / \u7ffb\u65b0": "Remodel",
        "Replacement / \u66f4\u6362": "Replacement",
        "High / \u9ad8": "High",
        "Medium / \u4e2d": "Medium",
        "Low / \u4f4e": "Low",
        "New lead / \u65b0\u5ba2\u6237": "New lead",
        "Quoted / \u5df2\u62a5\u4ef7": "Quoted",
        "Measuring / \u91cf\u5c3a\u4e2d": "Measuring",
        "Negotiating / \u6c9f\u901a\u4ef7\u683c": "Negotiating",
        "Waiting customer / \u7b49\u5ba2\u6237\u56de\u590d": "Waiting for customer reply",
        "On hold / \u6682\u505c": "On hold",
        "Not scheduled / \u672a\u5b89\u6392": "Not scheduled",
        "Measurement needed / \u5f85\u91cf\u5c3a": "Measurement needed",
        "Production / \u751f\u4ea7\u4e2d": "Production",
        "Ready to install / \u5f85\u5b89\u88c5": "Ready to install",
        "Installed / \u5df2\u5b89\u88c5": "Installed",
        "After-sales / \u552e\u540e\u8ddf\u8fdb": "After-sales follow-up",
        "Price / \u4ef7\u683c\u539f\u56e0": "Price",
        "Timeline / \u4ea4\u671f\u539f\u56e0": "Timeline",
        "Competitor / \u9009\u62e9\u7ade\u54c1": "Competitor",
        "No response / \u6ca1\u6709\u56de\u590d": "No response",
        "Project cancelled / \u9879\u76ee\u53d6\u6d88": "Project cancelled",
        "Product mismatch / \u4ea7\u54c1\u4e0d\u5339\u914d": "Product mismatch",
        "Other / \u5176\u4ed6": "Other",
        "New request / \u65b0\u552e\u540e": "New service request",
        "Reviewing / \u552e\u540e\u5ba1\u6838\u4e2d": "Reviewing",
        "Appointment scheduled / \u5df2\u548c\u5ba2\u6237\u9884\u7ea6\u65f6\u95f4": "Appointment scheduled",
        "Repairing / \u6b63\u5728\u7ef4\u4fee": "Repairing",
        "Waiting parts / \u7b49\u5f85\u914d\u4ef6": "Waiting for parts",
        "Completed / \u5df2\u7ef4\u4fee\u5b8c\u6210": "Repair completed",
        "Closed / \u5df2\u5173\u95ed": "Closed",
        "Urgent / \u7d27\u6025": "Urgent",
        "Normal / \u666e\u901a": "Normal",
        "Glass / \u73bb\u7483": "Glass",
        "Frame / \u6846\u67b6": "Frame",
        "Hardware / \u4e94\u91d1": "Hardware",
        "Track or roller / \u8f68\u9053\u6216\u6ed1\u8f6e": "Track or roller",
        "Lock / \u9501\u5177": "Lock",
        "Screen / \u7eb1\u7a97": "Screen",
        "Seal / \u5bc6\u5c01\u6761": "Seal",
        "Paint or finish / \u8868\u9762\u989c\u8272": "Paint or finish",
        "Installation issue / \u5b89\u88c5\u95ee\u9898": "Installation issue",
        "Product defect / \u4ea7\u54c1\u8d28\u91cf\u95ee\u9898": "Product defect",
        "Shipping damage / \u8fd0\u8f93\u635f\u574f": "Shipping damage",
        "Customer damage / \u5ba2\u6237\u4f7f\u7528\u635f\u574f": "Customer damage",
        "Weather or water / \u5929\u6c14\u6216\u8fdb\u6c34": "Weather or water",
        "Normal wear / \u6b63\u5e38\u635f\u8017": "Normal wear",
        "Unknown / \u539f\u56e0\u5f85\u786e\u8ba4": "Unknown cause",
        "Contractor / Contractor": "Contractor",
        "Homeowner / Homeowner": "Homeowner",
        "Reseller / Reseller": "Reseller",
        "Developer / Developer": "Developer",
        "New Build / New Build": "New Build",
        "Remodel / Remodel": "Remodel",
        "Replacement / Replacement": "Replacement",
        "High / High": "High",
        "Medium / Medium": "Medium",
        "Low / Low": "Low",
        "New lead / New lead": "New lead",
        "Quoted / Quoted": "Quoted",
        "Negotiating / Negotiating": "Negotiating",
        "Waiting customer / Waiting for customer reply": "Waiting for customer reply",
        "On hold / On hold": "On hold",
        "Not scheduled / Not scheduled": "Not scheduled",
        "Measurement needed / Measurement needed": "Measurement needed",
        "Ready to install / Ready to install": "Ready to install",
        "Installed / Installed": "Installed",
        "After-sales / After-sales follow-up": "After-sales follow-up",
        "New request / New service request": "New service request",
        "Appointment scheduled / Appointment scheduled": "Appointment scheduled",
        "Repairing / Repairing": "Repairing",
        "Waiting parts / Waiting for parts": "Waiting for parts",
        "Completed / Repair completed": "Repair completed",
        "Closed / Closed": "Closed",
        "Urgent / Urgent": "Urgent",
        "Normal / Normal": "Normal",
    }


def normalize_legacy_database_labels(conn: sqlite3.Connection) -> None:
    replacements = legacy_label_map()
    update_targets = {
        "customers": (
            "client_type",
            "project_type",
            "use_case",
            "showroom_status",
            "answer_status",
            "priority",
            "followup_stage",
            "install_status",
            "lost_reason",
        ),
        "service_requests": (
            "status",
            "priority",
            "damaged_part",
            "damage_reason",
        ),
        "service_timeline": ("status",),
    }
    for table, columns in update_targets.items():
        existing_tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if table not in existing_tables:
            continue
        table_columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for column in columns:
            if column not in table_columns:
                continue
            for old, new in replacements.items():
                conn.execute(
                    f"UPDATE {table} SET {column} = ? WHERE {column} = ?",
                    (new, old),
                )


def quote_discount_raw_value() -> float:
    discount_type = st.session_state.get("quote_discount_type", "No discount")
    if discount_type == "Percent %":
        return float(st.session_state.get("quote_discount_percent_value", st.session_state.get("quote_discount_value", 0.0)) or 0.0)
    if discount_type == "Amount $":
        return float(st.session_state.get("quote_discount_amount_value", st.session_state.get("quote_discount_value", 0.0)) or 0.0)
    return 0.0


def cart_discount(subtotal: float) -> tuple[float, str]:
    discount_type = st.session_state.get("quote_discount_type", "No discount")
    discount_value = quote_discount_raw_value()
    if discount_type == "Percent %":
        amount = subtotal * min(max(discount_value, 0.0), 100.0) / 100
        label = f"{discount_value:.2f}% discount"
    elif discount_type == "Amount $":
        amount = min(max(discount_value, 0.0), subtotal)
        label = "Discount"
    else:
        amount = 0.0
        label = ""
    return amount, label


def quote_tax_rate() -> float:
    return FIXED_SALES_TAX_RATE if st.session_state.get("quote_sales_tax_enabled", False) else 0.0


def quote_tax_label() -> str:
    rate = quote_tax_rate() * 100
    return f"Sales tax ({rate:.2f}%)" if rate else "Sales tax"


def quote_installation_fee() -> float:
    return max(float(st.session_state.get("quote_installation_fee", 0.0) or 0.0), 0.0)


def quote_shipping_fee() -> float:
    if not st.session_state.get("quote_shipping_enabled", False):
        return 0.0
    return max(float(st.session_state.get("quote_shipping_fee", 0.0) or 0.0), 0.0)


def sync_cart_item_price(item: dict[str, Any], unit_price: float) -> None:
    quantity = int(item.get("quantity", 1) or 1)
    original_unit = float(item.get("original_unit_price", item.get("unit_price", unit_price)) or 0.0)
    item["original_unit_price"] = original_unit
    item["unit_price"] = float(unit_price)
    item["line_total"] = float(unit_price) * quantity
    item["price_adjusted"] = abs(float(unit_price) - original_unit) > 0.005
    item["price_adjustment_mode"] = "unit" if item["price_adjusted"] else ""


def update_cart_item_configuration(
    item: dict[str, Any],
    product: Product,
    width: float,
    height: float,
    quantity: int,
    direction: str | None = None,
    glass: str | None = None,
    frame: str | None = None,
    color: str | None = None,
    notes: str | None = None,
) -> bool:
    width = float(width)
    height = float(height)
    quantity = int(quantity)
    direction = str(direction if direction is not None else item.get("direction") or (product.directions[0] if product.directions else ""))
    glass = str(glass if glass is not None else item.get("glass") or (product.glass_colors[0] if product.glass_colors else ""))
    frame = str(frame if frame is not None else item.get("frame") or (product.frame_colors[0] if product.frame_colors else ""))
    color = str(color if color is not None else item.get("color") or ((product.color_options or product.frame_colors)[0] if (product.color_options or product.frame_colors) else ""))
    notes = str(notes if notes is not None else item.get("notes") or "")

    current_values = (
        round(float(item.get("width") or 0.0), 3),
        round(float(item.get("height") or 0.0), 3),
        int(item.get("quantity") or 1),
        str(item.get("direction") or ""),
        str(item.get("glass") or ""),
        str(item.get("frame") or ""),
        str(item.get("color") or ""),
        str(item.get("notes") or ""),
    )
    new_values = (round(width, 3), round(height, 3), quantity, direction, glass, frame, color, notes)
    if current_values == new_values:
        return False

    calculated_unit, breakdown = price_product(product, width, height, glass, frame)
    sales_base_rate = float(item.get("sales_base_rate", product.base_rate) or product.base_rate)
    sales_unit_from_rate, sales_breakdown = price_product_with_rate(product, width, height, glass, frame, sales_base_rate)
    previous_unit = float(item.get("unit_price", calculated_unit) or calculated_unit)
    adjustment_mode = str(item.get("price_adjustment_mode") or "")
    was_unit_adjusted = bool(item.get("price_adjusted")) and adjustment_mode != "rate"

    item["direction"] = direction
    item["glass"] = glass
    item["frame"] = frame
    item["color"] = color
    item["width"] = width
    item["height"] = height
    item["quantity"] = quantity
    item["area_sqft"] = sales_breakdown["area_sqft"]
    item["base_rate"] = product.base_rate
    item["sales_base_rate"] = sales_base_rate
    item["original_unit_price"] = calculated_unit
    item["notes"] = notes
    if adjustment_mode == "rate":
        item["unit_price"] = sales_unit_from_rate
        item["price_adjusted"] = abs(sales_base_rate - float(product.base_rate)) > 0.005
    elif was_unit_adjusted:
        item["unit_price"] = previous_unit
        item["price_adjusted"] = abs(previous_unit - calculated_unit) > 0.005
        item["price_adjustment_mode"] = "unit" if item["price_adjusted"] else ""
    else:
        item["unit_price"] = calculated_unit
        item["price_adjusted"] = False
        item["price_adjustment_mode"] = ""
    item["line_total"] = float(item["unit_price"]) * quantity
    return True


def normalize_cart_item(item: dict[str, Any], index: int = 0) -> bool:
    changed = False
    if not item.get("line_id"):
        raw = f"{item.get('product_id', '')}-{item.get('name', '')}-{index}-{datetime.now().isoformat()}"
        item["line_id"] = hashlib.sha1(raw.encode()).hexdigest()[:10]
        changed = True
    if not item.get("quantity"):
        item["quantity"] = 1
        changed = True
    if "original_unit_price" not in item:
        item["original_unit_price"] = float(item.get("unit_price", 0.0) or 0.0)
        changed = True
    if "unit_price" not in item:
        item["unit_price"] = float(item.get("original_unit_price", 0.0) or 0.0)
        changed = True
    if "line_total" not in item:
        sync_cart_item_price(item, float(item.get("unit_price", 0.0) or 0.0))
        changed = True
    if "price_adjusted" not in item:
        item["price_adjusted"] = abs(float(item.get("unit_price", 0.0) or 0.0) - float(item.get("original_unit_price", 0.0) or 0.0)) > 0.005
        changed = True
    if "included_in_quote" not in item:
        item["included_in_quote"] = True
        changed = True
    return changed


def cart_merge_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(item.get("product_id") or "").strip().lower(),
        round(float(item.get("width") or 0), 3),
        round(float(item.get("height") or 0), 3),
        str(item.get("direction") or "").strip().lower(),
        str(item.get("glass") or "").strip().lower(),
        str(item.get("frame") or "").strip().lower(),
        str(item.get("color") or "").strip().lower(),
        str(item.get("notes") or "").strip().lower(),
        round(float(item.get("unit_price") or 0), 2),
        round(float(item.get("original_unit_price", item.get("unit_price", 0)) or 0), 2),
        bool(item.get("price_adjusted")),
        cart_item_included(item),
    )


def add_or_merge_cart_item(new_item: dict[str, Any]) -> bool:
    new_key = cart_merge_key(new_item)
    for existing in st.session_state.cart:
        normalize_cart_item(existing)
        if cart_merge_key(existing) == new_key:
            existing["quantity"] = int(existing.get("quantity") or 1) + int(new_item.get("quantity") or 1)
            existing["included_in_quote"] = cart_item_included(existing) or cart_item_included(new_item)
            existing["line_total"] = float(existing.get("unit_price") or 0) * int(existing["quantity"])
            return True
    st.session_state.cart.append(new_item)
    return False


def merge_duplicate_cart_items(cart: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    merged_items: list[dict[str, Any]] = []
    changed = False
    for index, raw_item in enumerate(cart):
        item = dict(raw_item)
        changed = normalize_cart_item(item, index) or changed
        item_key = cart_merge_key(item)
        match = next((existing for existing in merged_items if cart_merge_key(existing) == item_key), None)
        if match:
            match["quantity"] = int(match.get("quantity") or 1) + int(item.get("quantity") or 1)
            match["included_in_quote"] = cart_item_included(match) or cart_item_included(item)
            match["line_total"] = float(match.get("unit_price") or 0) * int(match["quantity"])
            changed = True
        else:
            merged_items.append(item)
    return merged_items, changed


def save_customer(customer_id: int | None, data: dict[str, Any]) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    if not data.get("assigned_to"):
        owner = default_customer_owner()
        if owner:
            data = {**data, "assigned_to": owner}
    data = {**data, "updated_at": now}
    if supabase_customers_enabled():
        save_payload = dict(data)
        if not customer_id:
            save_payload["created_at"] = now
        try:
            saved_customer_id = supabase_save_customer(customer_id, save_payload)
            mirror_customer_to_sqlite(saved_customer_id, {**save_payload, "id": saved_customer_id})
            return saved_customer_id
        except Exception as exc:
            st.error(f"Customer could not be saved to Supabase: {exc}")
            st.stop()
    with db_connect() as conn:
        if customer_id:
            assignments = ", ".join(f"{key} = ?" for key in data)
            conn.execute(
                f"UPDATE customers SET {assignments} WHERE id = ?",
                [*data.values(), customer_id],
            )
            return customer_id
        data = {**data, "created_at": now}
        columns = ", ".join(data)
        placeholders = ", ".join("?" for _ in data)
        cursor = conn.execute(
            f"INSERT INTO customers ({columns}) VALUES ({placeholders})",
            list(data.values()),
        )
        return int(cursor.lastrowid)


def update_customer_status(
    customer_id: int,
    status: str,
    followup_stage: str = "",
    next_followup_date: date | None = None,
    lost_reason: str = "",
    lost_notes: str = "",
    order_date: date | None = None,
) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    existing = customer_by_id(customer_id)
    inventory_messages: list[str] = []
    updates: dict[str, Any] = {
        "status": status,
        "updated_at": now,
    }
    title = f"Status changed to {STATUS_LABELS.get(status, status)}"
    notes = ""
    if status == "Following":
        updates["followup_stage"] = followup_stage or "Waiting for customer reply"
        updates["next_followup_date"] = (next_followup_date or date.today() + timedelta(days=7)).isoformat()
        updates["on_hold"] = 0
        notes = f"Stage: {updates['followup_stage']}. Next follow-up: {display_date(updates['next_followup_date'])}."
    elif status == "Lost":
        updates["lost_date"] = today_iso()
        updates["lost_reason"] = lost_reason
        updates["lost_notes"] = lost_notes.strip()
        notes = f"Reason: {lost_reason}."
        if lost_notes.strip():
            notes += f" {lost_notes.strip()}"
    elif status == "Ordered":
        order_day = order_date or date.today()
        updates["order_date"] = order_day.isoformat()
        if not followup_stage:
            updates["followup_stage"] = "Quoted"
        notes = f"Order date: {display_date(updates['order_date'])}."
        if existing is not None and existing["status"] != "Ordered":
            wishlist = parse_wishlist(existing["wishlist"])
            if wishlist:
                updated_wishlist, inventory_messages = deduct_inventory_for_order_items(wishlist)
                updates["wishlist"] = json.dumps(updated_wishlist, ensure_ascii=False)
                if production_required_items(updated_wishlist):
                    updates["install_followup_date"] = (order_day + timedelta(days=70)).isoformat()

    if supabase_customers_enabled():
        try:
            supabase_update_customer(customer_id, updates)
        except Exception as exc:
            st.error(f"Customer status could not be saved to Supabase: {exc}")
            raise
    else:
        with db_connect() as conn:
            assignments = ", ".join(f"{key} = ?" for key in updates)
            conn.execute(
                f"UPDATE customers SET {assignments} WHERE id = ?",
                [*updates.values(), customer_id],
            )
    add_customer_timeline_event(customer_id, date.today(), title, notes)
    if inventory_messages:
        add_customer_timeline_event(
            customer_id,
            date.today(),
            "Inventory updated",
            " ".join(inventory_messages),
        )
    if status == "Ordered" and updates.get("install_followup_date"):
        add_customer_timeline_event(
            customer_id,
            date.today(),
            "Production required",
            f"One or more ordered products need factory production. Installation reminder set for {display_date(updates['install_followup_date'])}.",
        )


def update_customer_basic_info(customer_id: int, data: dict[str, Any]) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    updates = {**data, "updated_at": now}
    if supabase_customers_enabled():
        try:
            supabase_update_customer(customer_id, updates)
        except Exception as exc:
            st.error(f"Customer information could not be saved to Supabase: {exc}")
            raise
    else:
        with db_connect() as conn:
            assignments = ", ".join(f"{key} = ?" for key in updates)
            conn.execute(
                f"UPDATE customers SET {assignments} WHERE id = ?",
                [*updates.values(), customer_id],
            )
    add_customer_timeline_event(
        customer_id,
        date.today(),
        "Customer information updated",
        "Basic customer information was edited from the customer card.",
    )


def update_customer_owner(customer_id: int, assigned_to: str, previous_owner: str = "") -> None:
    assigned_to = assigned_to.strip()
    now = datetime.now().isoformat(timespec="seconds")
    if supabase_customers_enabled():
        try:
            supabase_update_customer(customer_id, {"assigned_to": assigned_to, "updated_at": now})
        except Exception as exc:
            st.error(f"Customer owner could not be saved to Supabase: {exc}")
            raise
    else:
        with db_connect() as conn:
            conn.execute(
                "UPDATE customers SET assigned_to = ?, updated_at = ? WHERE id = ?",
                (assigned_to, now, customer_id),
            )
    from_label = previous_owner or "Unassigned"
    to_label = assigned_to or "Unassigned"
    add_customer_timeline_event(
        customer_id,
        date.today(),
        "Sales rep reassigned",
        f"Customer owner changed from {from_label} to {to_label}.",
    )


def update_customer_payment_schedule(
    customer_id: int,
    first_payment_date: date,
    first_payment_amount: float,
    first_payment_paid: bool,
    second_payment_enabled: bool,
    second_payment_date: date,
    second_payment_amount: float,
    second_payment_paid: bool,
) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    first_amount = max(float(first_payment_amount), 0.0)
    use_second_payment = bool(second_payment_enabled)
    second_amount = max(float(second_payment_amount), 0.0) if use_second_payment else 0.0
    second_paid_value = bool(second_payment_paid) if use_second_payment else False
    second_date_value = second_payment_date.isoformat() if use_second_payment else ""
    updates: dict[str, Any] = {
        "first_payment_date": first_payment_date.isoformat(),
        "first_payment_amount": first_amount,
        "first_payment_paid": int(first_payment_paid),
        "second_payment_enabled": int(use_second_payment),
        "second_payment_date": second_date_value,
        "second_payment_amount": second_amount,
        "second_payment_paid": int(second_paid_value),
        "updated_at": now,
    }
    if supabase_customers_enabled():
        try:
            supabase_update_customer(customer_id, updates)
            mirror_customer_to_sqlite(customer_id, {**updates, "id": customer_id})
        except Exception as exc:
            st.error(f"Payment schedule could not be saved to Supabase: {exc}")
            st.stop()
    else:
        with db_connect() as conn:
            assignments = ", ".join(f"{key} = ?" for key in updates)
            conn.execute(
                f"UPDATE customers SET {assignments} WHERE id = ?",
                [*updates.values(), customer_id],
            )
    second_note = (
        f"Second payment: {display_date(second_date_value)} · {money(second_amount)} · {'paid' if second_paid_value else 'unpaid'}."
        if use_second_payment
        else "Second payment: not required."
    )
    add_customer_timeline_event(
        customer_id,
        date.today(),
        "Payment schedule updated",
        (
            f"First payment: {display_date(first_payment_date.isoformat())} · {money(first_amount)} · {'paid' if first_payment_paid else 'unpaid'}. "
            f"{second_note}"
        ),
    )


def wishlist_item_label(item: dict[str, Any], index: int) -> str:
    name = item.get("name") or item.get("product_id") or f"Product {index}"
    quantity = int(item.get("quantity") or 1)
    details = []
    if item.get("width") and item.get("height"):
        details.append(f"{float(item['width']):.1f}\" W x {float(item['height']):.1f}\" H")
    if item.get("color"):
        details.append(str(item["color"]))
    if item.get("glass"):
        details.append(f"{item['glass']} glass")
    if item.get("frame"):
        details.append(f"{item['frame']} frame")
    amount = float(item.get("line_total") or 0)
    label = f"{index}. {name} x {quantity}"
    if details:
        label += " · " + " · ".join(details)
    if amount:
        label += f" · {money(amount)}"
    return label


def mark_wishlist_items_ordered(customer_id: int, wishlist: list[dict[str, Any]], selected_indexes: list[int]) -> None:
    if not selected_indexes:
        return
    selected_index_set = {int(index) for index in selected_indexes}
    selected_items = [dict(item) for index, item in enumerate(wishlist) if index in selected_index_set]
    if not selected_items:
        return
    selected_items, inventory_messages = deduct_inventory_for_order_items(selected_items)
    selected_by_index = dict(zip([index for index in range(len(wishlist)) if index in selected_index_set], selected_items))
    preserved_wishlist: list[dict[str, Any]] = []
    for index, item in enumerate(wishlist):
        if index in selected_by_index:
            updated_item = dict(selected_by_index[index])
            updated_item["order_status"] = "Ordered"
        else:
            updated_item = dict(item)
            updated_item.setdefault("order_status", "Wishlist")
        preserved_wishlist.append(updated_item)

    order_day = date.today()
    factory_items = production_required_items(selected_items)
    install_followup_date = (order_day + timedelta(days=70)).isoformat() if factory_items else order_day.isoformat()
    now = datetime.now().isoformat(timespec="seconds")
    product_names = ", ".join(
        dict.fromkeys(str(item.get("name") or item.get("product_id") or "Product") for item in selected_items)
    )
    product_total = wishlist_total(selected_items)
    tax = 0.0
    total = product_total + tax
    first_payment_due = product_total * 0.5
    second_payment_due = product_total * 0.5 + tax
    updates = {
        "status": "Ordered",
        "updated_at": now,
        "order_date": order_day.isoformat(),
        "followup_stage": "Quoted",
        "products_interest": product_names,
        "budget": total,
        "wishlist": json.dumps(preserved_wishlist, ensure_ascii=False),
        "install_status": "Not scheduled",
        "install_followup_date": install_followup_date,
        "first_payment_amount": first_payment_due,
        "first_payment_paid": 0,
        "second_payment_enabled": 1 if second_payment_due > 0 else 0,
        "second_payment_amount": second_payment_due,
        "first_payment_date": today_iso(),
        "second_payment_date": today_iso(),
        "second_payment_paid": 0,
        "on_hold": 0,
    }
    if supabase_customers_enabled():
        try:
            supabase_update_customer(customer_id, updates)
            mirror_customer_to_sqlite(customer_id, {**updates, "id": customer_id})
        except Exception as exc:
            st.error(f"Ordered status could not be saved to Supabase: {exc}")
            st.stop()
    else:
        with db_connect() as conn:
            assignments = ", ".join(f"{key} = ?" for key in updates)
            conn.execute(
                f"UPDATE customers SET {assignments} WHERE id = ?",
                [*updates.values(), customer_id],
            )
    save_customer_cart(customer_id, selected_items)
    add_customer_timeline_event(
        customer_id,
        date.today(),
        "Wishlist products marked as ordered",
        f"Ordered products: {product_names}. Estimated total: {money(total)}.",
    )
    if inventory_messages:
        add_customer_timeline_event(
            customer_id,
            date.today(),
            "Inventory updated",
            " ".join(inventory_messages),
        )
    if factory_items:
        add_customer_timeline_event(
            customer_id,
            date.today(),
            "Production required",
            f"{len(factory_items)} product line(s) need factory production. Installation reminder set for {display_date(install_followup_date)}.",
        )


def delete_customer(customer_id: int) -> None:
    if supabase_customers_enabled():
        try:
            supabase_delete_customer(customer_id)
        except Exception as exc:
            st.error(f"Customer could not be deleted from Supabase: {exc}")
            raise
    with db_connect() as conn:
        quote_rows = conn.execute(
            "SELECT quote_number FROM quotes WHERE customer_id = ?",
            (customer_id,),
        ).fetchall()
        conn.execute("DELETE FROM customer_timeline WHERE customer_id = ?", (customer_id,))
        conn.execute("DELETE FROM customer_carts WHERE customer_id = ?", (customer_id,))
        conn.execute("DELETE FROM quotes WHERE customer_id = ?", (customer_id,))
        if not supabase_customers_enabled():
            conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    for quote_row in quote_rows:
        quote_path = OUTPUT_DIR / f"{quote_row[0]}.pdf"
        if quote_path.exists():
            quote_path.unlink()
    if st.session_state.get("active_customer_id") == customer_id:
        st.session_state.active_customer_id = None
        st.session_state.cart = []
    if st.session_state.get("customer_editor_id") == customer_id:
        st.session_state.customer_editor_id = None
    if st.session_state.get("inline_customer_editor_id") == customer_id:
        st.session_state.inline_customer_editor_id = None


ZIP_CITY_PREFIXES = {
    "900": "Los Angeles",
    "901": "Los Angeles",
    "902": "Beverly Hills",
    "903": "Inglewood",
    "904": "Santa Monica",
    "905": "Torrance",
    "906": "Whittier",
    "907": "Long Beach",
    "908": "Long Beach",
    "910": "Pasadena",
    "911": "Pasadena",
    "912": "Glendale",
    "913": "San Fernando Valley",
    "914": "Van Nuys",
    "915": "Burbank",
    "916": "North Hollywood",
    "917": "Ontario",
    "918": "Alhambra",
    "919": "San Diego",
    "920": "San Diego",
    "921": "San Diego",
    "922": "Palm Springs",
    "923": "San Bernardino",
    "924": "San Bernardino",
    "925": "Riverside",
    "926": "Irvine",
    "927": "Santa Ana",
    "928": "Anaheim",
    "930": "Ventura",
    "931": "Santa Barbara",
    "932": "Bakersfield",
    "933": "Bakersfield",
    "934": "San Luis Obispo",
    "935": "Lancaster",
    "936": "Fresno",
    "937": "Fresno",
    "938": "Fresno",
    "939": "Salinas",
    "940": "San Mateo",
    "941": "San Francisco",
    "943": "Palo Alto",
    "944": "San Mateo",
    "945": "Oakland",
    "946": "Oakland",
    "947": "Berkeley",
    "948": "Richmond",
    "949": "Marin",
    "950": "San Jose",
    "951": "San Jose",
    "952": "Stockton",
    "953": "Modesto",
    "954": "Santa Rosa",
    "955": "Eureka",
    "956": "Sacramento",
    "957": "Sacramento",
    "958": "Sacramento",
    "959": "Chico",
    "960": "Redding",
}


def city_from_address(value: str) -> str:
    text_value = " ".join(str(value or "").replace("\n", ", ").split())
    if not text_value:
        return ""
    parts = [part.strip() for part in text_value.split(",") if part.strip()]
    if len(parts) >= 3 and re.search(r"\b[A-Z]{2}\b|California", parts[-1], re.IGNORECASE):
        return parts[-2].title()
    match = re.search(r"([A-Za-z][A-Za-z .'-]+?)\s*,\s*(?:CA|California)\s+\d{5}(?:-\d{4})?", text_value, re.IGNORECASE)
    if match:
        return match.group(1).strip().title()
    return ""


def city_from_zip(value: str) -> str:
    match = re.search(r"\b(\d{5})(?:-\d{4})?\b", str(value or ""))
    if not match:
        return ""
    return ZIP_CITY_PREFIXES.get(match.group(1)[:3], "")


def customer_city_label(row: sqlite3.Row | dict[str, Any]) -> str:
    saved_city = str(row_value(row, "city", "")).strip()
    if saved_city:
        return saved_city.title()
    address = row_value(row, "address")
    city = city_from_address(address)
    if city:
        return city
    for value in (row_value(row, "area_zip"), address):
        city = city_from_zip(value)
        if city:
            return city
    return ""



def customer_title_detail(row: sqlite3.Row) -> str:
    if row["status"] == "Following":
        return row["followup_stage"] or "New lead"
    if row["status"] == "Ordered":
        return row["install_status"] or "Ordered"
    if row["status"] == "Lost":
        return row["lost_reason"] or "Lost reason pending"
    return STATUS_LABELS.get(row["status"], row["status"])


def upsert_customer_from_quote(
    customer: dict[str, str],
    quote: dict[str, Any],
    first_followup: date,
    second_followup: date,
) -> int:
    existing = customer_by_id(quote.get("customer_id")) if quote.get("customer_id") else None
    if existing is None:
        existing = find_customer_by_contact(customer.get("email", ""), customer.get("phone", ""))
    notes = existing["notes"] if existing and existing["notes"] else ""
    quote_note = f"Quote {quote['quote_number']} created for {money(float(quote['total']))}."
    if quote.get("project_notes"):
        quote_note += f" Project notes: {quote['project_notes']}"
    if quote_note not in notes:
        notes = f"{notes}\n{quote_note}".strip()
    quoted_status = "Ordered" if existing and existing["status"] == "Ordered" else "Following"
    product_total = max(float(quote.get("subtotal") or 0) - float(quote.get("discount") or 0), 0.0)
    first_payment_due = product_total * 0.5
    second_payment_due = product_total * 0.5 + float(quote.get("tax") or 0) + float(quote.get("shipping_fee") or 0) + float(quote.get("installation_fee") or 0)
    existing_wishlist_for_quote = parse_wishlist(row_value(existing, "wishlist") if existing else None)
    quote_cart_wishlist = wishlist_from_cart()
    merged_quote_wishlist = append_wishlist_items(existing_wishlist_for_quote, quote_cart_wishlist) if existing else quote_cart_wishlist
    payload = {
        "status": quoted_status,
        "name": customer.get("name", "").strip(),
        "company": customer.get("company", "").strip(),
        "email": customer.get("email", "").strip(),
        "phone": format_us_phone(customer.get("phone", "")),
        "address": customer.get("address", "").strip(),
        "products_interest": ", ".join(dict.fromkeys(str(item.get("name", "")) for item in quote.get("items", []) if item.get("name"))),
        "client_type": row_value(existing, "client_type"),
        "client_type_note": row_value(existing, "client_type_note"),
        "project_type": row_value(existing, "project_type"),
        "project_type_note": row_value(existing, "project_type_note"),
        "use_case": row_value(existing, "use_case"),
        "use_case_note": row_value(existing, "use_case_note"),
        "area_zip": row_value(existing, "area_zip"),
        "area_zip_note": row_value(existing, "area_zip_note"),
        "showroom_status": row_value(existing, "showroom_status"),
        "showroom_note": row_value(existing, "showroom_note"),
        "answer_status": row_value(existing, "answer_status"),
        "answer_status_note": row_value(existing, "answer_status_note"),
        "source": row_value(existing, "source", "Quote form") or "Quote form",
        "initial_contact_date": row_value(existing, "initial_contact_date", today_iso()) or today_iso(),
        "priority": row_value(existing, "priority", "Medium") or "Medium",
        "budget": float(quote.get("total") or 0),
        "assigned_to": row_value(existing, "assigned_to") or default_customer_owner(),
        "notes": notes,
        "first_followup_date": first_followup.isoformat(),
        "next_followup_date": second_followup.isoformat(),
        "followup_stage": "Quoted",
        "on_hold": 0,
        "order_date": row_value(existing, "order_date", today_iso()),
        "first_payment_date": row_value(existing, "first_payment_date", today_iso()),
        "first_payment_amount": float(existing["first_payment_amount"] or first_payment_due) if existing else first_payment_due,
        "first_payment_paid": int(row_value(existing, "first_payment_paid", 0) or 0),
        "second_payment_enabled": int(row_value(existing, "second_payment_enabled", 1 if second_payment_due > 0 else 0) or 0),
        "second_payment_date": row_value(existing, "second_payment_date", today_iso()),
        "second_payment_amount": float(existing["second_payment_amount"] or second_payment_due) if existing else second_payment_due,
        "second_payment_paid": int(row_value(existing, "second_payment_paid", 0) or 0),
        "install_followup_date": row_value(existing, "install_followup_date", today_iso()),
        "install_status": row_value(existing, "install_status"),
        "lost_date": row_value(existing, "lost_date", today_iso()),
        "lost_reason": row_value(existing, "lost_reason"),
        "lost_notes": row_value(existing, "lost_notes"),
        "wishlist": row_value(existing, "wishlist") if quoted_status == "Ordered" and row_value(existing, "wishlist") else json.dumps(merged_quote_wishlist, ensure_ascii=False),
    }
    customer_id = save_customer(int(existing["id"]) if existing else None, payload)
    add_customer_timeline_event(customer_id, date.today(), "Quote created", quote_note, quote["quote_number"])
    if quoted_status == "Following":
        add_customer_timeline_event(customer_id, date.today(), "Progress updated", "Customer progress set to Quoted.", quote["quote_number"])
    add_customer_timeline_event(customer_id, first_followup, "First follow-up", "Initial follow-up after quote.", quote["quote_number"])
    add_customer_timeline_event(customer_id, second_followup, "Second follow-up", "Second follow-up reminder.", quote["quote_number"])
    return customer_id


def customer_editor(existing: sqlite3.Row | None = None, form_key: str = "customer-editor") -> None:
    is_edit = existing is not None
    default_status = existing["status"] if is_edit else "Following"
    with st.form(form_key):
        st.markdown("### Edit customer" if is_edit else "### Add customer")
        status = st.segmented_control(
            "Customer status",
            options=list(STATUS_LABELS),
            format_func=lambda option: STATUS_LABELS[option],
            default=default_status,
            key=f"{form_key}-status",
        ) or default_status
        identity1, identity2 = st.columns(2)
        with identity1:
            name = st.text_input("Customer name *", value=existing["name"] if is_edit else "")
            company = st.text_input("Company", value=existing["company"] if is_edit else "")
            email = st.text_input("Email", value=existing["email"] if is_edit else "")
            phone = st.text_input("Phone", value=format_us_phone(existing["phone"]) if is_edit else "", placeholder="(123) 456-7890", help="Enter a 10-digit US phone number. It will be saved as (123) 456-7890.")
        with identity2:
            priority = st.selectbox(
                "Priority",
                options=list(PRIORITY_LABELS),
                index=list(PRIORITY_LABELS).index(existing["priority"] if is_edit and existing["priority"] in PRIORITY_LABELS else "Medium"),
                format_func=lambda option: PRIORITY_LABELS[option],
            )
            source_options = customer_source_options(row_value(existing, "source"))
            source = st.selectbox(
                "Lead source",
                source_options,
                index=option_index(source_options, row_value(existing, "source")),
                format_func=lambda value: value or "Not set",
            )
            initial_contact_date = st.date_input(
                "First inquiry date",
                value=date_from_iso(existing["initial_contact_date"] if is_edit and "initial_contact_date" in existing.keys() else None, date.today()),
            )
            next_followup_date = st.date_input(
                "Next follow-up date",
                value=date_from_iso(existing["next_followup_date"] if is_edit else None, date.today() + timedelta(days=7)),
            )
            budget = st.number_input("Estimated budget", min_value=0.0, value=float(existing["budget"] or 0) if is_edit else 0.0, step=100.0)
            if is_manager_user():
                owner_default = row_value(existing, "assigned_to") if is_edit else default_customer_owner()
                owner_options = customer_owner_options(owner_default)
                owner_key = f"{form_key}-assigned-to"
                owner_mode = f"edit-{row_value(existing, 'id')}" if is_edit else f"new-{default_customer_owner()}"
                if st.session_state.get(f"{owner_key}-mode") != owner_mode:
                    st.session_state[owner_key] = owner_default if owner_default in owner_options else owner_options[0]
                    st.session_state[f"{owner_key}-mode"] = owner_mode
                assigned_to = st.selectbox(
                    "Owner / sales rep",
                    owner_options,
                    index=option_index(owner_options, st.session_state.get(owner_key) or owner_default),
                    key=owner_key,
                )
            else:
                assigned_to = current_employee_name()
                st.text_input("Owner / sales rep", value=assigned_to, disabled=True)
        address = st.text_area("Address", value=existing["address"] if is_edit else "", height=80)
        products_interest = st.text_area(
            "Interested products",
            value=existing["products_interest"] if is_edit else "",
            placeholder="Sliding door, casement window, black frame, Low-E glass...",
            height=80,
        )
        empty_label = "Not set"
        client_type_options = ("", *CLIENT_TYPES)
        project_type_options = ("", *PROJECT_TYPES)
        type1, type2 = st.columns(2)
        with type1:
            client_type = st.selectbox(
                "Client type",
                client_type_options,
                index=option_index(client_type_options, row_value(existing, "client_type")),
                format_func=lambda value: value or empty_label,
            )
        with type2:
            project_type = st.selectbox(
                "Project type",
                project_type_options,
                index=option_index(project_type_options, row_value(existing, "project_type")),
                format_func=lambda value: value or empty_label,
            )
        client_type_note = row_value(existing, "client_type_note")
        project_type_note = row_value(existing, "project_type_note")
        use_case = row_value(existing, "use_case")
        use_case_note = row_value(existing, "use_case_note")
        area_zip = row_value(existing, "area_zip")
        area_zip_note = row_value(existing, "area_zip_note")
        showroom_status = row_value(existing, "showroom_status")
        showroom_note = row_value(existing, "showroom_note")
        answer_status = row_value(existing, "answer_status")
        answer_status_note = row_value(existing, "answer_status_note")
        st.markdown("#### Customer cart / Wishlist")
        existing_wishlist = parse_wishlist(existing["wishlist"] if is_edit else None)
        use_cart_wishlist = False
        selected_products: list[str] = []
        st.caption("Wishlist is now a read-only view of this customer's saved cart. To change products, open the customer's cart and edit there.")
        if existing_wishlist:
            st.caption(f"Saved cart / wishlist: {len(existing_wishlist)} item(s).")

        if status == "Following":
            st.markdown("#### Follow-up")
            follow1, follow2 = st.columns(2)
            with follow1:
                first_followup_date = st.date_input(
                    "First follow-up",
                    value=date_from_iso(existing["first_followup_date"] if is_edit else None, date.today()),
                )
            with follow2:
                followup_stage = st.selectbox(
                    "Stage",
                    FOLLOWUP_STAGES,
                    index=FOLLOWUP_STAGES.index(existing["followup_stage"]) if is_edit and existing["followup_stage"] in FOLLOWUP_STAGES else 0,
                )
            on_hold = st.checkbox("On hold", value=bool(existing["on_hold"]) if is_edit else False)
        else:
            first_followup_date = date_from_iso(existing["first_followup_date"] if is_edit else None, date.today())
            followup_stage = existing["followup_stage"] if is_edit else ""
            on_hold = bool(existing["on_hold"]) if is_edit else False

        if status == "Ordered":
            st.markdown("#### Order and payment")
            order1, order2, order3 = st.columns(3)
            with order1:
                order_date = st.date_input("Order date", value=date_from_iso(existing["order_date"] if is_edit else None, date.today()))
                first_payment_date = st.date_input("First payment date", value=date_from_iso(existing["first_payment_date"] if is_edit else None, date.today()))
                first_payment_paid = st.checkbox("First payment paid", value=bool(int(row_value(existing, "first_payment_paid", 0) or 0)) if is_edit else False)
            with order2:
                first_payment_amount = st.number_input("First payment amount", min_value=0.0, value=float(existing["first_payment_amount"] or 0) if is_edit else 0.0, step=100.0)
                second_payment_enabled = st.checkbox(
                    "Use second payment",
                    value=bool(int(row_value(existing, "second_payment_enabled", 1) or 0)) if is_edit else True,
                )
                if second_payment_enabled:
                    second_payment_date = st.date_input("Second payment date", value=date_from_iso(existing["second_payment_date"] if is_edit else None, date.today() + timedelta(days=14)))
                else:
                    second_payment_date = date.today()
            with order3:
                if second_payment_enabled:
                    second_payment_amount = st.number_input("Second payment amount", min_value=0.0, value=float(existing["second_payment_amount"] or 0) if is_edit else 0.0, step=100.0)
                    second_payment_paid = st.checkbox("Second payment paid", value=bool(int(row_value(existing, "second_payment_paid", 0) or 0)) if is_edit else False)
                else:
                    second_payment_amount = float(existing["second_payment_amount"] or 0) if is_edit else 0.0
                    second_payment_paid = bool(int(row_value(existing, "second_payment_paid", 0) or 0)) if is_edit else False
                install_followup_date = st.date_input("Installation follow-up", value=date_from_iso(existing["install_followup_date"] if is_edit else None, date.today() + timedelta(days=30)))
            install_status = st.selectbox(
                "Installation status",
                INSTALL_STATUSES,
                index=INSTALL_STATUSES.index(existing["install_status"]) if is_edit and existing["install_status"] in INSTALL_STATUSES else 0,
            )
        else:
            order_date = date_from_iso(existing["order_date"] if is_edit else None, date.today())
            first_payment_date = date_from_iso(existing["first_payment_date"] if is_edit else None, date.today())
            first_payment_amount = float(existing["first_payment_amount"] or 0) if is_edit else 0.0
            first_payment_paid = bool(int(row_value(existing, "first_payment_paid", 0) or 0)) if is_edit else False
            second_payment_enabled = bool(int(row_value(existing, "second_payment_enabled", 1) or 0)) if is_edit else True
            second_payment_date = date_from_iso(existing["second_payment_date"] if is_edit else None, date.today())
            second_payment_amount = float(existing["second_payment_amount"] or 0) if is_edit else 0.0
            second_payment_paid = bool(int(row_value(existing, "second_payment_paid", 0) or 0)) if is_edit else False
            install_followup_date = date_from_iso(existing["install_followup_date"] if is_edit else None, date.today())
            install_status = existing["install_status"] if is_edit else ""

        if status == "Lost":
            st.markdown("#### Lost reason")
            lost1, lost2 = st.columns([1, 2])
            with lost1:
                lost_date = st.date_input("Lost date", value=date_from_iso(existing["lost_date"] if is_edit else None, date.today()))
            with lost2:
                lost_reason = st.selectbox(
                    "Reason",
                    LOST_REASONS,
                    index=LOST_REASONS.index(existing["lost_reason"]) if is_edit and existing["lost_reason"] in LOST_REASONS else 0,
                )
            lost_notes = st.text_area("Lost notes", value=existing["lost_notes"] if is_edit else "", height=80)
        else:
            lost_date = date_from_iso(existing["lost_date"] if is_edit else None, date.today())
            lost_reason = existing["lost_reason"] if is_edit else ""
            lost_notes = existing["lost_notes"] if is_edit else ""

        notes = st.text_area("Internal notes", value=existing["notes"] if is_edit else "", height=110)
        submitted = st.form_submit_button("Save customer", type="primary", width="stretch")
        if submitted:
            if not name.strip():
                st.error("Customer name is required.")
                return
            if selected_products and not (is_edit and existing["status"] == "Ordered"):
                wishlist_to_save = wishlist_from_products(selected_products)
            else:
                wishlist_to_save = existing_wishlist
            inventory_messages: list[str] = []
            if status == "Ordered" and (not is_edit or existing["status"] != "Ordered") and wishlist_to_save:
                wishlist_to_save, inventory_messages = deduct_inventory_for_order_items(wishlist_to_save)
                if production_required_items(wishlist_to_save):
                    install_followup_date = order_date + timedelta(days=70)
            payload = {
                "status": status,
                "name": name.strip(),
                "company": company.strip(),
                "email": email.strip(),
                "phone": format_us_phone(phone),
                "address": address.strip(),
                "products_interest": products_interest.strip(),
                "client_type": client_type,
                "client_type_note": client_type_note.strip(),
                "project_type": project_type,
                "project_type_note": project_type_note.strip(),
                "use_case": use_case,
                "use_case_note": use_case_note.strip(),
                "area_zip": area_zip.strip(),
                "area_zip_note": area_zip_note.strip(),
                "showroom_status": showroom_status,
                "showroom_note": showroom_note.strip(),
                "answer_status": answer_status,
                "answer_status_note": answer_status_note.strip(),
                "source": source.strip(),
                "initial_contact_date": initial_contact_date.isoformat(),
                "priority": priority,
                "budget": float(budget),
                "assigned_to": assigned_to.strip(),
                "notes": notes.strip(),
                "first_followup_date": first_followup_date.isoformat(),
                "next_followup_date": next_followup_date.isoformat(),
                "followup_stage": followup_stage,
                "on_hold": int(on_hold),
                "order_date": order_date.isoformat(),
                "first_payment_date": first_payment_date.isoformat(),
                "first_payment_amount": float(first_payment_amount),
                "first_payment_paid": int(first_payment_paid),
                "second_payment_enabled": int(second_payment_enabled),
                "second_payment_date": second_payment_date.isoformat() if second_payment_enabled else (str(row_value(existing, "second_payment_date", "")) if is_edit else ""),
                "second_payment_amount": float(second_payment_amount) if second_payment_enabled or is_edit else 0.0,
                "second_payment_paid": int(second_payment_paid) if second_payment_enabled or is_edit else 0,
                "install_followup_date": install_followup_date.isoformat(),
                "install_status": install_status,
                "lost_date": lost_date.isoformat(),
                "lost_reason": lost_reason,
                "lost_notes": lost_notes.strip(),
                "wishlist": json.dumps(wishlist_to_save, ensure_ascii=False),
            }
            saved_id = save_customer(existing["id"] if is_edit else None, payload)
            if inventory_messages:
                add_customer_timeline_event(
                    int(saved_id),
                    date.today(),
                    "Inventory updated",
                    " ".join(inventory_messages),
                )
            st.session_state.customer_editor_id = saved_id
            st.session_state.wishlist_draft = []
            if not is_edit:
                owner_key = f"{form_key}-assigned-to"
                st.session_state.pop(owner_key, None)
                st.session_state.pop(f"{owner_key}-mode", None)
            st.success(f"{name.strip()} saved.")
            st.rerun()


def customer_summary_metrics(rows: list[sqlite3.Row]) -> None:
    following = [row for row in rows if row["status"] == "Following"]
    ordered = [row for row in rows if row["status"] == "Ordered"]
    lost = [row for row in rows if row["status"] == "Lost"]
    due_followups = [
        row for row in rows
        if row["status"] != "Lost" and not row["on_hold"]
        and row["next_followup_date"] and date_from_iso(row["next_followup_date"]) <= date.today()
    ]
    install_due = [
        row for row in ordered
        if row["install_followup_date"] and date_from_iso(row["install_followup_date"]) <= date.today()
        and row["install_status"] != "Installed"
    ]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Following", len(following))
    c2.metric("Ordered", len(ordered))
    c3.metric("Lost", len(lost))
    c4.metric("Follow-ups due today or overdue", len(due_followups))
    c5.metric("Installation reminders", len(install_due))


def render_customer_basic_info(row: sqlite3.Row, priority_color: str) -> None:
    st.markdown("### Customer information")
    basic1, basic2, basic3 = st.columns(3)
    with basic1:
        st.markdown(f"**Name:** {row['name'] or 'Not set'}")
        st.markdown(f"**Email:** {row['email'] or 'Not set'}")
    with basic2:
        st.markdown(f"**Phone:** {row['phone'] or 'Not set'}")
        st.markdown(f"**Client type:** {row_value(row, 'client_type') or 'Not set'}")
    with basic3:
        st.markdown(f"**Company:** {row['company'] or 'Not set'}")
        st.markdown(f"**Address:** {row['address'] or 'Not set'}")

    st.markdown("### Project information")
    project1, project2, project3 = st.columns(3)
    with project1:
        st.markdown(f"**Project type:** {row_value(row, 'project_type') or 'Not set'}")
        st.markdown(f"**Source:** {row['source'] or 'Not set'}")
    with project2:
        st.markdown(f"**First inquiry:** {display_date(row['initial_contact_date'])}")
        st.markdown(f"**Next follow-up:** {display_date(row['next_followup_date'])}")
    with project3:
        st.markdown(f"<b>Priority:</b> <span style='color:{priority_color}'>{row['priority'] or 'Medium'}</span>", unsafe_allow_html=True)
        st.markdown(f"**Budget:** {money(float(row['budget'])) if row['budget'] else 'Not set'}")
        st.markdown(f"**Owner:** {row['assigned_to'] or 'Not set'}")


def render_customer_basic_info_editor(row: sqlite3.Row) -> None:
    empty_label = "Not set"
    with st.form(f"customer-basic-editor-{row['id']}"):
        st.markdown("### Customer information")
        basic1, basic2, basic3 = st.columns(3)
        with basic1:
            name = st.text_input("Customer name *", value=row["name"] or "")
            email = st.text_input("Email", value=row["email"] or "")
        with basic2:
            phone = st.text_input("Phone", value=format_us_phone(row["phone"]) or "", placeholder="(123) 456-7890", help="Enter a 10-digit US phone number. It will be saved as (123) 456-7890.")
            client_type_options = ("", *CLIENT_TYPES)
            client_type = st.selectbox(
                "Client type",
                client_type_options,
                index=option_index(client_type_options, row_value(row, "client_type")),
                format_func=lambda value: value or empty_label,
            )
        with basic3:
            company = st.text_input("Company", value=row["company"] or "")
            address = st.text_area("Address", value=row["address"] or "", height=78)

        st.markdown("### Project information")
        project1, project2, project3 = st.columns(3)
        with project1:
            project_type_options = ("", *PROJECT_TYPES)
            project_type = st.selectbox(
                "Project type",
                project_type_options,
                index=option_index(project_type_options, row_value(row, "project_type")),
                format_func=lambda value: value or empty_label,
            )
            source_options = customer_source_options(row["source"])
            source = st.selectbox(
                "Source",
                source_options,
                index=option_index(source_options, row["source"]),
                format_func=lambda value: value or empty_label,
            )
        with project2:
            first_inquiry = st.date_input(
                "First inquiry date",
                value=date_from_iso(row["initial_contact_date"], date.today()),
            )
            next_followup = st.date_input(
                "Next follow-up date",
                value=date_from_iso(row["next_followup_date"], date.today() + timedelta(days=7)),
            )
        with project3:
            priority = st.selectbox(
                "Priority",
                options=list(PRIORITY_LABELS),
                index=list(PRIORITY_LABELS).index(row["priority"] if row["priority"] in PRIORITY_LABELS else "Medium"),
                format_func=lambda option: PRIORITY_LABELS[option],
            )
            budget = st.number_input("Budget", min_value=0.0, value=float(row["budget"] or 0), step=100.0)
            if is_manager_user():
                owner_options = customer_owner_options(row["assigned_to"])
                assigned_to = st.selectbox(
                    "Owner",
                    owner_options,
                    index=option_index(owner_options, row["assigned_to"] or default_customer_owner()),
                )
            else:
                assigned_to = current_employee_name()
                st.text_input("Owner", value=assigned_to, disabled=True)

        save_col, cancel_col = st.columns([1, 1])
        with save_col:
            save = st.form_submit_button("Save customer information", type="primary", width="stretch")
        with cancel_col:
            cancel = st.form_submit_button("Cancel", width="stretch")

        if cancel:
            st.session_state.inline_customer_editor_id = None
            st.rerun()
        if save:
            if not name.strip():
                st.error("Customer name is required.")
                return
            update_customer_basic_info(
                int(row["id"]),
                {
                    "name": name.strip(),
                    "email": email.strip(),
                    "phone": format_us_phone(phone),
                    "company": company.strip(),
                    "address": address.strip(),
                    "source": source.strip(),
                    "initial_contact_date": first_inquiry.isoformat(),
                    "next_followup_date": next_followup.isoformat(),
                    "priority": priority,
                    "client_type": client_type,
                    "project_type": project_type,
                    "budget": float(budget),
                    "assigned_to": assigned_to.strip(),
                },
            )
            st.session_state.inline_customer_editor_id = None
            st.success("Customer information saved.")
            st.rerun()


def customer_card(row: sqlite3.Row) -> None:
    priority_color = {"High": "#b42318", "Medium": "#9a6700", "Low": "#2e6b45"}.get(row["priority"], "#68736d")
    city_label = customer_city_label(row)
    city_title = f" ｜ {city_label}" if city_label else ""
    owner_title = f" ｜ {row_value(row, 'assigned_to') or 'Unassigned'}" if is_manager_user() else ""
    title = f"{row['name']}{city_title} ｜ {customer_title_detail(row)}{owner_title}"
    is_inline_editing = st.session_state.get("inline_customer_editor_id") == int(row["id"])
    with st.expander(title, expanded=is_inline_editing):
        if is_manager_user():
            owner_options = customer_owner_options(row_value(row, "assigned_to"))
            owner_col, assign_col, save_owner_col = st.columns([1.1, 1.2, 0.7], vertical_alignment="bottom")
            with owner_col:
                st.markdown(f"**Sales rep:** {row_value(row, 'assigned_to') or 'Unassigned'}")
            with assign_col:
                selected_owner = st.selectbox(
                    "Assign sales rep",
                    owner_options,
                    index=option_index(owner_options, row_value(row, "assigned_to") or default_customer_owner()),
                    key=f"assign-owner-{row['id']}",
                )
            with save_owner_col:
                if st.button(
                    "Save owner",
                    key=f"save-owner-{row['id']}",
                    disabled=selected_owner == (row_value(row, "assigned_to") or ""),
                    width="stretch",
                ):
                    update_customer_owner(int(row["id"]), selected_owner, row_value(row, "assigned_to"))
                    st.success(f"Customer assigned to {selected_owner}.")
                    st.rerun()
            st.divider()

        if is_inline_editing:
            render_customer_basic_info_editor(row)
        else:
            render_customer_basic_info(row, priority_color)

        st.markdown("**Quick status update**")
        status_options = list(STATUS_LABELS)
        status_key = f"quick-status-{row['id']}"
        status_row_key = f"{status_key}-row-status"
        if status_key not in st.session_state or st.session_state.get(status_row_key) != row["status"]:
            st.session_state[status_key] = row["status"]
            st.session_state[status_row_key] = row["status"]
        current_status_value = st.session_state.get(status_key, row["status"])
        quick1, quick2, quick3 = st.columns([1, 1.4, 1])
        with quick1:
            selected_status = st.selectbox(
                "Status",
                status_options,
                index=status_options.index(current_status_value) if current_status_value in status_options else 0,
                format_func=lambda value: STATUS_LABELS[value],
                key=status_key,
            )
        quick_followup_stage = row["followup_stage"] or "Waiting for customer reply"
        quick_next_followup = date_from_iso(row["next_followup_date"], date.today() + timedelta(days=7))
        quick_lost_reason = row["lost_reason"] if row["lost_reason"] in LOST_REASONS else LOST_REASONS[0]
        quick_lost_notes = row["lost_notes"] or ""
        quick_order_date = date_from_iso(row["order_date"], date.today())
        with quick2:
            if selected_status == "Following":
                quick_followup_stage = st.selectbox(
                    "Stage",
                    FOLLOWUP_STAGES,
                    index=FOLLOWUP_STAGES.index(quick_followup_stage) if quick_followup_stage in FOLLOWUP_STAGES else 0,
                    key=f"quick-stage-{row['id']}",
                )
                quick_next_followup = st.date_input("Next follow-up", value=quick_next_followup, key=f"quick-next-{row['id']}")
            elif selected_status == "Lost":
                quick_lost_reason = st.selectbox(
                    "Lost reason",
                    LOST_REASONS,
                    index=LOST_REASONS.index(quick_lost_reason),
                    key=f"quick-lost-reason-{row['id']}",
                )
                quick_lost_notes = st.text_input("Lost notes", value=quick_lost_notes, key=f"quick-lost-notes-{row['id']}")
            elif selected_status == "Ordered":
                quick_order_date = st.date_input("Order date", value=quick_order_date, key=f"quick-order-date-{row['id']}")
        with quick3:
            st.write("")
            st.write("")
            if st.button("Update status", key=f"quick-save-status-{row['id']}", width="stretch"):
                update_customer_status(
                    int(row["id"]),
                    selected_status,
                    followup_stage=quick_followup_stage,
                    next_followup_date=quick_next_followup,
                    lost_reason=quick_lost_reason,
                    lost_notes=quick_lost_notes,
                    order_date=quick_order_date,
                )
                st.success("Customer status updated.")
                st.rerun()

        wishlist = parse_wishlist(row["wishlist"])
        order_summary = order_summary_from_quote(
            latest_customer_quote(int(row["id"])) if row["status"] == "Ordered" else None,
            wishlist,
        )
        if wishlist:
            render_wishlist(
                wishlist,
                title="Ordered products" if row["status"] == "Ordered" else "Wishlist",
            )

        if row["status"] == "Following":
            if row["on_hold"]:
                st.info("This customer is on hold.")
            else:
                label, color = due_label(row["next_followup_date"])
                st.progress(followup_progress(row), text=f"First: {display_date(row['first_followup_date'])} · Next: {display_date(row['next_followup_date'])} · {label}")
                st.markdown(f"<span style='color:{color};font-weight:700'>{label}</span>", unsafe_allow_html=True)
            st.write(f"**Stage:** {row['followup_stage'] or 'Not set'}")
        elif row["status"] == "Ordered":
            render_order_summary(order_summary)
            st.write(f"**Order date:** {display_date(row['order_date'])}")
            payment_schedule = render_payment_receipt(row, float(order_summary["total"]))
            render_payment_schedule_editor(row, float(order_summary["total"]))
            receipt_pdf = build_receipt_pdf(
                row,
                order_summary,
                float(payment_schedule["first_amount"]),
                float(payment_schedule["second_amount"]),
                wishlist,
            )
            st.download_button(
                "Download receipt PDF",
                receipt_pdf,
                file_name=f"{order_summary.get('quote_number') or 'order'}-receipt.pdf",
                mime="application/pdf",
                key=f"receipt-pdf-{row['id']}",
                width="stretch",
            )
            factory_items = production_required_items(wishlist)
            if factory_items:
                factory_pdf = build_factory_production_pdf(row, factory_items, date_from_iso(row["order_date"], date.today()))
                st.info("Some ordered products are not in stock. A factory production PDF is ready to send.")
                st.download_button(
                    "Download factory production PDF",
                    factory_pdf,
                    file_name=f"factory-production-{row['id']}-{date_from_iso(row['order_date'], date.today()).strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    key=f"factory-pdf-{row['id']}",
                    width="stretch",
                )
            install_label, install_color = due_label(row["install_followup_date"])
            st.markdown(
                f"**Installation:** {row['install_status'] or 'Not set'} · "
                f"<span style='color:{install_color};font-weight:700'>{install_label}</span> · "
                f"{display_date(row['install_followup_date'])}",
                unsafe_allow_html=True,
            )
        else:
            st.write(f"**Lost date:** {display_date(row['lost_date'])}")
            st.write(f"**Reason:** {row['lost_reason'] or 'Not set'}")
            if row["lost_notes"]:
                st.caption(row["lost_notes"])

        if row["notes"]:
            st.markdown("**Internal notes**")
            st.write(row["notes"])
        timeline_rows = customer_timeline(int(row["id"]))
        if timeline_rows:
            st.markdown("**Follow-up timeline**")
            for event in timeline_rows:
                line = f"{display_date(event['event_date'])} · **{event['title']}**"
                if event["quote_number"]:
                    line += f" · {event['quote_number']}"
                st.markdown(line)
                if event["notes"]:
                    st.caption(event["notes"])
        saved_quotes = customer_quotes(int(row["id"]))
        if saved_quotes:
            st.markdown("**Saved quotes**")
            for quote_row in saved_quotes:
                quote_line = f"{quote_row['quote_number']} · {money(float(quote_row['total']))} · {display_date(str(quote_row['created_at'])[:10])}"
                quote_path = OUTPUT_DIR / f"{quote_row['quote_number']}.pdf"
                q1, q2 = st.columns([3, 1])
                with q1:
                    st.write(quote_line)
                with q2:
                    if quote_path.exists():
                        st.download_button(
                            "PDF",
                            quote_path.read_bytes(),
                            file_name=quote_path.name,
                            mime="application/pdf",
                            key=f"customer-quote-{row['id']}-{quote_row['quote_number']}",
                            width="stretch",
                        )
        action1, action2 = st.columns(2)
        with action1:
            if st.button("Work on this customer's cart", key=f"cart-customer-{row['id']}", width="stretch"):
                set_active_customer(int(row["id"]))
                st.session_state.page = "Cart"
                st.rerun()
        with action2:
            if st.button("Edit this customer", key=f"edit-customer-{row['id']}", width="stretch"):
                st.session_state.inline_customer_editor_id = int(row["id"])
                st.rerun()
        st.divider()
        confirm_delete = st.checkbox(
            f"I understand this will delete {row['name']} from customer management.",
            key=f"confirm-delete-customer-{row['id']}",
        )
        if st.button(
            "Delete this customer",
            key=f"delete-customer-{row['id']}",
            type="secondary",
            disabled=not confirm_delete,
            width="stretch",
        ):
            delete_customer(int(row["id"]))
            st.success(f"{row['name']} deleted.")
            st.rerun()


def customers_page() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="eyebrow">Customer CRM</div>
          <h1>Customer CRM</h1>
          <p>Track following, ordered, and lost customers with follow-up dates, payment milestones, installation reminders, and lost reasons.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if supabase_customers_enabled():
        st.caption("Customer database: Supabase connected. New customers and customer edits should be saved to the backend database.")
    else:
        st.warning("Customer database is not connected to Supabase. Customers created now will be saved locally only and will not appear in the Supabase backend.")
    search = st.text_input("Search customers", placeholder="Search name, email, phone, address or interested products...")
    rows = customer_rows(search=search.strip())
    customer_summary_metrics(rows)
    st.write("")

    overview_tab, following_tab, ordered_tab, lost_tab, edit_tab = st.tabs(
        ["Dashboard / Follow-ups", "Following", "Ordered", "Lost", "Add / Edit"]
    )
    with overview_tab:
        due_followups = [
            row for row in rows
            if row["status"] != "Lost" and not row["on_hold"] and row["next_followup_date"]
            and date_from_iso(row["next_followup_date"]) <= date.today()
        ]
        due_installs = [
            row for row in rows
            if row["status"] == "Ordered" and row["install_followup_date"]
            and date_from_iso(row["install_followup_date"]) <= date.today()
            and row["install_status"] != "Installed"
        ]
        if not rows:
            st.markdown('<div class="empty">No customers yet. Add your first customer from the Add / Edit tab.</div>', unsafe_allow_html=True)
        else:
            left, right = st.columns(2)
            with left:
                st.markdown("#### Follow-ups due today")
                if not due_followups:
                    st.success("No customers need follow-up today.")
                for row in due_followups:
                    label, color = due_label(row["next_followup_date"])
                    with st.container(border=True):
                        st.markdown(f"**{row['name']}** · {STATUS_LABELS.get(row['status'], row['status'])}")
                        st.markdown(
                            f"<span style='color:{color};font-weight:800'>{label}</span> · "
                            f"Next follow-up: {display_date(row['next_followup_date'])}",
                            unsafe_allow_html=True,
                        )
                        if is_manager_user():
                            st.write(f"**Sales rep:** {row['assigned_to'] or 'Unassigned'}")
                        st.write(f"**Contact:** {row['phone'] or row['email'] or 'No contact'}")
                        st.write(f"**Stage:** {row['followup_stage'] or 'Not set'}")
            with right:
                st.markdown("#### Installation reminders")
                if not due_installs:
                    st.success("No installation reminders due today.")
                for row in due_installs:
                    label, _ = due_label(row["install_followup_date"])
                    owner_suffix = f" · Sales rep: {row['assigned_to'] or 'Unassigned'}" if is_manager_user() else ""
                    st.write(f"**{row['name']}** · {label} · {row['install_status'] or 'Not set'}{owner_suffix}")
    with following_tab:
        following = [row for row in rows if row["status"] == "Following"]
        if not following:
            st.markdown('<div class="empty">No following customers found.</div>', unsafe_allow_html=True)
        for row in following:
            customer_card(row)
    with ordered_tab:
        ordered = [row for row in rows if row["status"] == "Ordered"]
        if not ordered:
            st.markdown('<div class="empty">No ordered customers found.</div>', unsafe_allow_html=True)
        for row in ordered:
            customer_card(row)
    with lost_tab:
        lost = [row for row in rows if row["status"] == "Lost"]
        if not lost:
            st.markdown('<div class="empty">No lost customers found.</div>', unsafe_allow_html=True)
        for row in lost:
            customer_card(row)
    with edit_tab:
        if st.session_state.get("inline_customer_editor_id"):
            st.info("A customer editor is open inside the customer card. Close it there to use this Add / Edit tab.")
            return
        all_rows = customer_rows()
        edit_options = [0] + [int(row["id"]) for row in all_rows]
        selected_id = st.selectbox(
            "Choose customer to edit",
            edit_options,
            index=edit_options.index(st.session_state.customer_editor_id) if st.session_state.customer_editor_id in edit_options else 0,
            format_func=lambda value: "Add new customer" if value == 0 else next(row["name"] for row in all_rows if row["id"] == value),
        )
        st.session_state.customer_editor_id = selected_id or None
        customer_editor(customer_by_id(selected_id) if selected_id else None, form_key="customer-editor-tab")


def finance_page() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="eyebrow">Finance dashboard</div>
          <h1>Company Financial Overview</h1>
          <p>Review sales, salesperson contribution, expected second-payment collections, paid cash, and open receivables for monthly, quarterly, and yearly finance handoff.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    records = finance_order_records()
    if not records:
        st.markdown('<div class="empty">No ordered customers yet. Orders will appear here after customers are moved to Ordered.</div>', unsafe_allow_html=True)
        return

    filter_left, filter_mid, filter_right = st.columns([1, 1, 1.2])
    with filter_left:
        period = st.selectbox("Finance period", ("Month", "Quarter", "Year"), index=0)
    with filter_mid:
        anchor = st.date_input("Period includes", value=date.today())
    with filter_right:
        if is_manager_user():
            sales_options = ["All sales", *sorted({str(record["sales"]) for record in records})]
            salesperson = st.selectbox("Salesperson filter", sales_options)
        else:
            salesperson = current_employee_name() or "My sales"
            st.text_input("Salesperson", value=salesperson, disabled=True)

    start, end = period_bounds(period, anchor)
    filtered = [
        record for record in records
        if salesperson == "All sales" or str(record["sales"]).strip().lower() == salesperson.strip().lower()
    ]
    period_orders = [
        record for record in filtered
        if in_date_range(record["order_date"], start, end)
    ]
    expected_second = [
        record for record in filtered
        if record["second_payment_enabled"]
        and not record["second_payment_paid"]
        and in_date_range(record["second_payment_date"], start, end)
    ]
    overdue_payments = [
        record for record in filtered
        if (
            (not record["first_payment_paid"] and record["first_payment_amount"] > 0 and record["first_payment_date"] and date_from_iso(record["first_payment_date"]) < date.today())
            or (
                record["second_payment_enabled"]
                and not record["second_payment_paid"]
                and record["second_payment_amount"] > 0
                and record["second_payment_date"]
                and date_from_iso(record["second_payment_date"]) < date.today()
            )
        )
    ]

    sales_amount = sum(float(record["order_total"]) for record in period_orders)
    collected_amount = sum(payment_amount_in_period(record, start, end) for record in filtered)
    expected_second_amount = sum(float(record["second_payment_amount"]) for record in expected_second)
    open_balance = sum(float(record["balance"]) for record in filtered)

    st.caption(f"Showing {display_date(start.isoformat())} to {display_date(end.isoformat())}. Sales are based on Ordered customers by order date. Expected second payment includes unpaid second payments due in the selected period.")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Sales amount", money(sales_amount), f"{len(period_orders)} orders")
    kpi2.metric("Collected in period", money(collected_amount))
    kpi3.metric("Expected second payment", money(expected_second_amount), f"{len(expected_second)} customers")
    kpi4.metric("Open A/R balance", money(open_balance), f"{len(overdue_payments)} overdue")

    contribution: dict[str, dict[str, float | int]] = {}
    for record in period_orders:
        sales_name = str(record["sales"])
        if sales_name not in contribution:
            contribution[sales_name] = {"orders": 0, "sales": 0.0, "collected": 0.0, "balance": 0.0}
        contribution[sales_name]["orders"] = int(contribution[sales_name]["orders"]) + 1
        contribution[sales_name]["sales"] = float(contribution[sales_name]["sales"]) + float(record["order_total"])
        contribution[sales_name]["collected"] = float(contribution[sales_name]["collected"]) + payment_amount_in_period(record, start, end)
        contribution[sales_name]["balance"] = float(contribution[sales_name]["balance"]) + float(record["balance"])

    contribution_rows = [
        {
            "Salesperson": sales_name,
            "Orders": values["orders"],
            "Sales amount": money(float(values["sales"])),
            "Collected in period": money(float(values["collected"])),
            "Open balance": money(float(values["balance"])),
            "Share": f"{(float(values['sales']) / sales_amount * 100):.1f}%" if sales_amount else "0.0%",
        }
        for sales_name, values in sorted(contribution.items(), key=lambda item: float(item[1]["sales"]), reverse=True)
    ]

    sales_tab, second_tab, ar_tab, export_tab = st.tabs(["Sales contribution", "Second-payment forecast", "Receivables", "Export"])
    with sales_tab:
        if not contribution_rows:
            st.markdown('<div class="empty">No orders in this period.</div>', unsafe_allow_html=True)
        else:
            st.dataframe(contribution_rows, hide_index=True, width="stretch")
            max_sales = max(float(values["sales"]) for values in contribution.values()) or 1.0
            for row in contribution_rows:
                raw_value = float(contribution[str(row["Salesperson"])]["sales"])
                width = max(6, int(raw_value / max_sales * 100))
                st.markdown(
                    f"""
                    <div style="margin:10px 0">
                      <div style="display:flex;justify-content:space-between;font-size:13px;font-weight:800">
                        <span>{html.escape(str(row["Salesperson"]))}</span><span>{row["Sales amount"]}</span>
                      </div>
                      <div style="height:10px;background:#e2e8e3;border-radius:999px;overflow:hidden">
                        <div style="height:10px;width:{width}%;background:#23342c"></div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown("#### Order details in this period")
            period_detail_rows = [
                {
                    "Customer": record["customer"],
                    "Salesperson": record["sales"],
                    "Order date": display_date(record["order_date"]),
                    "Order total": money(float(record["order_total"])),
                    "Collected in period": money(payment_amount_in_period(record, start, end)),
                    "Paid total": money(float(record["paid_total"])),
                    "Open balance": money(float(record["balance"])),
                    "Customer ID": record["customer_id"],
                }
                for record in sorted(period_orders, key=lambda item: (item["order_date"] or "", item["customer"]), reverse=True)
            ]
            if period_detail_rows:
                st.dataframe(period_detail_rows, hide_index=True, width="stretch")
            else:
                st.markdown('<div class="empty">No order detail rows for this period.</div>', unsafe_allow_html=True)

    with second_tab:
        forecast_rows = [
            {
                "Due date": display_date(record["second_payment_date"]),
                "Customer": record["customer"],
                "Sales": record["sales"],
                "Expected second payment": money(float(record["second_payment_amount"])),
                "Order total": money(float(record["order_total"])),
                "Balance": money(float(record["balance"])),
            }
            for record in sorted(expected_second, key=lambda item: item["second_payment_date"] or "")
        ]
        if forecast_rows:
            st.dataframe(forecast_rows, hide_index=True, width="stretch")
        else:
            st.markdown('<div class="empty">No unpaid second payments due in this period.</div>', unsafe_allow_html=True)

    with ar_tab:
        receivable_rows = [
            {
                "Customer": record["customer"],
                "Sales": record["sales"],
                "Order date": display_date(record["order_date"]),
                "Order total": money(float(record["order_total"])),
                "Paid": money(float(record["paid_total"])),
                "Balance": money(float(record["balance"])),
                "Next due": display_date(record["second_payment_date"] if record["second_payment_enabled"] and not record["second_payment_paid"] else record["first_payment_date"]),
            }
            for record in sorted(filtered, key=lambda item: float(item["balance"]), reverse=True)
            if float(record["balance"]) > 0
        ]
        if receivable_rows:
            st.dataframe(receivable_rows, hide_index=True, width="stretch")
        else:
            st.success("No open receivable balance for the current filter.")

    with export_tab:
        detail_rows = [
            {
                "Customer": record["customer"],
                "Company": record["company"],
                "Sales": record["sales"],
                "Order date": display_date(record["order_date"]),
                "Quote": record["quote_number"] or "Customer record",
                "Order total": money(float(record["order_total"])),
                "Paid total": money(float(record["paid_total"])),
                "Balance": money(float(record["balance"])),
                "First paid": "Yes" if record["first_payment_paid"] else "No",
                "Second due": display_date(record["second_payment_date"]),
                "Second amount": money(float(record["second_payment_amount"])),
                "Second paid": "Yes" if record["second_payment_paid"] else "No",
            }
            for record in sorted(filtered, key=lambda item: item["order_date"] or "", reverse=True)
        ]
        st.dataframe(detail_rows, hide_index=True, width="stretch")
        st.download_button(
            "Download finance CSV",
            data=finance_csv(filtered),
            file_name=f"finance-dashboard-{start.isoformat()}-{end.isoformat()}.csv",
            mime="text/csv",
            width="stretch",
        )


def product_choice_label(choice: dict[str, Any]) -> str:
    snapshot = choice.get("snapshot", {})
    details = []
    if snapshot.get("width") and snapshot.get("height"):
        details.append(f"{float(snapshot['width']):.1f}\" W x {float(snapshot['height']):.1f}\" H")
    for key in ("color", "glass", "frame", "direction"):
        if snapshot.get(key):
            details.append(str(snapshot[key]))
    source = choice.get("quote_number") or "Wishlist / customer record"
    return f"{source} · {choice['name']} · " + " · ".join(details)


def service_request_card(row: sqlite3.Row) -> None:
    priority_color = {
        "Urgent": "#b42318",
        "High": "#9a6700",
        "Normal": "#2e6b45",
        "Low": "#68736d",
    }.get(row["priority"], "#68736d")
    title = f"{row['request_number']} · {row['customer_name']} · {row['product_name']} · {row['status']}"
    with st.expander(title, expanded=row["status"] not in ("Repair completed", "Closed")):
        top1, top2, top3 = st.columns([1.2, 1.3, 1])
        with top1:
            st.markdown(f"**Customer:** {row['customer_name']}")
            st.markdown(f"**Phone:** {row['customer_phone'] or 'Not set'}")
            st.markdown(f"**Email:** {row['customer_email'] or 'Not set'}")
        with top2:
            st.markdown(f"**Project address:** {row['project_address'] or 'Not set'}")
            st.markdown(f"**Quote / order:** {row['quote_number'] or 'Customer record'}")
            st.markdown(f"**Product:** {row['product_name']} `{row['product_id'] or ''}`")
        with top3:
            st.markdown(f"<b>Priority:</b> <span style='color:{priority_color}'>{row['priority']}</span>", unsafe_allow_html=True)
            st.markdown(f"**Created:** {display_date(str(row['created_at'])[:10])}")
            st.markdown(f"**Appointment:** {display_date(row['appointment_date'])}")
        st.markdown(f"**Damaged part:** {row['damaged_part']}")
        st.markdown(f"**Damage reason:** {row['damage_reason']}")
        st.write(row["issue_description"])
        if row["internal_notes"]:
            st.markdown("**Internal notes**")
            st.write(row["internal_notes"])

        timeline = service_timeline(int(row["id"]))
        if timeline:
            st.markdown("**Service timeline**")
            for event in timeline:
                st.markdown(f"{display_date(event['event_date'])} · **{event['title']}** · {event['status']}")
                if event["notes"]:
                    st.caption(event["notes"])

        st.markdown("**Update progress**")
        update1, update2, update3 = st.columns([1.2, 1, 1])
        with update1:
            new_status = st.selectbox(
                "Status",
                SERVICE_STATUSES,
                index=option_index(SERVICE_STATUSES, row["status"]),
                key=f"service-status-{row['id']}",
            )
        with update2:
            appointment_date = st.date_input(
                "Customer appointment",
                value=date_from_iso(row["appointment_date"], date.today()),
                key=f"service-appointment-{row['id']}",
            )
        with update3:
            assigned_to = st.text_input("Assigned to", value=row["assigned_to"] or "", key=f"service-assigned-{row['id']}")
        internal_notes = st.text_area(
            "Internal repair notes",
            value=row["internal_notes"] or "",
            height=80,
            key=f"service-internal-{row['id']}",
        )
        timeline_notes = st.text_input(
            "Timeline note for this update",
            placeholder="Example: Confirmed appointment with customer for Friday morning.",
            key=f"service-timeline-note-{row['id']}",
        )
        if st.button("Save service progress", type="primary", key=f"save-service-{row['id']}", width="stretch"):
            update_service_request(
                int(row["id"]),
                new_status,
                appointment_date,
                assigned_to,
                internal_notes,
                timeline_notes,
            )
            st.success("Service progress updated.")
            st.rerun()


def after_sales_page() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="eyebrow">After-sales service</div>
          <h1>After-sales Requests and Repair Progress</h1>
          <p>Search customers, review quote or order products, submit service requests for specific products, and track appointments, repairs, and completion.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    submit_tab, dashboard_tab = st.tabs(["Submit service request", "Service dashboard"])

    with submit_tab:
        search = st.text_input(
            "Search customer",
            placeholder="Search customer name, phone, email, project address or interested products...",
            key="service_customer_search",
        )
        rows = customer_rows(search=search.strip())
        if not rows:
            st.markdown('<div class="empty">No customers found. Create or import the customer from the Customers tab first.</div>', unsafe_allow_html=True)
        else:
            st.caption(f"{len(rows)} customer(s) found")
            for row in rows[:8]:
                info, action = st.columns([4, 1], vertical_alignment="center")
                with info:
                    st.markdown(f"**{row['name']}** · {row['phone'] or row['email'] or 'No contact'}")
                    st.caption(f"{row['address'] or 'No project address'} · {customer_title_detail(row)}")
                with action:
                    if st.button("Select", key=f"service-select-customer-{row['id']}", width="stretch"):
                        st.session_state.service_customer_id = int(row["id"])
                        st.rerun()

        selected_customer = customer_by_id(st.session_state.service_customer_id) if st.session_state.service_customer_id else None
        if not selected_customer:
            st.info("Select a customer above to submit a service request. The dashboard tab is still available.")
        else:
            st.divider()
            st.markdown(f"### Selected customer: {selected_customer['name']}")
            st.write(
                f"**Phone:** {selected_customer['phone'] or 'Not set'}  \n"
                f"**Email:** {selected_customer['email'] or 'Not set'}  \n"
                f"**Project address:** {selected_customer['address'] or 'Not set'}"
            )
            quote_rows = customer_quotes(int(selected_customer["id"]))
            if quote_rows:
                st.markdown("**Quote / order records**")
                for quote_row in quote_rows:
                    st.write(
                        f"{quote_row['quote_number']} · {money(float(quote_row['total']))} · "
                        f"{display_date(str(quote_row['created_at'])[:10])} · {quote_row['status']}"
                    )
            else:
                st.info("This customer has no saved quote yet. You can still submit service from their wishlist / customer record if available.")

            product_choices = customer_service_product_choices(int(selected_customer["id"]))
            if not product_choices:
                st.warning("No quote products or wishlist products found for this customer.")
            else:
                with st.form("service-request-form"):
                    selected_index = st.selectbox(
                        "Choose product for after-sales request *",
                        range(len(product_choices)),
                        format_func=lambda index: product_choice_label(product_choices[index]),
                    )
                    selected_choice = product_choices[selected_index]
                    snapshot = selected_choice.get("snapshot", {})
                    st.markdown("#### Product selected")
                    st.write(product_choice_label(selected_choice))
                    if snapshot.get("notes"):
                        st.caption(str(snapshot["notes"]))

                    form1, form2, form3 = st.columns(3)
                    with form1:
                        damaged_part = st.selectbox("Which part is damaged? *", DAMAGED_PARTS)
                        priority = st.selectbox("Priority", SERVICE_PRIORITIES, index=2)
                    with form2:
                        damage_reason = st.selectbox("Damage reason *", DAMAGE_REASONS)
                        appointment_date = st.date_input("Appointment date", value=date.today())
                    with form3:
                        status = st.selectbox("Initial status", SERVICE_STATUSES, index=0)
                        assigned_to = st.text_input("Assign to / Owner or after-sales team", placeholder="After-sales team, manager name...")
                    issue_description = st.text_area(
                        "Issue details *",
                        placeholder="Describe what happened, when it was discovered, photos received, access notes, customer availability...",
                        height=120,
                    )
                    internal_notes = st.text_area("Internal notes", height=80)
                    submit = st.form_submit_button("Submit after-sales request", type="primary", width="stretch")
                    if submit:
                        if not issue_description.strip():
                            st.error("Please describe the service issue before submitting.")
                        else:
                            request_id = save_service_request(
                                {
                                    "status": status,
                                    "priority": priority,
                                    "customer_id": int(selected_customer["id"]),
                                    "customer_name": selected_customer["name"],
                                    "customer_email": selected_customer["email"],
                                    "customer_phone": selected_customer["phone"],
                                    "project_address": selected_customer["address"],
                                    "quote_number": selected_choice.get("quote_number", ""),
                                    "product_id": selected_choice.get("product_id", ""),
                                    "product_name": selected_choice["name"],
                                    "product_snapshot": json.dumps(snapshot, ensure_ascii=False),
                                    "damaged_part": damaged_part,
                                    "damage_reason": damage_reason,
                                    "issue_description": issue_description.strip(),
                                    "appointment_date": appointment_date.isoformat(),
                                    "assigned_to": assigned_to.strip(),
                                    "internal_notes": internal_notes.strip(),
                                    "completed_at": "",
                                }
                            )
                            st.session_state.service_editor_id = request_id
                            st.success("After-sales request submitted. It is now visible in the service dashboard.")
                            st.rerun()

    with dashboard_tab:
        rows = service_requests()
        open_rows = [row for row in rows if row["status"] not in ("Repair completed", "Closed")]
        scheduled = [row for row in rows if row["status"] == "Appointment scheduled"]
        completed = [row for row in rows if row["status"] in ("Repair completed", "Closed")]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Open service", len(open_rows))
        m2.metric("Appointments", len(scheduled))
        m3.metric("Completed", len(completed))
        m4.metric("All requests", len(rows))

        filter1, filter2 = st.columns([2, 1])
        with filter1:
            service_search = st.text_input("Search service requests", placeholder="Search customer, request number, quote, product, issue...", key="service_dashboard_search")
        with filter2:
            status_filter = st.selectbox(
                "Status filter",
                ("", *SERVICE_STATUSES),
                format_func=lambda value: "All statuses" if value == "" else value,
            )
        filtered_rows = service_requests(search=service_search.strip(), status=status_filter)
        if not filtered_rows:
            st.markdown('<div class="empty">No after-sales requests found.</div>', unsafe_allow_html=True)
        for row in filtered_rows:
            service_request_card(row)


def inventory_editor(existing: sqlite3.Row | None = None) -> None:
    is_edit = existing is not None
    product_options = [product.id for product in PRODUCTS]
    if not product_options:
        st.info("Add products before recording inventory.")
        return
    default_product_id = existing["product_id"] if is_edit and existing["product_id"] in product_options else product_options[0]

    def option_index(options: tuple[str, ...], current: str | None) -> int:
        return options.index(current) if current in options else 0

    with st.form("inventory-editor"):
        st.markdown("### Edit inventory item" if is_edit else "### Add inventory")
        identity1, identity2, identity3 = st.columns(3)
        with identity1:
            product_id = st.selectbox(
                "Product *",
                product_options,
                index=product_options.index(default_product_id),
                format_func=lambda product_id: f"{get_product(product_id).name} · {product_id}",
            )
            sku = st.text_input("SKU / batch number", value=existing["sku"] if is_edit else "")
        with identity2:
            received_date = st.date_input(
                "Received date *",
                value=date_from_iso(existing["received_date"] if is_edit else None, date.today()),
            )
            status = st.selectbox(
                "Status",
                INVENTORY_STATUSES,
                index=INVENTORY_STATUSES.index(existing["status"]) if is_edit and existing["status"] in INVENTORY_STATUSES else 0,
            )
        with identity3:
            warehouse = st.text_input("Warehouse", value=existing["warehouse"] if is_edit else "")
            location = st.text_input("Location", value=existing["location"] if is_edit else "")

        selected_product = get_product(product_id)
        specs1, specs2, specs3, specs4 = st.columns(4)
        with specs1:
            color_options = ("", *(selected_product.color_options or selected_product.frame_colors))
            color = st.selectbox(
                "Color",
                color_options,
                index=option_index(color_options, existing["color"] if is_edit else ""),
                format_func=lambda value: "Any / not specified" if value == "" else value,
            )
            width = st.number_input("Width (inches)", min_value=0.0, value=float(existing["width"] or 0) if is_edit else 0.0, step=0.5)
        with specs2:
            glass_options = ("", *selected_product.glass_colors)
            glass = st.selectbox(
                "Glass",
                glass_options,
                index=option_index(glass_options, existing["glass"] if is_edit else ""),
                format_func=lambda value: "Any / not specified" if value == "" else value,
            )
            height = st.number_input("Height (inches)", min_value=0.0, value=float(existing["height"] or 0) if is_edit else 0.0, step=0.5)
        with specs3:
            frame_options = ("", *selected_product.frame_colors)
            frame = st.selectbox(
                "Frame / finish",
                frame_options,
                index=option_index(frame_options, existing["frame"] if is_edit else ""),
                format_func=lambda value: "Any / not specified" if value == "" else value,
            )
            quantity = st.number_input("Quantity *", min_value=0, value=int(existing["quantity"] or 0) if is_edit else 1, step=1)
        with specs4:
            direction_options = ("", *selected_product.directions)
            direction = st.selectbox(
                "Opening / handing",
                direction_options,
                index=option_index(direction_options, existing["direction"] if is_edit else ""),
                format_func=lambda value: "Any / not specified" if value == "" else value,
            )
            reserved_quantity = st.number_input("Reserved quantity", min_value=0, value=int(existing["reserved_quantity"] or 0) if is_edit else 0, step=1)
        cost_notes1, cost_notes2 = st.columns([1, 2])
        with cost_notes1:
            unit_cost = st.number_input("Unit cost", min_value=0.0, value=float(existing["unit_cost"] or 0) if is_edit else 0.0, step=10.0)
        with cost_notes2:
            notes = st.text_area("Notes", value=existing["notes"] if is_edit else "", height=90)
        submitted = st.form_submit_button("Save inventory", type="primary", width="stretch")
        if submitted:
            if reserved_quantity > quantity:
                st.error("Reserved quantity cannot be greater than quantity.")
                return
            saved_id = save_inventory_item(
                int(existing["id"]) if is_edit else None,
                {
                    "product_id": product_id,
                    "sku": sku.strip(),
                    "received_date": received_date.isoformat(),
                    "warehouse": warehouse.strip(),
                    "location": location.strip(),
                    "width": float(width),
                    "height": float(height),
                    "color": color,
                    "glass": glass,
                    "frame": frame,
                    "direction": direction,
                    "quantity": int(quantity),
                    "reserved_quantity": int(reserved_quantity),
                    "unit_cost": float(unit_cost),
                    "status": status,
                    "notes": notes.strip(),
                },
            )
            st.session_state.inventory_editor_id = saved_id
            st.success("Inventory saved.")
            st.rerun()


def inventory_page() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="eyebrow">Inventory</div>
          <h1>Inventory Entry and Search</h1>
          <p>Record product specs, received dates, warehouse locations, and available quantities. Customer records automatically show matching stock availability.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    rows = inventory_rows()
    total_quantity = sum(int(row["quantity"] or 0) for row in rows if row["status"] in ("Available", "Reserved"))
    reserved = sum(int(row["reserved_quantity"] or 0) for row in rows if row["status"] in ("Available", "Reserved"))
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Inventory records", len(rows))
    m2.metric("Total units", total_quantity)
    m3.metric("Available units", max(total_quantity - reserved, 0))
    m4.metric("Reserved units", reserved)

    search_col, product_col = st.columns([2, 1])
    with search_col:
        search = st.text_input("Search inventory", placeholder="Search product, SKU, warehouse, color, location or notes...")
    with product_col:
        product_filter_options = [""] + [product.id for product in PRODUCTS]
        product_filter = st.selectbox(
            "Product filter",
            product_filter_options,
            format_func=lambda value: "All products" if value == "" else f"{get_product(value).name} · {value}",
        )
    filtered_rows = inventory_rows(search=search.strip(), product_id=product_filter)

    list_tab, edit_tab = st.tabs(["Inventory list", "Add / Edit"])
    with list_tab:
        if not filtered_rows:
            st.markdown('<div class="empty">No inventory records found. Add stock from the Add / Edit tab.</div>', unsafe_allow_html=True)
        else:
            for row in filtered_rows:
                product = get_product_or_none(row["product_id"])
                product_name = product.name if product else row["product_id"]
                available = max(int(row["quantity"] or 0) - int(row["reserved_quantity"] or 0), 0)
                with st.container(border=True):
                    top, actions = st.columns([4, 1], vertical_alignment="center")
                    with top:
                        st.markdown(f"**{product_name}** · `{row['product_id']}` · {row['status']}")
                        details = [
                            f"Received: {display_date(row['received_date'])}",
                            f"SKU: {row['sku'] or 'Not set'}",
                            f"Warehouse: {row['warehouse'] or 'Not set'}",
                            f"Location: {row['location'] or 'Not set'}",
                        ]
                        st.caption(" · ".join(details))
                        spec_line = " · ".join(
                            value
                            for value in (
                                f"{float(row['width']):.1f}\" W" if row["width"] else "",
                                f"{float(row['height']):.1f}\" H" if row["height"] else "",
                                row["color"] or "",
                                row["glass"] or "",
                                row["frame"] or "",
                                row["direction"] or "",
                            )
                            if value
                        )
                        if spec_line:
                            st.write(spec_line)
                        if row["notes"]:
                            st.caption(row["notes"])
                    with actions:
                        st.metric("Available", available)
                        st.caption(f"Qty {int(row['quantity'] or 0)} · Reserved {int(row['reserved_quantity'] or 0)}")
                        if st.button("Edit", key=f"edit-inventory-{row['id']}", width="stretch"):
                            st.session_state.inventory_editor_id = int(row["id"])
                            st.rerun()
    with edit_tab:
        edit_options = [0] + [int(row["id"]) for row in inventory_rows()]
        selected_id = st.selectbox(
            "Choose inventory item",
            edit_options,
            index=edit_options.index(st.session_state.inventory_editor_id) if st.session_state.inventory_editor_id in edit_options else 0,
            format_func=lambda value: "Add new inventory" if value == 0 else f"Inventory #{value}",
        )
        st.session_state.inventory_editor_id = selected_id or None
        inventory_editor(inventory_item_by_id(selected_id) if selected_id else None)
        if selected_id:
            st.divider()
            confirm_delete = st.checkbox("I understand this inventory record will be deleted.", key=f"confirm-delete-inventory-{selected_id}")
            if st.button("Delete inventory record", disabled=not confirm_delete, type="secondary", width="stretch"):
                delete_inventory_item(int(selected_id))
                st.session_state.inventory_editor_id = None
                st.success("Inventory record deleted.")
                st.rerun()


def top_nav() -> None:
    left, nav1, nav2, nav3, nav4, finance_nav, admin_nav, cart, account = st.columns([2.0, 0.85, 1.0, 1.0, 1.15, 0.9, 0.85, 1.0, 0.95], vertical_alignment="center")
    with left:
        st.markdown('<div class="brand"><div class="mark">▦</div> FRAMEFLOW <span style="font-size:11px;color:#748079;font-weight:500">TRADE PORTAL</span></div>', unsafe_allow_html=True)
    for column, label in [(nav1, "Catalog"), (nav2, "Inventory"), (nav3, "Customers"), (nav4, "After-sales")]:
        with column:
            if st.button(label, type="tertiary", width="stretch"):
                st.session_state.page = label
                st.session_state.selected_product = None
                st.rerun()
    with finance_nav:
        if st.button("Finance", type="tertiary", width="stretch"):
            st.session_state.page = "Finance"
            st.session_state.selected_product = None
            st.rerun()
    with admin_nav:
        if is_manager_user() and st.button("Admin", type="tertiary", width="stretch"):
            st.session_state.page = "Admin"
            st.session_state.selected_product = None
            st.rerun()
    with cart:
        if st.button(f"Cart  {len(st.session_state.cart)}", type="primary", width="stretch"):
            st.session_state.page = "Cart"
            st.session_state.selected_product = None
            st.rerun()
    with account:
        if st.button("Sign out", type="tertiary", width="stretch"):
            st.session_state.employee_authenticated = False
            st.session_state.employee_name = ""
            st.session_state.admin_authenticated = False
            st.session_state.page = "Catalog"
            st.session_state.selected_product = None
            st.session_state.active_customer_id = None
            st.session_state.customer_editor_id = None
            st.session_state.inline_customer_editor_id = None
            st.session_state.service_customer_id = None
            st.session_state.cart = []
            st.rerun()
    st.markdown("<div style='border-bottom:1px solid #dfe4e0;margin-bottom:18px'></div>", unsafe_allow_html=True)


def image_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def direction_visual(product: Product, direction: str) -> tuple[Path, str, str] | None:
    value = direction.lower()
    category = product.category.lower()
    product_name = product.name.lower()
    if "bifold" in category or "bifold" in product_name:
        if "split" in value:
            icon_id = "bifold-split-stack"
            title = "Split stack / panels fold to both sides"
            description = "The folding panels divide and stack on both sides of the opening."
        elif "right" in value:
            icon_id = "bifold-stack-right"
            title = "Stack right / panels fold to the right"
            description = "Viewed from outside facing inside, the panels collect on the right side."
        else:
            icon_id = "bifold-stack-left"
            title = "Stack left / panels fold to the left"
            description = "Viewed from outside facing inside, the panels collect on the left side."
        return opening_direction_path(icon_id), title, description
    if "hinge" in category or "casement door" in product_name or "hinged" in product_name:
        side = "right" if "right" in value else "left"
        swing = "outswing" if "out" in value else "inswing"
        icon_id = f"hinge-{side}-{swing}"
        title = f"{side.title()} {swing}"
        description = (
            "The plan view shows interior/exterior so the customer can confirm the door swings to the correct side."
        )
        return opening_direction_path(icon_id), title, description
    return None


def render_direction_visual(product: Product, direction: str) -> None:
    visual = direction_visual(product, direction)
    if not visual:
        return
    path, title, description = visual
    if not path.exists():
        make_opening_direction_icon(path.stem)
    st.markdown(
        f"""
        <div class="direction-visual">
          <img src="{image_data_uri(path)}" alt="{html.escape(title)} opening direction diagram">
          <div>
            <div class="direction-visual-title">{html.escape(title)}</div>
            <div class="direction-visual-copy">{html.escape(description)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def opening_style_grid(section: str) -> None:
    available_categories = {product.category for product in PRODUCTS if product.section == section and product.active}
    styles = [style for style in OPENING_STYLES.get(section, []) if style["category"] in available_categories]
    if not styles:
        return
    st.markdown(f'<div class="opening-heading">Browse all {section} →</div>', unsafe_allow_html=True)
    columns = st.columns(5 if section == "Windows" else 6)
    for index, style in enumerate(styles):
        active = st.session_state.category == style["category"]
        path = opening_style_path(style["icon"])
        image_src = image_data_uri(path) if path.exists() else ""
        with columns[index % len(columns)]:
            st.markdown(
                f"""
                <div class="opening-card {'active' if active else ''}">
                  <img src="{image_src}" alt="{style['label']} opening diagram">
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(style["label"], key=f"opening-{section}-{style['category']}", type="primary" if active else "secondary", width="stretch"):
                st.session_state.category = style["category"]
                st.rerun()
    st.write("")


def product_card(product: Product) -> None:
    st.image(str(image_path(product, "hero")), width="stretch")
    st.markdown(
        f"""
        <div style="min-height:104px">
          <div class="eyebrow">{product.category}</div>
          <h3 style="margin:.3rem 0">{product.name}</h3>
          <p style="color:#6d756f;font-size:13px;margin:.2rem 0">{product.subtitle}</p>
          <div style="font-weight:700;color:#2e4338;font-size:13px;margin-top:8px">{product_price_label(product)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Configure product", key=f"view-{product.id}", width="stretch"):
        st.session_state.selected_product = product.id
        st.rerun()


def product_info_panel(product: Product) -> None:
    stock_text = product.stock_information.strip()
    if not stock_text:
        return
    st.divider()
    st.markdown("### Stock information")
    with st.container(border=True):
        st.write(stock_text)


def configuration_stock_panel(
    product: Product,
    width: float,
    height: float,
    color: str,
    glass: str,
    frame: str,
    direction: str,
    quantity: int,
) -> None:
    stock_text = product.stock_information.strip()
    matches = matching_inventory_rows(product.id, width, height, color, glass, frame, direction)
    available = sum(inventory_available_quantity(row) for row in matches)
    reserved = sum(int(row["reserved_quantity"] or 0) for row in matches)
    total = sum(int(row["quantity"] or 0) for row in matches)
    if available >= quantity:
        stock_label = f"Current selection in stock: {available} available"
        stock_color = "#2e6b45"
    elif available > 0:
        stock_label = f"Partial stock: {available} available, {quantity} requested"
        stock_color = "#9a6700"
    else:
        stock_label = "No matching stock for current selection"
        stock_color = "#b42318"
    st.markdown(
        """
        <div style="background:#fbfcfa;border:1px solid #dfe4e0;border-radius:12px;padding:14px;margin:10px 0 14px">
          <div style="font-size:12px;font-weight:800;color:#68736d;text-transform:uppercase;letter-spacing:.08em">Inventory</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='color:{stock_color};font-weight:800;margin-bottom:6px'>{stock_label}</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"Matched: {width:.1f}\" W x {height:.1f}\" H · {color} · {glass} glass · "
        f"{frame} finish · {direction}"
    )
    metric1, metric2, metric3 = st.columns(3)
    metric1.metric("Available", available)
    metric2.metric("Reserved", reserved)
    metric3.metric("Total matched", total)
    if matches:
        st.markdown("**Matching warehouse stock**")
        stock_rows = []
        for row in matches[:12]:
            details = " · ".join(
                value
                for value in (
                    f"{float(row['width']):.1f}\" W" if row["width"] else "",
                    f"{float(row['height']):.1f}\" H" if row["height"] else "",
                    row["color"] or "",
                    row["glass"] or "",
                    row["frame"] or "",
                    row["direction"] or "",
                )
                if value
            )
            stock_rows.append(
                {
                    "SKU": row["sku"] or f"Inventory #{row['id']}",
                    "Warehouse": row["warehouse"] or "Not set",
                    "Location": row["location"] or "Not set",
                    "Available": inventory_available_quantity(row),
                    "Qty": int(row["quantity"] or 0),
                    "Reserved": int(row["reserved_quantity"] or 0),
                    "Received": display_date(row["received_date"]),
                    "Details": details or "General stock",
                    "Notes": row["notes"] or "",
                }
            )
        st.dataframe(stock_rows, hide_index=True, width="stretch")
        if len(matches) > 12:
            st.caption(f"Showing 12 of {len(matches)} matching inventory records.")
    else:
        broader_summary = inventory_summary(product.id, color)
        if broader_summary["available"]:
            st.info(
                f"This product/color has {broader_summary['available']} available unit(s), "
                "but none match the current size/options exactly."
            )
        else:
            st.write("No warehouse stock matches this product and color yet.")
    if stock_text:
        st.markdown("**Product stock note**")
        st.write(stock_text)
    st.markdown("</div>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def configured_preview_bytes(image_file: str, glass: str, mirror: bool = False) -> bytes:
    image = Image.open(image_file).convert("RGBA")
    if mirror:
        image = ImageOps.mirror(image)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def should_mirror_for_direction(direction: str, product: Product | None = None) -> bool:
    value = direction.lower()
    neutral_terms = ("split", "center", "fixed", "both")
    if any(term in value for term in neutral_terms):
        return False
    product_text = f"{product.category if product else ''} {product.name if product else ''}".lower()
    if "bifold" in product_text:
        return "stack left" in value or (("left" in value) and ("stack" in value))
    mirror_terms = ("right", "hinge right", "pivot right")
    return any(term in value for term in mirror_terms)


def catalog_page() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="eyebrow">Internal sales configurator</div>
          <h1>Build a better opening.</h1>
          <p>Configure made-to-measure doors and windows, calculate pricing, and create a polished customer quote in one place.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    doors, windows, accessories, spacer = st.columns([1, 1, 1.25, 3.75])
    with doors:
        if st.button("Doors", type="primary" if st.session_state.section == "Doors" else "secondary", width="stretch"):
            st.session_state.section = "Doors"
            st.session_state.category = "All doors"
            st.rerun()
    with windows:
        if st.button("Windows", type="primary" if st.session_state.section == "Windows" else "secondary", width="stretch"):
            st.session_state.section = "Windows"
            st.session_state.category = "All windows"
            st.rerun()
    with accessories:
        if st.button("Accessories", type="primary" if st.session_state.section == "Accessories" else "secondary", width="stretch"):
            st.session_state.section = "Accessories"
            st.session_state.category = "All accessories"
            st.rerun()
    st.write("")
    opening_style_grid(st.session_state.section)
    all_labels = {
        "Doors": "All doors",
        "Windows": "All windows",
        "Accessories": "All accessories",
    }
    all_label = all_labels.get(st.session_state.section, f"All {st.session_state.section.lower()}")
    visible = [p for p in PRODUCTS if p.active and p.section == st.session_state.section and (st.session_state.category == all_label or p.category == st.session_state.category)]
    st.markdown(f"### {st.session_state.section}")
    st.caption(f"{len(visible)} product systems · Pricing shown is an estimate before tax")
    cols = st.columns(3)
    for index, product in enumerate(visible):
        with cols[index % 3]:
            with st.container(border=True):
                product_card(product)


def configure_page(product: Product) -> None:
    if st.button("← Back to catalog", type="tertiary"):
        st.session_state.selected_product = None
        st.rerun()
    customers = customer_rows()
    customer_options = [0] + [int(row["id"]) for row in customers]
    customer_lookup = {int(row["id"]): row for row in customers}
    selector_col, add_col = st.columns([2.4, 1], vertical_alignment="bottom")
    with selector_col:
        selected_customer = st.selectbox(
            "Adding items for",
            customer_options,
            index=customer_options.index(st.session_state.active_customer_id) if st.session_state.active_customer_id in customer_options else 0,
            format_func=lambda value: "No customer selected" if value == 0 else customer_picker_label(customer_lookup[value]),
            help="Open the dropdown and type a customer name, phone, email, or company to search. Each customer keeps their own saved cart.",
        )
    with add_col:
        st.write("")
        if st.button("Add new customer", width="stretch", key="configure-add-customer-button"):
            st.session_state.show_quick_customer_form = not st.session_state.get("show_quick_customer_form", False)
            st.rerun()
    if st.session_state.get("show_quick_customer_form"):
        with st.form("quick-customer-from-configure"):
            st.markdown("#### Add new customer")
            quick1, quick2 = st.columns(2)
            with quick1:
                quick_name = st.text_input("Customer name *", key="quick-customer-name")
                quick_phone = st.text_input("Phone", placeholder="(123) 456-7890", help="Enter a 10-digit US phone number. It will be saved as (123) 456-7890.", key="quick-customer-phone")
                quick_email = st.text_input("Email", key="quick-customer-email")
            with quick2:
                quick_company = st.text_input("Company", key="quick-customer-company")
                quick_source = st.text_input("Lead source", value="Catalog", key="quick-customer-source")
                quick_address = st.text_input("Address", key="quick-customer-address")
            submitted_customer = st.form_submit_button("Create and use this customer", type="primary", width="stretch")
            if submitted_customer:
                if not quick_name.strip():
                    st.error("Customer name is required.")
                    return
                if quick_phone.strip() and not is_valid_us_phone(quick_phone):
                    st.error("Please enter a 10-digit US phone number, for example (123) 456-7890.")
                    return
                current_cart = list(st.session_state.cart)
                had_active_customer = bool(st.session_state.active_customer_id)
                save_customer_cart(st.session_state.active_customer_id)
                new_customer_id = save_customer(
                    None,
                    {
                        "status": "Following",
                        "name": quick_name.strip(),
                        "company": quick_company.strip(),
                        "email": quick_email.strip(),
                        "phone": format_us_phone(quick_phone),
                        "address": quick_address.strip(),
                        "products_interest": product.name,
                        "client_type": "",
                        "client_type_note": "",
                        "project_type": "",
                        "project_type_note": "",
                        "use_case": "",
                        "use_case_note": "",
                        "area_zip": "",
                        "area_zip_note": "",
                        "showroom_status": "",
                        "showroom_note": "",
                        "answer_status": "",
                        "answer_status_note": "",
                        "source": quick_source.strip() or "Catalog",
                        "initial_contact_date": today_iso(),
                        "priority": "Medium",
                        "budget": 0.0,
                        "assigned_to": "",
                        "notes": "",
                        "first_followup_date": today_iso(),
                        "next_followup_date": (date.today() + timedelta(days=7)).isoformat(),
                        "followup_stage": FOLLOWUP_STAGES[0],
                        "on_hold": 0,
                        "order_date": today_iso(),
                        "first_payment_date": today_iso(),
                        "first_payment_amount": 0.0,
                        "first_payment_paid": 0,
                        "second_payment_enabled": 0,
                        "second_payment_date": today_iso(),
                        "second_payment_amount": 0.0,
                        "second_payment_paid": 0,
                        "install_followup_date": today_iso(),
                        "install_status": "",
                        "lost_date": today_iso(),
                        "lost_reason": "",
                        "lost_notes": "",
                        "wishlist": "[]",
                    },
                )
                add_customer_timeline_event(new_customer_id, date.today(), "Customer created", f"Created from product page while viewing {product.name}.")
                if had_active_customer:
                    set_active_customer(new_customer_id)
                else:
                    set_active_customer(new_customer_id, load_cart=False)
                    st.session_state.cart = current_cart
                    save_customer_cart(new_customer_id)
                st.session_state.show_quick_customer_form = False
                st.success(f"{quick_name.strip()} created and selected.")
                st.rerun()
    if selected_customer != (st.session_state.active_customer_id or 0):
        save_customer_cart(st.session_state.active_customer_id)
        set_active_customer(selected_customer or None)
        st.rerun()
    if st.session_state.active_customer_id:
        st.info(f"Adding items for: {customer_display_name(st.session_state.active_customer_id)}")
    color_choices = product.color_options or product.frame_colors
    config_defaults = {
        f"config-{product.id}-direction": product.directions[0],
        f"config-{product.id}-glass": product.glass_colors[0],
        f"config-{product.id}-frame": product.frame_colors[0],
        f"config-{product.id}-color": color_choices[0],
        f"config-{product.id}-width": 72.0 if product.section == "Doors" else 48.0,
        f"config-{product.id}-height": 96.0 if product.section == "Doors" else 60.0,
        f"config-{product.id}-quantity": 1,
        f"config-{product.id}-notes": "",
    }
    for key, value in config_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    option_guards = {
        f"config-{product.id}-direction": product.directions,
        f"config-{product.id}-glass": product.glass_colors,
        f"config-{product.id}-frame": product.frame_colors,
        f"config-{product.id}-color": color_choices,
    }
    for key, options in option_guards.items():
        if st.session_state[key] not in options:
            st.session_state[key] = options[0]
    selected_glass = st.session_state[f"config-{product.id}-glass"]
    selected_direction = st.session_state[f"config-{product.id}-direction"]
    mirror_preview = should_mirror_for_direction(selected_direction, product)
    image_col, form_col = st.columns([1.15, 0.85], gap="large")
    with image_col:
        hero_path = image_path(product, "hero")
        st.image(configured_preview_bytes(str(hero_path), selected_glass, mirror_preview), width="stretch")
        st.caption(
            f"Preview shown as {selected_direction}, viewed from outside facing inside."
            if mirror_preview
            else "Preview shown from outside facing inside."
        )
        gallery = [image_path(product, "hero")] + detail_image_paths(product)
        columns = st.columns(min(3, len(gallery)))
        for index, path in enumerate(gallery):
            with columns[index % len(columns)]:
                st.image(
                    configured_preview_bytes(str(path), selected_glass, mirror_preview),
                    caption="Effect / room view" if index == 0 else f"Product detail {index}",
                    width="stretch",
                )
    with form_col:
        st.markdown(f'<div class="eyebrow">{product.category} · {product.id}</div>', unsafe_allow_html=True)
        st.title(product.name)
        st.write(product.description)
        sales_base_rate = float(product.base_rate)
        if product.base_rate <= 0:
            st.markdown(
                f'<div style="font-weight:700;color:#2e4338;margin:8px 0 18px">{product_price_label(product)}</div>',
                unsafe_allow_html=True,
            )
        st.markdown("#### Configuration")
        hide_opening_and_glass = product.id == "AC-100" or product.name.strip().lower() == "roller screen"
        direction = st.session_state[f"config-{product.id}-direction"]
        glass = st.session_state[f"config-{product.id}-glass"]
        config1, config2 = st.columns(2)
        if hide_opening_and_glass:
            with config1:
                frame = st.selectbox("Frame / finish", product.frame_colors, key=f"config-{product.id}-frame")
            with config2:
                color = st.selectbox("Stacking side", color_choices, key=f"config-{product.id}-color")
            direction = color
        else:
            with config1:
                direction = st.selectbox("Opening / handing", product.directions, key=f"config-{product.id}-direction")
                frame = st.selectbox("Frame / finish", product.frame_colors, key=f"config-{product.id}-frame")
            with config2:
                glass = st.selectbox("Glass", product.glass_colors, key=f"config-{product.id}-glass")
                color = st.selectbox("Color", color_choices, key=f"config-{product.id}-color")
            render_direction_visual(product, direction)
        width_col, height_col = st.columns(2)
        with width_col:
            width = st.number_input("Width (inches)", min_value=12.0, max_value=360.0, step=0.5, key=f"config-{product.id}-width")
        with height_col:
            height = st.number_input("Height (inches)", min_value=12.0, max_value=240.0, step=0.5, key=f"config-{product.id}-height")
        quantity = st.number_input("Quantity", min_value=1, max_value=99, key=f"config-{product.id}-quantity")
        notes = st.text_area("Item notes", placeholder="Hardware, project room, special requirements…", key=f"config-{product.id}-notes")
        unit_price, breakdown = price_product(product, width, height, glass, frame)
        if product.base_rate > 0:
            rate_info_col, rate_input_col = st.columns([0.8, 1.2], vertical_alignment="bottom")
            with rate_info_col:
                st.caption(f"Company base price: {money(product.base_rate)}/sq ft")
            with rate_input_col:
                rate_key = f"config-{product.id}-sales-rate"
                rate_sync_key = f"config-{product.id}-sales-rate-base"
                if st.session_state.get(rate_sync_key) != float(product.base_rate):
                    st.session_state[rate_key] = float(product.base_rate)
                    st.session_state[rate_sync_key] = float(product.base_rate)
                sales_base_rate = st.number_input(
                    "Sales price ($/sq ft)",
                    min_value=0.0,
                    step=1.0,
                    key=rate_key,
                    help="Company standard price is shown on the left. If approved, adjust this sales price per square foot for this quote.",
                )
        sales_unit_price, sales_breakdown = price_product_with_rate(product, width, height, glass, frame, sales_base_rate)
        price_adjusted_by_rate = abs(float(sales_base_rate) - float(product.base_rate)) > 0.005
        st.markdown(
            f"""
            <div style="background:#edf1ed;padding:16px;border-radius:12px;margin:10px 0">
              <span style="color:#65706a;font-size:12px">CALCULATED PRICE</span>
              <div style="font-size:28px;font-weight:700;color:#203128">{money(sales_unit_price)}</div>
              <span style="color:#65706a;font-size:12px">{sales_breakdown['area_sqft']:.2f} sq ft × {money(sales_base_rate)}/sq ft</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if price_adjusted_by_rate:
            st.caption(f"Company base calculation: {money(unit_price)} at {money(product.base_rate)}/sq ft.")
        configuration_stock_panel(product, width, height, color, glass, frame, direction, int(quantity))
        if st.button("Add to cart", type="primary", width="stretch", key=f"add-cart-{product.id}"):
            item = {
                "line_id": hashlib.sha1(f"{product.id}-{datetime.now().isoformat()}".encode()).hexdigest()[:10],
                "product_id": product.id,
                "name": product.name,
                "category": product.category,
                "direction": direction,
                "glass": glass,
                "frame": frame,
                "color": color,
                "width": width,
                "height": height,
                "quantity": int(quantity),
                "area_sqft": breakdown["area_sqft"],
                "base_rate": product.base_rate,
                "sales_base_rate": sales_base_rate,
                "original_unit_price": unit_price,
                "unit_price": sales_unit_price,
                "line_total": sales_unit_price * quantity,
                "price_adjusted": price_adjusted_by_rate,
                "price_adjustment_mode": "rate" if price_adjusted_by_rate else "",
                "included_in_quote": True,
                "notes": notes,
            }
            merged = add_or_merge_cart_item(item)
            save_customer_cart(st.session_state.active_customer_id)
            st.toast(f"{product.name} quantity updated in cart." if merged else f"{product.name} added to cart.")
            st.rerun()
    product_info_panel(product)



def cart_item_included(item: dict[str, Any]) -> bool:
    return bool(item.get("included_in_quote", True))


def included_cart_items(cart: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    source = st.session_state.cart if cart is None else cart
    return [item for item in source if cart_item_included(item)]


def cart_subtotal(cart: list[dict[str, Any]] | None = None) -> float:
    return sum(float(item.get("line_total", 0.0) or 0.0) for item in included_cart_items(cart))

def cart_metrics() -> tuple[float, float, float]:
    subtotal = cart_subtotal()
    discount, _ = cart_discount(subtotal)
    discounted_subtotal = max(subtotal - discount, 0.0)
    tax_rate = quote_tax_rate()
    tax = discounted_subtotal * tax_rate
    return subtotal, tax, discounted_subtotal + tax + quote_installation_fee() + quote_shipping_fee()


def quote_adjustment_snapshot() -> dict[str, Any]:
    subtotal = cart_subtotal()
    discount, discount_label = cart_discount(subtotal)
    installation_fee = quote_installation_fee()
    shipping_fee = quote_shipping_fee()
    tax_rate = quote_tax_rate()
    discounted_subtotal = max(subtotal - discount, 0.0)
    tax = discounted_subtotal * tax_rate
    return {
        "subtotal": subtotal,
        "discount": discount,
        "discount_label": discount_label or "Discount",
        "installation_fee": installation_fee,
        "shipping_fee": shipping_fee,
        "shipping_enabled": bool(st.session_state.get("quote_shipping_enabled", False)),
        "tax_rate": tax_rate,
        "tax_rate_percent": tax_rate * 100,
        "tax": tax,
        "total": discounted_subtotal + tax + installation_fee + shipping_fee,
        "discount_type": st.session_state.get("quote_discount_type", "No discount"),
        "discount_value": quote_discount_raw_value(),
        "tax_enabled": bool(st.session_state.get("quote_sales_tax_enabled", False)),
    }


def cart_page() -> None:
    merged_cart, merged_changed = merge_duplicate_cart_items(st.session_state.cart)
    if merged_changed:
        st.session_state.cart = merged_cart
        save_customer_cart(st.session_state.active_customer_id)
    st.title("Your project cart")
    st.caption("Review configured products before creating the customer quote.")
    customers = customer_rows()
    customer_options = [0] + [int(row["id"]) for row in customers]
    selected_customer = st.selectbox(
        "Cart customer",
        customer_options,
        index=customer_options.index(st.session_state.active_customer_id) if st.session_state.active_customer_id in customer_options else 0,
        format_func=lambda value: "No customer selected" if value == 0 else next(row["name"] for row in customers if row["id"] == value),
        help="Choose the customer you are shopping for. Their saved cart will load here.",
    )
    if selected_customer != (st.session_state.active_customer_id or 0):
        set_active_customer(selected_customer or None)
        st.rerun()
    if st.session_state.active_customer_id:
        st.success(f"Current cart is linked to {customer_display_name(st.session_state.active_customer_id)}.")
    if not st.session_state.cart:
        st.markdown('<div class="empty"><h3>Your cart is empty</h3><p>Choose a door or window, enter its size, and add it here.</p></div>', unsafe_allow_html=True)
        if st.button("Browse products", type="primary"):
            st.session_state.page = "Catalog"
            st.rerun()
        return
    items_col, summary_col = st.columns([2.2, 0.8], gap="large")
    with items_col:
        cart_changed = False
        for index, item in enumerate(st.session_state.cart):
            cart_changed = normalize_cart_item(item, index) or cart_changed
            product = get_product_or_none(str(item.get("product_id") or ""))
            if product is None:
                st.warning(f"A cart item references a deleted product ({item.get('product_id')}). It was removed from this cart.")
                st.session_state.cart.pop(index)
                save_customer_cart(st.session_state.active_customer_id)
                st.rerun()
            line_id = str(item["line_id"])
            with st.container(border=True):
                image, info, action = st.columns([0.85, 2.6, 0.65], vertical_alignment="center")
                with image:
                    st.image(str(image_path(product, "hero")), width="stretch")
                with info:
                    included = cart_item_included(item)
                    color_label = item_color_label(item)
                    color_line = f" · {color_label}" if color_label else ""
                    area_sqft = float(item.get("area_sqft") or (float(item.get("width") or 0) * float(item.get("height") or 0) / 144))
                    item_summary = (
                        f"**{item['name']}**  \n"
                        f'{item["width"]:.1f}" W × {item["height"]:.1f}" H · {area_sqft:.2f} sq ft · {item["direction"]}  \n'
                        f"{item['glass']} glass · {item['frame']} finish{color_line} · Qty {item['quantity']}"
                    )
                    if included:
                        st.markdown(item_summary)
                    else:
                        st.markdown(
                            f"<div style='opacity:.42'><b>{html.escape(str(item['name']))}</b><br/>"
                            f"{float(item['width']):.1f}&quot; W × {float(item['height']):.1f}&quot; H · {area_sqft:.2f} sq ft · {html.escape(str(item['direction']))}<br/>"
                            f"{html.escape(str(item['glass']))} glass · {html.escape(str(item['frame']))} finish{html.escape(color_line)} · Qty {int(item['quantity'])}</div>",
                            unsafe_allow_html=True,
                        )
                        st.caption("Excluded from quote / order total")
                    edit_state_key = f"cart-edit-{line_id}"
                    if st.session_state.get(edit_state_key, False):
                        direction_options = option_tuple_with_current(product.directions, str(item.get("direction") or ""))
                        glass_options = option_tuple_with_current(product.glass_colors, str(item.get("glass") or ""))
                        frame_options = option_tuple_with_current(product.frame_colors, str(item.get("frame") or ""))
                        color_options = option_tuple_with_current(product.color_options or product.frame_colors, str(item.get("color") or ""))
                        edit_size_cols = st.columns([1, 1, 0.8])
                        with edit_size_cols[0]:
                            cart_width = st.number_input(
                                "Width (inches)",
                                min_value=12.0,
                                max_value=360.0,
                                value=float(item.get("width") or 12.0),
                                step=0.5,
                                key=f"cart-width-{line_id}",
                            )
                        with edit_size_cols[1]:
                            cart_height = st.number_input(
                                "Height (inches)",
                                min_value=12.0,
                                max_value=240.0,
                                value=float(item.get("height") or 12.0),
                                step=0.5,
                                key=f"cart-height-{line_id}",
                            )
                        with edit_size_cols[2]:
                            cart_quantity = st.number_input(
                                "Qty",
                                min_value=1,
                                max_value=99,
                                value=int(item.get("quantity") or 1),
                                step=1,
                                key=f"cart-qty-{line_id}",
                            )
                        edit_option_cols = st.columns(4)
                        with edit_option_cols[0]:
                            cart_direction = st.selectbox(
                                "Opening / handling",
                                direction_options,
                                index=option_index(direction_options, str(item.get("direction") or "")),
                                key=f"cart-direction-{line_id}",
                            )
                        with edit_option_cols[1]:
                            cart_glass = st.selectbox(
                                "Glass",
                                glass_options,
                                index=option_index(glass_options, str(item.get("glass") or "")),
                                key=f"cart-glass-{line_id}",
                            )
                        with edit_option_cols[2]:
                            cart_frame = st.selectbox(
                                "Frame / finish",
                                frame_options,
                                index=option_index(frame_options, str(item.get("frame") or "")),
                                key=f"cart-frame-{line_id}",
                            )
                        with edit_option_cols[3]:
                            cart_color = st.selectbox(
                                "Color",
                                color_options,
                                index=option_index(color_options, str(item.get("color") or "")),
                                key=f"cart-color-{line_id}",
                            )
                        cart_notes = st.text_input("Item notes", value=str(item.get("notes") or ""), key=f"cart-notes-{line_id}")
                        edited_area_sqft = float(cart_width) * float(cart_height) / 144
                        st.caption(f"Area: {edited_area_sqft:.2f} sq ft")
                        if update_cart_item_configuration(
                            item,
                            product,
                            cart_width,
                            cart_height,
                            int(cart_quantity),
                            direction=str(cart_direction),
                            glass=str(cart_glass),
                            frame=str(cart_frame),
                            color=str(cart_color),
                            notes=str(cart_notes),
                        ):
                            save_customer_cart(st.session_state.active_customer_id)
                            st.rerun()
                    stock_label, stock_color = inventory_status_text(
                        str(item.get("product_id") or ""),
                        requested=int(item.get("quantity") or 1),
                        color=str(item.get("color") or ""),
                    )
                    st.markdown(f"<span style='color:{stock_color};font-weight:700'>{stock_label}</span>", unsafe_allow_html=True)
                    if item["notes"]:
                        st.caption(item["notes"])
                    price_col, total_col, reset_col = st.columns([1, 1, 0.8], vertical_alignment="bottom")
                    price_widget_key = f"unit-price-{line_id}"
                    price_sync_key = f"unit-price-sync-{line_id}"
                    item_unit_price = float(item.get("unit_price", 0.0) or 0.0)
                    last_synced_price = float(st.session_state.get(price_sync_key, item_unit_price) or 0.0)
                    widget_price = st.session_state.get(price_widget_key)
                    if widget_price is None or (abs(last_synced_price - item_unit_price) > 0.005 and abs(float(widget_price or 0.0) - last_synced_price) <= 0.005):
                        st.session_state[price_widget_key] = item_unit_price
                    st.session_state[price_sync_key] = item_unit_price
                    with price_col:
                        adjusted_unit = st.number_input(
                            "Unit price for quote",
                            min_value=0.0,
                            step=10.0,
                            key=price_widget_key,
                            help="Adjust this item only. The PDF quote will use this price.",
                        )
                    if adjusted_unit != float(item.get("unit_price", 0.0) or 0.0):
                        sync_cart_item_price(item, adjusted_unit)
                        st.session_state[price_sync_key] = float(adjusted_unit)
                        save_customer_cart(st.session_state.active_customer_id)
                    with total_col:
                        st.markdown(f"**Line total**  \n{money(float(item['line_total']))}")
                    with reset_col:
                        if item.get("price_adjusted") and st.button("Reset price", key=f"reset-price-{line_id}"):
                            sync_cart_item_price(item, float(item.get("original_unit_price", item["unit_price"])))
                            save_customer_cart(st.session_state.active_customer_id)
                            st.rerun()
                    if item.get("price_adjusted"):
                        st.caption(f"Original calculated unit price: {money(float(item.get('original_unit_price', 0.0)))}")
                with action:
                    include_key = f"include-{line_id}"
                    if include_key not in st.session_state:
                        st.session_state[include_key] = cart_item_included(item)
                    include_item = st.checkbox("Include", key=include_key, help="Only included items are counted in quote totals.")
                    if include_item != cart_item_included(item):
                        item["included_in_quote"] = bool(include_item)
                        save_customer_cart(st.session_state.active_customer_id)
                        st.rerun()
                    edit_state_key = f"cart-edit-{line_id}"
                    edit_label = "Done" if st.session_state.get(edit_state_key, False) else "Edit"
                    if st.button(edit_label, key=f"edit-{line_id}", type="secondary"):
                        st.session_state[edit_state_key] = not st.session_state.get(edit_state_key, False)
                        st.rerun()
                    if st.button("Remove", key=f"remove-{line_id}", type="tertiary"):
                        st.session_state.cart.pop(index)
                        save_customer_cart(st.session_state.active_customer_id)
                        st.rerun()
        if cart_changed:
            save_customer_cart(st.session_state.active_customer_id)
    with summary_col:
        st.markdown("#### Quote price adjustment")
        st.selectbox(
            "Total discount",
            ("No discount", "Percent %", "Amount $"),
            key="quote_discount_type",
            help="Apply one discount to the whole cart before generating the PDF quote.",
        )
        if st.session_state.quote_discount_type == "Percent %":
            if "quote_discount_percent_value" not in st.session_state:
                st.session_state.quote_discount_percent_value = min(max(float(st.session_state.get("quote_discount_value", 0.0) or 0.0), 0.0), 100.0)
            st.number_input("Discount percent", min_value=0.0, max_value=100.0, step=1.0, key="quote_discount_percent_value")
        elif st.session_state.quote_discount_type == "Amount $":
            if "quote_discount_amount_value" not in st.session_state:
                st.session_state.quote_discount_amount_value = max(float(st.session_state.get("quote_discount_value", 0.0) or 0.0), 0.0)
            st.number_input("Discount amount", min_value=0.0, step=50.0, key="quote_discount_amount_value")
        else:
            st.session_state.quote_discount_value = 0.0
        st.markdown("#### Installation")
        st.number_input(
            "Installation fee ($)",
            min_value=0.0,
            value=float(st.session_state.quote_installation_fee),
            step=50.0,
            key="quote_installation_fee",
            help="Enter the installation/labor amount to add to this quote.",
        )
        st.markdown("#### Shipping")
        st.checkbox(
            "Charge shipping",
            key="quote_shipping_enabled",
            help="Turn this on only when this quote should include a shipping/delivery charge.",
        )
        if st.session_state.get("quote_shipping_enabled", False):
            st.number_input(
                "Shipping fee ($)",
                min_value=0.0,
                value=float(st.session_state.quote_shipping_fee),
                step=50.0,
                key="quote_shipping_fee",
                help="Enter the shipping or delivery amount to add to this quote.",
            )
        st.markdown("#### Sales tax")
        st.checkbox(
            f"Calculate sales tax ({FIXED_SALES_TAX_RATE * 100:.2f}%)",
            key="quote_sales_tax_enabled",
            help="Turn this off for tax-exempt customers or orders that should not include sales tax.",
        )
        adjustment_snapshot = quote_adjustment_snapshot()
        st.session_state.checkout_quote_adjustments = adjustment_snapshot
        subtotal = float(adjustment_snapshot["subtotal"])
        discount = float(adjustment_snapshot["discount"])
        discount_label = str(adjustment_snapshot["discount_label"])
        installation_fee = float(adjustment_snapshot["installation_fee"])
        shipping_fee = float(adjustment_snapshot.get("shipping_fee") or 0.0)
        tax = float(adjustment_snapshot["tax"])
        total = float(adjustment_snapshot["total"])
        tax_label = quote_tax_label()
        tax_summary_line = (
            f'<div style="display:flex;justify-content:space-between;margin-top:10px"><span class="muted">{tax_label}</span><span>{money(tax)}</span></div>'
            if tax
            else ""
        )
        shipping_summary_line = (
            f'<div style="display:flex;justify-content:space-between;margin-top:10px"><span class="muted">Shipping</span><span>{money(shipping_fee)}</span></div>'
            if shipping_fee
            else ""
        )
        st.markdown(
            f"""
            <div class="summary-card">
              <div class="eyebrow" style="color:#b9c7bf">Project summary</div>
              <div style="display:flex;justify-content:space-between;margin-top:18px"><span class="muted">Products included</span><span>{len(included_cart_items())} / {len(st.session_state.cart)}</span></div>
              <div style="display:flex;justify-content:space-between;margin-top:10px"><span class="muted">Subtotal</span><span>{money(subtotal)}</span></div>
              <div style="display:flex;justify-content:space-between;margin-top:10px"><span class="muted">{discount_label or 'Discount'}</span><span>{'-' + money(discount) if discount else money(0)}</span></div>
              {tax_summary_line}
              {shipping_summary_line}
              <div style="display:flex;justify-content:space-between;margin-top:10px"><span class="muted">Installation</span><span>{money(installation_fee)}</span></div>
              <div style="border-top:1px solid #536159;margin-top:18px;padding-top:16px"><span class="muted">Estimated total</span><div class="total">{money(total)}</div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("")
        if st.button("Create customer quote", type="primary", width="stretch", disabled=not included_cart_items()):
            st.session_state.checkout_quote_adjustments = quote_adjustment_snapshot()
            save_customer_cart(st.session_state.active_customer_id)
            st.session_state.page = "Checkout"
            st.rerun()
        if st.session_state.active_customer_id and st.button("Save cart to this customer", width="stretch"):
            save_customer_cart(st.session_state.active_customer_id)
            st.success("Customer cart saved.")
        if st.button("Continue shopping", width="stretch"):
            st.session_state.page = "Catalog"
            st.rerun()


def quote_number() -> str:
    now = datetime.now()
    return f"Q-{now:%Y%m%d}-{now:%H%M%S%f}-{secrets.token_hex(2).upper()}"


def quote_item_thumbnail(item: dict[str, Any]) -> RLImage | str:
    try:
        product = get_product(str(item.get("product_id", "")))
        path = image_path(product, "hero")
    except Exception:
        path = None
    if not path or not path.exists():
        return ""
    thumbnail = RLImage(str(path), width=0.82 * inch, height=0.55 * inch)
    thumbnail.hAlign = "CENTER"
    return thumbnail


def company_logo_flowable(width: float = 2.85 * inch) -> RLImage | Paragraph:
    if COMPANY_LOGO_PATH.exists():
        with Image.open(COMPANY_LOGO_PATH) as logo:
            aspect = logo.height / logo.width
        return RLImage(str(COMPANY_LOGO_PATH), width=width, height=width * aspect)
    styles = getSampleStyleSheet()
    return Paragraph(f"<b>{COMPANY_NAME}</b>", styles["Normal"])


def pdf_text(value: Any, fallback: str = "-") -> str:
    text = str(value or "").strip()
    return html.escape(text).replace("\n", "<br/>") if text else fallback


def branded_pdf_header(document_label: str, document_number: str, styles: dict[str, ParagraphStyle]) -> Table:
    header = Table(
        [
            [
                [
                    company_logo_flowable(),
                ],
                Paragraph(
                    f"<font color='{BRAND_BLUE}'><b>{document_label}</b></font><br/><font size=9 color='#5f6f86'>{document_number}</font>",
                    styles["RightSmall"],
                ),
            ]
        ],
        colWidths=[4.7 * inch, 2.2 * inch],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, colors.HexColor(BRAND_LINE)),
            ]
        )
    )
    return header


def build_quote_pdf(quote: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=f"Quote {quote['quote_number']}",
        author=COMPANY_NAME,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Tiny", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=11, textColor=colors.HexColor("#5f6f86")))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontName="Helvetica", fontSize=9.5, leading=13, textColor=colors.HexColor("#1f2a44")))
    styles.add(ParagraphStyle(name="RightSmall", parent=styles["Small"], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="QuoteTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=25, leading=30, textColor=colors.HexColor(BRAND_BLUE), alignment=TA_LEFT))
    story = []
    header = branded_pdf_header("QUOTE", quote["quote_number"], styles)
    story.extend([header, Spacer(1, 18)])
    customer = quote["customer"]
    bill_to = Paragraph(
        f"<font size=8 color='{BRAND_BLUE}'>PREPARED FOR</font><br/><b>{pdf_text(customer.get('name'))}</b><br/>{pdf_text(customer.get('address'))}<br/>{pdf_text(customer.get('phone'))}<br/>{pdf_text(customer.get('email'))}",
        styles["Small"],
    )
    details = Paragraph(
        f"<font size=8 color='{BRAND_BLUE}'>QUOTE DETAILS</font><br/><b>Date:</b> {quote['created_at']}<br/><b>Valid until:</b> {quote['valid_until']}<br/><b>Status:</b> Estimate",
        styles["Small"],
    )
    info = Table([[bill_to, details]], colWidths=[4.5 * inch, 2.4 * inch])
    info.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 18)]))
    story.append(info)
    data = [[Paragraph("<b>IMAGE</b>", styles["Tiny"]), Paragraph("<b>PRODUCT / CONFIGURATION</b>", styles["Tiny"]), Paragraph("<b>QTY</b>", styles["Tiny"]), Paragraph("<b>UNIT</b>", styles["Tiny"]), Paragraph("<b>AMOUNT</b>", styles["Tiny"])]]
    for item in quote["items"]:
        description = (
            f"<b>{pdf_text(item.get('name'))}</b><br/>"
            f"{float(item.get('width') or 0):.1f}\" W x {float(item.get('height') or 0):.1f}\" H | {pdf_text(item.get('direction'))}<br/>"
            f"{pdf_text(item.get('glass'))} glass | {pdf_text(item.get('frame'))} finish"
        )
        color_label = item_color_label(item)
        if color_label:
            description += f" | {pdf_text(color_label)}"
        if item.get("notes"):
            description += f"<br/><font color='#68736d'>Note: {pdf_text(item.get('notes'))}</font>"
        data.append([
            quote_item_thumbnail(item),
            Paragraph(description, styles["Small"]),
            Paragraph(str(item["quantity"]), styles["Small"]),
            Paragraph(money(item["unit_price"]), styles["RightSmall"]),
            Paragraph(money(item["line_total"]), styles["RightSmall"]),
        ])
    item_table = Table(data, colWidths=[0.95 * inch, 3.45 * inch, 0.5 * inch, 0.9 * inch, 1.1 * inch], repeatRows=1)
    item_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BRAND_LIGHT)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(BRAND_BLUE)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#D7E3EE")),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.extend([item_table, Spacer(1, 14)])
    discount_amount = float(quote.get("discount", 0.0) or 0.0)
    tax_amount = float(quote.get("tax", 0.0) or 0.0)
    installation_amount = float(quote.get("installation_fee", 0.0) or 0.0)
    shipping_amount = float(quote.get("shipping_fee", 0.0) or 0.0)
    total_rows = [
        ["Subtotal", money(quote["subtotal"])],
    ]
    if discount_amount > 0:
        total_rows.append([quote.get("discount_label") or "Discount", f"-{money(discount_amount)}"])
    total_rows.extend(
        [
            [f"Sales tax ({float(quote.get('tax_rate', 0.0) or 0.0):.2f}%)", money(tax_amount)],
        ]
    )
    if shipping_amount > 0:
        total_rows.append(["Shipping", money(shipping_amount)])
    total_rows.extend(
        [
            ["Installation", money(installation_amount)],
        ]
    )
    total_rows.extend(
        [
            [Paragraph("<b>ESTIMATED TOTAL</b>", styles["Small"]), Paragraph(f"<b>{money(quote['total'])}</b>", styles["RightSmall"])],
        ]
    )
    totals = Table(
        total_rows,
        colWidths=[1.55 * inch, 1.4 * inch],
        hAlign="RIGHT",
    )
    total_index = len(total_rows) - 1
    totals.setStyle(TableStyle([("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("LINEABOVE", (0, total_index), (-1, total_index), 1.2, colors.HexColor(BRAND_BLUE))]))
    story.extend([totals, Spacer(1, 24)])
    story.append(Paragraph("<b>Notes and terms</b>", styles["Small"]))
    story.append(Paragraph("This document is an estimate based on the dimensions and options provided. Final pricing is subject to field verification, engineering review, delivery, installation requirements, applicable taxes, and written order confirmation. Product images are illustrative.", styles["Tiny"]))
    if quote.get("project_notes"):
        story.extend([Spacer(1, 8), Paragraph(f"<b>Project notes:</b> {quote['project_notes']}", styles["Tiny"])])
    doc.build(story)
    return buffer.getvalue()


def receipt_product_description(item: dict[str, Any]) -> str:
    details = []
    if item.get("width") and item.get("height"):
        details.append(f"{float(item['width']):.1f}\" W x {float(item['height']):.1f}\" H")
    if item.get("direction"):
        details.append(str(item["direction"]))
    if item.get("glass"):
        details.append(f"{item['glass']} glass")
    if item.get("frame"):
        details.append(f"{item['frame']} frame")
    color_label = item_color_label(item)
    if color_label:
        details.append(color_label)
    description = f"<b>{item.get('name') or item.get('product_id') or 'Product'}</b>"
    if details:
        description += "<br/>" + " | ".join(details)
    if item.get("notes"):
        description += f"<br/><font color='#5f6f86'>Note: {item['notes']}</font>"
    return description


def build_receipt_pdf(
    customer: sqlite3.Row,
    summary: dict[str, float | str],
    first_due: float,
    second_due: float,
    ordered_items: list[dict[str, Any]] | None = None,
) -> bytes:
    buffer = io.BytesIO()
    receipt_number = str(summary.get("quote_number") or f"ORDER-{customer['id']}")
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=f"Receipt {receipt_number}",
        author=COMPANY_NAME,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Tiny", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=11, textColor=colors.HexColor("#5f6f86")))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontName="Helvetica", fontSize=9.5, leading=13, textColor=colors.HexColor("#1f2a44")))
    styles.add(ParagraphStyle(name="RightSmall", parent=styles["Small"], alignment=TA_RIGHT))
    story: list[Any] = [branded_pdf_header("RECEIPT", receipt_number, styles), Spacer(1, 18)]
    bill_to = Paragraph(
        f"<font size=8 color='{BRAND_BLUE}'>CUSTOMER</font><br/><b>{customer['name']}</b><br/>{(customer['address'] or 'Not set').replace(chr(10), '<br/>')}<br/>{customer['phone'] or ''}<br/>{customer['email'] or ''}",
        styles["Small"],
    )
    details = Paragraph(
        f"<font size=8 color='{BRAND_BLUE}'>ORDER DETAILS</font><br/><b>Order date:</b> {display_date(customer['order_date'])}<br/><b>Status:</b> Receipt",
        styles["Small"],
    )
    info = Table([[bill_to, details]], colWidths=[4.5 * inch, 2.4 * inch])
    info.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 18)]))
    story.append(info)
    ordered_items = ordered_items or []
    if ordered_items:
        product_rows = [[Paragraph("<b>ORDERED PRODUCTS</b>", styles["Tiny"]), Paragraph("<b>QTY</b>", styles["Tiny"]), Paragraph("<b>UNIT</b>", styles["Tiny"]), Paragraph("<b>AMOUNT</b>", styles["Tiny"])]]
        for item in ordered_items:
            quantity = int(item.get("quantity") or 1)
            line_total = float(item.get("line_total") or 0)
            unit_price = float(item.get("unit_price") or (line_total / quantity if quantity else 0))
            product_rows.append(
                [
                    Paragraph(receipt_product_description(item), styles["Small"]),
                    Paragraph(str(quantity), styles["Small"]),
                    Paragraph(money(unit_price), styles["RightSmall"]),
                    Paragraph(money(line_total), styles["RightSmall"]),
                ]
            )
        products_table = Table(product_rows, colWidths=[4.15 * inch, 0.55 * inch, 1.0 * inch, 1.2 * inch], repeatRows=1)
        products_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BRAND_LIGHT)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(BRAND_BLUE)),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#D7E3EE")),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ]
            )
        )
        story.extend([products_table, Spacer(1, 14)])
    rows = [
        ["Items subtotal", money(float(summary["subtotal"]))],
        ["Discount", f"-{money(float(summary['discount']))}" if float(summary["discount"]) else money(0)],
        [f"Sales tax ({float(summary['tax_rate']):.2f}%)", money(float(summary["tax"]))],
    ]
    shipping_amount = float(summary.get("shipping") or 0)
    if shipping_amount > 0:
        rows.append(["Shipping", money(shipping_amount)])
    rows.extend(
        [
            ["Installation", money(float(summary["installation"]))],
            [Paragraph("<b>ORDER TOTAL</b>", styles["Small"]), Paragraph(f"<b>{money(float(summary['total']))}</b>", styles["RightSmall"])],
        ]
    )
    table = Table(rows, colWidths=[2.0 * inch, 1.45 * inch], hAlign="RIGHT")
    total_row_index = len(rows) - 1
    table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEABOVE", (0, total_row_index), (-1, total_row_index), 1.2, colors.HexColor(BRAND_BLUE)),
            ]
        )
    )
    story.extend([table, Spacer(1, 18)])
    first_paid = bool(int(row_value(customer, "first_payment_paid", 0) or 0))
    second_enabled = bool(int(row_value(customer, "second_payment_enabled", 1) or 0))
    second_paid = bool(int(row_value(customer, "second_payment_paid", 0) or 0)) if second_enabled else False
    paid_total = (float(first_due) if first_paid else 0.0) + (float(second_due) if second_paid else 0.0)
    balance_due = max(float(summary["total"]) - paid_total, 0.0)
    payment_rows = [
        [f"First payment ({display_date(customer['first_payment_date'])}) · {'Paid' if first_paid else 'Unpaid'}", money(first_due)],
        [
            f"Second payment ({display_date(customer['second_payment_date'])}) · {'Paid' if second_paid else 'Unpaid'}" if second_enabled else "Second payment · Not required",
            money(second_due) if second_enabled else money(0),
        ],
        ["Paid total", money(paid_total)],
        [Paragraph("<b>BALANCE DUE</b>", styles["Small"]), Paragraph(f"<b>{money(balance_due)}</b>", styles["RightSmall"])],
    ]
    payment_table = Table(payment_rows, colWidths=[2.0 * inch, 1.45 * inch], hAlign="RIGHT")
    payment_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BRAND_LIGHT)),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor(BRAND_BLUE)),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#D7E3EE")),
                ("LINEABOVE", (0, -1), (-1, -1), 1.0, colors.HexColor(BRAND_BLUE)),
            ]
        )
    )
    story.extend([Paragraph("<b>Payment schedule</b>", styles["Small"]), Spacer(1, 6), payment_table, Spacer(1, 18)])
    story.append(Paragraph("Thank you for your order. This receipt reflects the current order summary saved in the internal sales system.", styles["Tiny"]))
    doc.build(story)
    return buffer.getvalue()


def inch_to_mm(value: Any) -> int:
    try:
        return round(float(value or 0) * 25.4)
    except (TypeError, ValueError):
        return 0


def factory_production_quantity(item: dict[str, Any]) -> int:
    short_quantity = int(item.get("inventory_short_quantity") or 0)
    if short_quantity > 0:
        return short_quantity
    return int(item.get("quantity") or 1)


def factory_product_notes(item: dict[str, Any]) -> str:
    notes = []
    if item.get("notes"):
        notes.append(str(item["notes"]))
    deducted = int(item.get("inventory_deducted_quantity") or 0)
    short = int(item.get("inventory_short_quantity") or 0)
    if short:
        notes.append(f"Out of stock / produce {short}. Stock deducted: {deducted}.")
    return " ".join(notes) or "-"


def build_factory_production_pdf(
    customer: sqlite3.Row,
    production_items: list[dict[str, Any]],
    order_day: date | None = None,
) -> bytes:
    order_day = order_day or date.today()
    target_day = order_day + timedelta(days=70)
    document_number = f"PROD-{customer['id']}-{order_day.strftime('%Y%m%d')}"
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=0.35 * inch,
        leftMargin=0.35 * inch,
        topMargin=0.35 * inch,
        bottomMargin=0.35 * inch,
        title=f"Factory Production Order {document_number}",
        author=COMPANY_NAME,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Tiny", parent=styles["Normal"], fontName="Helvetica", fontSize=6.5, leading=8, textColor=colors.HexColor("#516070")))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor("#1f2a44")))
    styles.add(ParagraphStyle(name="RightSmall", parent=styles["Small"], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="HeaderCell", parent=styles["Tiny"], fontName="Helvetica-Bold", textColor=colors.white))
    story: list[Any] = [branded_pdf_header("FACTORY PRODUCTION ORDER", document_number, styles), Spacer(1, 10)]

    customer_info = Paragraph(
        f"<font size=7 color='{BRAND_BLUE}'>CUSTOMER / PROJECT</font><br/>"
        f"<b>{pdf_text(customer['name'])}</b><br/>"
        f"Phone: {pdf_text(customer['phone'])}<br/>"
        f"Email: {pdf_text(customer['email'])}<br/>"
        f"Address: {pdf_text(customer['address'])}",
        styles["Small"],
    )
    order_info = Paragraph(
        f"<font size=7 color='{BRAND_BLUE}'>PRODUCTION TIMING</font><br/>"
        f"<b>Order date:</b> {display_date(order_day.isoformat())}<br/>"
        f"<b>Target installation reminder:</b> {display_date(target_day.isoformat())}<br/>"
        f"<b>Reason:</b> no available stock / factory production required",
        styles["Small"],
    )
    info = Table([[customer_info, order_info]], colWidths=[5.2 * inch, 4.7 * inch])
    info.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story.append(info)

    rows: list[list[Any]] = [[
        Paragraph("ITEM", styles["HeaderCell"]),
        Paragraph("SERIES / PRODUCT", styles["HeaderCell"]),
        Paragraph("MATERIAL", styles["HeaderCell"]),
        Paragraph("THICK.", styles["HeaderCell"]),
        Paragraph("PROFILE COLOR", styles["HeaderCell"]),
        Paragraph("GLASS", styles["HeaderCell"]),
        Paragraph("OPEN STYLE", styles["HeaderCell"]),
        Paragraph("WIDTH MM", styles["HeaderCell"]),
        Paragraph("HEIGHT MM", styles["HeaderCell"]),
        Paragraph("AREA M²", styles["HeaderCell"]),
        Paragraph("QTY", styles["HeaderCell"]),
        Paragraph("TOTAL M²", styles["HeaderCell"]),
        Paragraph("OTHER DETAILS / NOTES", styles["HeaderCell"]),
    ]]
    total_area = 0.0
    total_qty = 0
    for index, item in enumerate(production_items, start=1):
        width_mm = inch_to_mm(item.get("width"))
        height_mm = inch_to_mm(item.get("height"))
        area_m2 = (width_mm * height_mm / 1_000_000) if width_mm and height_mm else 0.0
        qty = factory_production_quantity(item)
        line_area = area_m2 * qty
        total_area += line_area
        total_qty += qty
        other_details = (
            f"Screen: No<br/>"
            f"View: Outside view<br/>"
            f"Accessories: Standard<br/>"
            f"Packing: Wood crate<br/>"
            f"Architrave: No<br/>"
            f"Glass separate: No<br/>"
            f"Notes: {pdf_text(factory_product_notes(item))}"
        )
        rows.append(
            [
                Paragraph(str(index), styles["Small"]),
                Paragraph(pdf_text(item.get("name") or item.get("product_id")), styles["Small"]),
                Paragraph("Aluminum, Glass", styles["Small"]),
                Paragraph("2.0mm", styles["Small"]),
                Paragraph(pdf_text(item.get("frame") or item.get("color")), styles["Small"]),
                Paragraph(pdf_text(item.get("glass")), styles["Small"]),
                Paragraph(pdf_text(item.get("direction")), styles["Small"]),
                Paragraph(str(width_mm or "-"), styles["Small"]),
                Paragraph(str(height_mm or "-"), styles["Small"]),
                Paragraph(f"{area_m2:.2f}" if area_m2 else "-", styles["Small"]),
                Paragraph(str(qty), styles["Small"]),
                Paragraph(f"{line_area:.2f}" if line_area else "-", styles["Small"]),
                Paragraph(other_details, styles["Tiny"]),
            ]
        )
    rows.append(
        [
            Paragraph("<b>TOTAL</b>", styles["Small"]),
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            Paragraph(f"<b>{total_qty}</b>", styles["Small"]),
            Paragraph(f"<b>{total_area:.2f}</b>", styles["Small"]),
            "",
        ]
    )
    table = Table(
        rows,
        colWidths=[
            0.35 * inch,
            1.35 * inch,
            0.78 * inch,
            0.42 * inch,
            0.85 * inch,
            0.62 * inch,
            0.86 * inch,
            0.55 * inch,
            0.55 * inch,
            0.5 * inch,
            0.36 * inch,
            0.55 * inch,
            2.4 * inch,
        ],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BRAND_BLUE)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C8D6E3")),
                ("BACKGROUND", (0, 1), (-1, -2), colors.HexColor("#FBFDFF")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor(BRAND_LIGHT)),
                ("SPAN", (0, -1), (9, -1)),
                ("ALIGN", (0, -1), (9, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([table, Spacer(1, 8)])
    story.append(Paragraph("Factory notes: dimensions are converted from customer order inches to millimeters. Please confirm final engineering details before production.", styles["Tiny"]))
    doc.build(story)
    return buffer.getvalue()


def save_quote(quote: dict[str, Any]) -> None:
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO quotes
            (quote_number, created_at, customer_name, customer_email, customer_phone,
             customer_address, subtotal, tax, total, status, payload, customer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                quote["quote_number"],
                datetime.now().isoformat(),
                quote["customer"]["name"],
                quote["customer"]["email"],
                quote["customer"]["phone"],
                quote["customer"]["address"],
                quote["subtotal"],
                quote["tax"],
                quote["total"],
                "Created",
                json.dumps(quote),
                quote.get("customer_id"),
            ),
        )


def smtp_configured() -> bool:
    try:
        return all(key in st.secrets for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "FROM_EMAIL"))
    except Exception:
        return False


def default_quote_email_subject(quote: dict[str, Any]) -> str:
    return f"Your door and window quote {quote['quote_number']}"


def default_quote_email_body(quote: dict[str, Any]) -> str:
    return f"""Hello {quote['customer']['name']},

Thank you for the opportunity to quote your project.

Your estimated total is {money(quote['total'])}. The detailed quote is attached as a PDF.

Please reply to this email if you would like to make changes or proceed with the order.

FrameFlow Doors + Windows
"""


def send_quote_email(quote: dict[str, Any], pdf_bytes: bytes, subject: str, body: str) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = st.secrets["FROM_EMAIL"]
    message["To"] = quote["customer"]["email"]
    message.set_content(body)
    message.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=f"{quote['quote_number']}.pdf")
    with smtplib.SMTP(st.secrets["SMTP_HOST"], int(st.secrets["SMTP_PORT"])) as server:
        server.starttls()
        server.login(st.secrets["SMTP_USER"], st.secrets["SMTP_PASSWORD"])
        server.send_message(message)


def checkout_page() -> None:
    if not st.session_state.cart or not included_cart_items():
        st.session_state.page = "Cart"
        st.rerun()
    quote_items = included_cart_items()
    st.markdown('<div class="quote-head"><div class="eyebrow" style="color:#b9c7bf">Final step</div><h1 style="margin:5px 0;color:white">Create customer quote</h1><p style="color:#c4d0c9;margin:0">Enter customer details, review the estimate, then generate a PDF.</p></div>', unsafe_allow_html=True)
    form_col, review_col = st.columns([1.45, 0.75], gap="large")
    adjustment_snapshot = st.session_state.get("checkout_quote_adjustments") or quote_adjustment_snapshot()
    subtotal = float(adjustment_snapshot["subtotal"])
    discount = float(adjustment_snapshot["discount"])
    discount_label = str(adjustment_snapshot.get("discount_label") or "Discount")
    installation_fee = float(adjustment_snapshot["installation_fee"])
    shipping_fee = float(adjustment_snapshot.get("shipping_fee") or 0.0)
    tax = float(adjustment_snapshot["tax"])
    total = float(adjustment_snapshot["total"])
    tax_rate_percent = float(adjustment_snapshot["tax_rate_percent"])
    active_customer = customer_by_id(st.session_state.active_customer_id) if st.session_state.active_customer_id else None
    if active_customer:
        st.success(f"This quote will be saved under {active_customer['name']}.")
    with form_col:
        with st.form("customer-form"):
            st.markdown("### Customer information")
            name = st.text_input("Customer name *", value=active_customer["name"] if active_customer else "")
            company = st.text_input("Company", value=active_customer["company"] if active_customer else "")
            email = st.text_input("Email *", value=active_customer["email"] if active_customer else "")
            phone = st.text_input("Phone *", value=format_us_phone(active_customer["phone"]) if active_customer else "", placeholder="(123) 456-7890", help="Enter a 10-digit US phone number. It will be saved as (123) 456-7890.")
            address = st.text_area("Project / delivery address *", value=active_customer["address"] if active_customer else "")
            project_notes = st.text_area("Project notes")
            follow1, follow2 = st.columns(2)
            with follow1:
                first_followup = st.date_input("First follow-up", value=date.today())
            with follow2:
                second_followup = st.date_input("Second follow-up", value=date.today() + timedelta(days=7))
            st.caption("The quote is an estimate. Tax, shipping and installation can be confirmed before the final order.")
            create = st.form_submit_button("Generate quote", width="stretch")
            if create:
                if not name or "@" not in email or not phone or not address:
                    st.error("Please complete the required customer fields and enter a valid email.")
                elif not is_valid_us_phone(phone):
                    st.error("Please enter a 10-digit US phone number, for example (123) 456-7890.")
                elif second_followup < first_followup:
                    st.error("Second follow-up should be on or after the first follow-up.")
                else:
                    quote_items = included_cart_items()
                    if not quote_items:
                        st.error("Please include at least one cart item before generating a quote.")
                        return
                    final_adjustment_snapshot = st.session_state.get("checkout_quote_adjustments") or quote_adjustment_snapshot()
                    subtotal = float(final_adjustment_snapshot["subtotal"])
                    discount = float(final_adjustment_snapshot["discount"])
                    discount_label = str(final_adjustment_snapshot.get("discount_label") or "Discount")
                    installation_fee = float(final_adjustment_snapshot["installation_fee"])
                    shipping_fee = float(final_adjustment_snapshot.get("shipping_fee") or 0.0)
                    tax = float(final_adjustment_snapshot["tax"])
                    total = float(final_adjustment_snapshot["total"])
                    tax_rate_percent = float(final_adjustment_snapshot["tax_rate_percent"])
                    now = datetime.now()
                    customer_payload = {"name": name, "company": company, "email": email, "phone": format_us_phone(phone), "address": address}
                    quote_customer_id = st.session_state.active_customer_id
                    if active_customer and not customer_matches_checkout_payload(active_customer, customer_payload):
                        quote_customer_id = None
                    quote = {
                        "quote_number": quote_number(),
                        "created_at": now.strftime("%B %d, %Y"),
                        "valid_until": datetime.fromtimestamp(now.timestamp() + 30 * 86400).strftime("%B %d, %Y"),
                        "customer": customer_payload,
                        "items": [dict(item) for item in quote_items],
                        "subtotal": subtotal,
                        "discount": discount,
                        "discount_label": discount_label,
                        "tax_enabled": bool(final_adjustment_snapshot.get("tax_enabled", False)),
                        "tax_rate": tax_rate_percent,
                        "installation_fee": installation_fee,
                        "shipping_fee": shipping_fee,
                        "shipping_enabled": bool(final_adjustment_snapshot.get("shipping_enabled", False)),
                        "tax": tax,
                        "total": total,
                        "project_notes": project_notes,
                        "customer_id": quote_customer_id,
                    }
                    customer_id = upsert_customer_from_quote(customer_payload, quote, first_followup, second_followup)
                    quote["customer_id"] = customer_id
                    pdf = build_quote_pdf(quote)
                    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                    (OUTPUT_DIR / f"{quote['quote_number']}.pdf").write_bytes(pdf)
                    save_quote(quote)
                    set_active_customer(customer_id, load_cart=False)
                    save_customer_cart(customer_id)
                    st.session_state.last_quote = {"data": quote, "pdf": pdf}
                    st.success(f"Quote {quote['quote_number']} created and saved under {name}.")
    with review_col:
        st.markdown("### Quote review")
        for item in quote_items:
            color_label = item_color_label(item)
            color_note = f" · {color_label}" if color_label else ""
            st.markdown(f"**{item['name']} × {item['quantity']}**  \n{item['width']:.1f}\" × {item['height']:.1f}\"{color_note} · {money(item['line_total'])}")
            if item.get("price_adjusted"):
                st.caption(f"Adjusted unit price from {money(float(item.get('original_unit_price', item['unit_price'])))} to {money(float(item['unit_price']))}")
            st.divider()
        st.metric("Subtotal", money(subtotal))
        st.metric(discount_label or "Discount", f"-{money(discount)}" if discount else money(0))
        st.metric(f"Sales tax ({tax_rate_percent:.2f}%)", money(tax))
        if shipping_fee > 0:
            st.metric("Shipping", money(shipping_fee))
        st.metric("Installation", money(installation_fee))
        st.metric("Estimated total", money(total))
    if st.session_state.last_quote:
        quote = st.session_state.last_quote["data"]
        pdf = st.session_state.last_quote["pdf"]
        st.divider()
        st.markdown(f"### Quote ready: {quote['quote_number']}")
        download, send = st.columns(2)
        with download:
            st.download_button("Download quote PDF", data=pdf, file_name=f"{quote['quote_number']}.pdf", mime="application/pdf", width="stretch")
        with send:
            if smtp_configured():
                st.success(f"Email is ready to send from {st.secrets['FROM_EMAIL']} to {quote['customer']['email']}.")
            else:
                st.button("Email setup required", disabled=True, width="stretch")
                st.caption("Add your work email SMTP settings in `.streamlit/secrets.toml` before sending.")
        if smtp_configured():
            with st.form(f"quote-email-form-{quote['quote_number']}"):
                st.markdown("#### Email draft")
                st.caption(f"To: {quote['customer']['email']}")
                subject = st.text_input(
                    "Subject",
                    value=default_quote_email_subject(quote),
                    key=f"email-subject-{quote['quote_number']}",
                )
                body = st.text_area(
                    "Email message",
                    value=default_quote_email_body(quote),
                    height=230,
                    key=f"email-body-{quote['quote_number']}",
                )
                send_email = st.form_submit_button("Send email with PDF quote", type="primary", width="stretch")
                if send_email:
                    if not subject.strip() or not body.strip():
                        st.error("Email subject and message cannot be empty.")
                    else:
                        try:
                            send_quote_email(quote, pdf, subject.strip(), body.strip())
                            st.success("Quote email sent successfully.")
                        except Exception as exc:
                            st.error(f"Email could not be sent: {exc}")
                st.caption("Add SMTP settings to `.streamlit/secrets.toml` to enable sending.")


def quotes_page() -> None:
    st.title("Saved quotes")
    st.caption("Quotes generated on this computer are stored in the local SQLite database.")
    with db_connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT quotes.*, customers.name AS linked_customer_name
            FROM quotes
            LEFT JOIN customers ON customers.id = quotes.customer_id
            ORDER BY quotes.created_at DESC
            LIMIT 100
            """
        ).fetchall()
    if not rows:
        st.markdown('<div class="empty">No quotes yet. Create one from the cart.</div>', unsafe_allow_html=True)
        return
    for row in rows:
        with st.expander(f"{row['quote_number']} · {row['customer_name']} · {money(row['total'])}"):
            linked = row["linked_customer_name"] or "Not linked"
            st.write(f"**Linked customer:** {linked}  \n**Email:** {row['customer_email']}  \n**Phone:** {row['customer_phone']}  \n**Address:** {row['customer_address']}  \n**Status:** {row['status']}")
            path = OUTPUT_DIR / f"{row['quote_number']}.pdf"
            if path.exists():
                st.download_button("Download PDF", path.read_bytes(), file_name=path.name, mime="application/pdf", key=f"saved-{row['quote_number']}")


def product_editor(existing: Product | None, form_key: str) -> None:
    is_edit = existing is not None
    product = existing or Product(
        id="",
        section="Doors",
        category="Sliding Door",
        name="",
        subtitle="",
        description="",
        base_rate=100.0,
        minimum_price=500.0,
        directions=("Left opening", "Right opening"),
        glass_colors=("Clear", "Low-E", "Grey", "Bronze", "Frosted"),
        frame_colors=("Black", "White", "Charcoal", "Bronze"),
        color_options=("Black", "White", "Charcoal", "Bronze"),
        accent="#64746a",
    )
    with st.form(form_key):
        st.markdown("### Edit product" if is_edit else "### Add new product")
        identity1, identity2 = st.columns(2)
        with identity1:
            product_id = st.text_input("Product ID *", value=product.id, disabled=is_edit, help="Use a unique code such as SD-101.")
            section_options = ("Doors", "Windows", "Accessories")
            section = st.selectbox(
                "Section *",
                section_options,
                index=section_options.index(product.section) if product.section in section_options else 0,
            )
            category = st.text_input("Category *", value=product.category)
        with identity2:
            name = st.text_input("Product name *", value=product.name)
            subtitle = st.text_input("Short description", value=product.subtitle)
            active = st.checkbox("Visible in catalog", value=product.active)
        description = st.text_area("Full product description", value=product.description, height=110)
        price1, price2, color_col = st.columns(3)
        with price1:
            base_rate = st.number_input("Base rate / sq ft", min_value=0.0, value=float(product.base_rate), step=1.0)
        with price2:
            minimum_price = st.number_input("Minimum price", min_value=0.0, value=float(product.minimum_price), step=10.0)
        with color_col:
            accent = st.color_picker("Placeholder accent", value=product.accent)
        option1, option2, option3, option4 = st.columns(4)
        with option1:
            directions = st.text_area("Opening options", value="\n".join(product.directions), help="One option per line, or separate with commas.")
        with option2:
            glass_colors = st.text_area("Glass options", value="\n".join(product.glass_colors))
        with option3:
            frame_colors = st.text_area("Frame / finish options", value="\n".join(product.frame_colors))
        with option4:
            color_options = st.text_area("Color options", value="\n".join(product.color_options or product.frame_colors))
        st.markdown("#### Color and stock information")
        info1, info2 = st.columns(2)
        with info1:
            color_information = st.text_area(
                "Color information",
                value=product.color_information,
                height=110,
                placeholder="Available colors, lead times by color, finish notes...",
            )
        with info2:
            stock_information = st.text_area(
                "Stock information",
                value=product.stock_information,
                height=110,
                placeholder="In stock, made to order, warehouse notes, expected restock date...",
            )
        st.markdown("#### Product images")
        st.caption("All uploads are automatically centered, cropped and compressed to 1500 × 1000 pixels (3:2). The original file is kept as a backup.")
        image1, image2 = st.columns(2)
        with image1:
            hero_upload = st.file_uploader("Replace main product image", type=("png", "jpg", "jpeg", "webp"), key=f"{form_key}-hero")
            if is_edit and image_path(product, "hero").exists():
                st.image(str(image_path(product, "hero")), caption="Current main image", width="stretch")
        with image2:
            detail_uploads = st.file_uploader(
                "Add product detail images",
                type=("png", "jpg", "jpeg", "webp"),
                accept_multiple_files=True,
                key=f"{form_key}-details",
            )
            replace_details = st.checkbox("Replace all current detail images", value=False)
            if is_edit:
                st.caption(f"Current detail images: {len(detail_image_paths(product))}")
        submitted = st.form_submit_button("Save product", type="primary", width="stretch")
        if submitted:
            clean_id = safe_product_id(product_id)
            if not clean_id or not name.strip() or not category.strip():
                st.error("Product ID, product name and category are required.")
                return
            if not split_options(directions) or not split_options(glass_colors) or not split_options(frame_colors) or not split_options(color_options):
                st.error("Each product needs at least one opening, glass, finish and color option.")
                return
            if not is_edit and any(item.id == clean_id for item in PRODUCTS):
                st.error("That Product ID already exists.")
                return
            hero_image = product.hero_image
            details = list(product.detail_images)
            try:
                if hero_upload is not None:
                    hero_image = save_uploaded_image(hero_upload, clean_id, "hero")
                if detail_uploads:
                    uploaded_details = [
                        save_uploaded_image(upload, clean_id, f"detail-{index + 1}")
                        for index, upload in enumerate(detail_uploads)
                    ]
                    details = uploaded_details if replace_details else details + uploaded_details
            except Exception as exc:
                st.error(f"Image could not be saved: {exc}")
                return
            updated = seed_product_images(
                Product(
                    id=clean_id,
                    section=section,
                    category=category.strip(),
                    name=name.strip(),
                    subtitle=subtitle.strip(),
                    description=description.strip(),
                    base_rate=float(base_rate),
                    minimum_price=float(minimum_price),
                    directions=split_options(directions),
                    glass_colors=split_options(glass_colors),
                    frame_colors=split_options(frame_colors),
                    color_options=split_options(color_options),
                    accent=accent,
                    hero_image=hero_image,
                    detail_images=tuple(dict.fromkeys(details)),
                    active=active,
                    updated_at=datetime.now().isoformat(timespec="seconds"),
                    color_information=color_information.strip(),
                    stock_information=stock_information.strip(),
                )
            )
            updated_products = [item for item in PRODUCTS if item.id != clean_id]
            updated_products.append(updated)
            updated_products.sort(key=lambda item: (item.section, item.category, item.name))
            save_products(updated_products)
            reload_products()
            ensure_assets()
            st.session_state.admin_editor_id = clean_id
            st.success(f"{updated.name} has been saved.")
            st.rerun()


def admin_page() -> None:
    if not st.session_state.admin_authenticated:
        st.markdown('<div class="quote-head"><div class="eyebrow" style="color:#b9c7bf">Protected area</div><h1 style="margin:5px 0;color:white">Product administration</h1><p style="color:#c4d0c9;margin:0">Sign in to update product text, pricing, options and images.</p></div>', unsafe_allow_html=True)
        with st.form("admin-login"):
            password = st.text_input("Admin password", type="password")
            login = st.form_submit_button("Sign in", type="primary", width="stretch")
            if login:
                if secrets.compare_digest(password, admin_password()):
                    st.session_state.admin_authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
        return

    heading, logout = st.columns([5, 1], vertical_alignment="center")
    with heading:
        st.title("Product administration")
        st.caption("Changes are saved locally and appear in the product catalog immediately.")
    with logout:
        if st.button("Sign out", width="stretch"):
            st.session_state.admin_authenticated = False
            st.rerun()
    if admin_password() == "frameflow-admin":
        st.warning("You are using the temporary development password. Set ADMIN_PASSWORD in `.streamlit/secrets.toml` before publishing this website.")

    active_count = sum(product.active for product in PRODUCTS)
    m1, m2, m3 = st.columns(3)
    m1.metric("All products", len(PRODUCTS))
    m2.metric("Visible products", active_count)
    m3.metric("Uploaded images", len(list(UPLOAD_DIR.glob("*.webp"))) if UPLOAD_DIR.exists() else 0)

    edit_tab, add_tab = st.tabs(["Edit products", "Add product"])
    with edit_tab:
        if not PRODUCTS:
            st.info("There are no products yet. Use Add product to create one.")
        else:
            recent = (
                next((product for product in PRODUCTS if product.id == st.session_state.admin_editor_id), None)
                or most_recent_product()
            )
            if recent:
                recent_image = image_path(recent, "hero")
                recent_col, recent_text = st.columns([0.8, 4], vertical_alignment="center")
                with recent_col:
                    if recent_image.exists():
                        st.image(str(recent_image), width="stretch")
                with recent_text:
                    st.success(f"Recently edited: {recent.name} · {recent.id}")
                    st.caption(f"{recent.section} / {recent.category}")

            search = st.text_input(
                "Search products",
                placeholder="Search by product name, ID or category…",
                key="admin_product_search",
            ).strip().lower()
            filtered_products = [
                product
                for product in PRODUCTS
                if not search
                or search in product.name.lower()
                or search in product.id.lower()
                or search in product.category.lower()
                or search in product.section.lower()
            ]
            if not filtered_products:
                st.warning("No products match that search.")
                return
            product_ids = [product.id for product in filtered_products]
            preferred = st.session_state.admin_editor_id or (recent.id if recent else None)
            selected_index = product_ids.index(preferred) if preferred in product_ids else 0
            selected_id = st.selectbox(
                "Choose a product",
                product_ids,
                index=selected_index,
                format_func=lambda product_id: (
                    f"{get_product(product_id).name} · {product_id} · "
                    f"{get_product(product_id).section} / {get_product(product_id).category}"
                ),
            )
            st.session_state.admin_editor_id = selected_id
            product_editor(get_product(selected_id), f"edit-{selected_id}")
            st.divider()
            st.markdown("#### Delete product")
            confirm_delete = st.checkbox(f"I understand that {get_product(selected_id).name} will be removed from the catalog.", key=f"confirm-delete-{selected_id}")
            if st.button("Delete selected product", disabled=not confirm_delete, type="secondary", key=f"delete-{selected_id}"):
                remaining = [product for product in PRODUCTS if product.id != selected_id]
                save_products(remaining)
                st.session_state.cart = [item for item in st.session_state.cart if item["product_id"] != selected_id]
                st.session_state.admin_editor_id = None
                reload_products()
                st.success("Product deleted. Uploaded image files were kept as a safety backup.")
                st.rerun()
    with add_tab:
        product_editor(None, "add-product")


def about_page() -> None:
    st.empty()


def main() -> None:
    css()
    init_state()
    if not st.session_state.employee_authenticated:
        employee_login_page()
        st.markdown('<div class="footer">FRAMEFLOW · EMPLOYEE ACCESS REQUIRED</div>', unsafe_allow_html=True)
        return
    # Phone numbers are formatted on save/quote generation.
    # The live browser mask is disabled because it can interrupt Streamlit text input.
    init_db()
    reload_products()
    normalize_existing_catalog_images()
    ensure_assets()
    top_nav()
    if st.session_state.selected_product and any(product.id == st.session_state.selected_product and product.active for product in PRODUCTS):
        configure_page(get_product(st.session_state.selected_product))
    elif st.session_state.page == "Catalog":
        catalog_page()
    elif st.session_state.page == "Cart":
        cart_page()
    elif st.session_state.page == "Checkout":
        checkout_page()
    elif st.session_state.page == "Quotes":
        st.session_state.page = "Catalog"
        st.rerun()
    elif st.session_state.page == "Customers":
        customers_page()
    elif st.session_state.page == "Inventory":
        inventory_page()
    elif st.session_state.page == "After-sales":
        after_sales_page()
    elif st.session_state.page == "Finance":
        finance_page()
    elif st.session_state.page == "Admin":
        admin_page() if is_manager_user() else catalog_page()
    else:
        about_page()
    st.markdown('<div class="footer">FRAMEFLOW · INTERNAL TRADE PORTAL · PRICING SUBJECT TO FINAL REVIEW</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
