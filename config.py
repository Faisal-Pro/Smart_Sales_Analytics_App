import os

# App Information
APP_NAME = "Smart Sales & Inventory Analytics"
APP_VERSION = "1.1.0"

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# A single database file for the whole app.
# Can be overridden with the SMART_SALES_DB environment variable (used by the tests).
DB_PATH = os.environ.get(
    "SMART_SALES_DB", os.path.join(BASE_DIR, "database", "sales_inventory.db")
)

# Business rules
LOW_STOCK_THRESHOLD = 5  # products with stock <= this value are flagged
CURRENCY = "$"

# Theme Settings
APPEARANCE_MODE = "Light"  # "Light" or "Dark" (can also be toggled in the app)
COLOR_THEME = "green"
