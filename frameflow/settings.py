from pathlib import Path


APP_DIR = Path(__file__).resolve().parent.parent
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
AUTH_STORAGE_KEY = "frameflow_employee_daily_auth_v1"
MAX_ORDER_QUANTITY = 1000

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

# Commission logic is prepared but intentionally disabled until inventory data is complete.
FINANCE_COMMISSION_ENABLED = False
STOCK_COMMISSION_RATE = 0.05
FACTORY_ORDER_COMMISSION_RATE = 0.08

DEPOSIT_REFUND_NOTICE = (
    "Deposit is non-refundable. Custom orders are not returnable or exchangeable "
    "once the deposit is paid, except as required by applicable law or agreed in "
    "writing by SUMMIT Windows & Doors."
)

