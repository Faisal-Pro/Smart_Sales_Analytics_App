import os
import sqlite3
from contextlib import contextmanager

from config import DB_PATH


def get_connection():
    """Create a SQLite connection with foreign keys enforced."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    # SQLite does NOT enforce foreign keys unless this is enabled per connection.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session():
    """Open a connection; commit on success, roll back on error, always close."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Create tables/indexes if missing and migrate older databases."""
    with db_session() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                product_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT NOT NULL,
                category       TEXT NOT NULL,
                price          REAL NOT NULL CHECK (price >= 0),
                stock_quantity INTEGER NOT NULL CHECK (stock_quantity >= 0),
                cost_price     REAL NOT NULL CHECK (cost_price >= 0)
            );

            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                phone       TEXT,
                email       TEXT
            );

            CREATE TABLE IF NOT EXISTS sales (
                sale_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id  INTEGER,
                customer_id INTEGER,
                quantity    INTEGER NOT NULL CHECK (quantity > 0),
                total_price REAL NOT NULL CHECK (total_price >= 0),
                unit_cost   REAL,
                sale_date   TEXT NOT NULL,
                FOREIGN KEY (product_id)  REFERENCES products (product_id),
                FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
            );

            CREATE INDEX IF NOT EXISTS idx_sales_product  ON sales (product_id);
            CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales (customer_id);
            CREATE INDEX IF NOT EXISTS idx_sales_date     ON sales (sale_date);
            """
        )

        # Migration: older databases have no unit_cost column on sales.
        # It freezes the product's cost at the time of sale so profit stays
        # correct even if cost_price is edited later.
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(sales)")]
        if "unit_cost" not in cols:
            conn.execute("ALTER TABLE sales ADD COLUMN unit_cost REAL")
        conn.execute(
            """
            UPDATE sales
            SET unit_cost = (SELECT cost_price FROM products p
                             WHERE p.product_id = sales.product_id)
            WHERE unit_cost IS NULL
            """
        )


if __name__ == "__main__":
    init_database()
    print("[SUCCESS] Database schema initialized:", DB_PATH)
