import csv
import os
import sys
from datetime import datetime

# Allow `python database/db_operations.py` as well as normal package imports.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_manager import db_session, init_database  # noqa: E402


class DatabaseError(Exception):
    """User-presentable database/validation error."""


# ----------------------------------------------------------------- validation
def _clean_text(value, field, required=True):
    value = (value or "").strip()
    if required and not value:
        raise DatabaseError(f"{field} is required.")
    return value


def _number(value, field, integer=False, minimum=0, strictly_positive=False):
    try:
        num = int(value) if integer else float(value)
    except (TypeError, ValueError):
        kind = "a whole number" if integer else "a number"
        raise DatabaseError(f"{field} must be {kind}.")
    if num != num or num in (float("inf"), float("-inf")):
        raise DatabaseError(f"{field} is not a valid number.")
    if strictly_positive and num <= 0:
        raise DatabaseError(f"{field} must be greater than zero.")
    if num < minimum:
        raise DatabaseError(f"{field} cannot be negative.")
    return num


def _validate_email(email):
    email = (email or "").strip()
    if email and ("@" not in email or "." not in email.split("@")[-1]):
        raise DatabaseError("Email address is not valid.")
    return email


# ------------------------------------------------------------------- products
def add_product(name, category, price, stock_quantity, cost_price):
    name = _clean_text(name, "Product name")
    category = _clean_text(category, "Category")
    price = _number(price, "Price")
    stock_quantity = _number(stock_quantity, "Stock quantity", integer=True)
    cost_price = _number(cost_price, "Cost price")
    with db_session() as conn:
        cur = conn.execute(
            "INSERT INTO products (name, category, price, stock_quantity, cost_price) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, category, price, stock_quantity, cost_price),
        )
        return cur.lastrowid


def get_all_products(search=""):
    with db_session() as conn:
        if search:
            like = f"%{search.strip()}%"
            return conn.execute(
                "SELECT * FROM products WHERE name LIKE ? OR category LIKE ? "
                "ORDER BY product_id",
                (like, like),
            ).fetchall()
        return conn.execute("SELECT * FROM products ORDER BY product_id").fetchall()


def get_product(product_id):
    with db_session() as conn:
        return conn.execute(
            "SELECT * FROM products WHERE product_id = ?", (product_id,)
        ).fetchone()


def update_product(product_id, name, category, price, stock_quantity, cost_price):
    name = _clean_text(name, "Product name")
    category = _clean_text(category, "Category")
    price = _number(price, "Price")
    stock_quantity = _number(stock_quantity, "Stock quantity", integer=True)
    cost_price = _number(cost_price, "Cost price")
    with db_session() as conn:
        cur = conn.execute(
            "UPDATE products SET name=?, category=?, price=?, stock_quantity=?, "
            "cost_price=? WHERE product_id=?",
            (name, category, price, stock_quantity, cost_price, product_id),
        )
        if cur.rowcount == 0:
            raise DatabaseError("Product not found.")


def delete_product(product_id):
    with db_session() as conn:
        used = conn.execute(
            "SELECT COUNT(*) FROM sales WHERE product_id = ?", (product_id,)
        ).fetchone()[0]
        if used:
            raise DatabaseError(
                f"This product has {used} recorded sale(s) and cannot be deleted. "
                "Set its stock to 0 instead to keep your sales history intact."
            )
        conn.execute("DELETE FROM products WHERE product_id = ?", (product_id,))


# ------------------------------------------------------------------ customers
def add_customer(name, phone, email=""):
    name = _clean_text(name, "Customer name")
    phone = _clean_text(phone, "Phone", required=False)
    email = _validate_email(email)
    with db_session() as conn:
        cur = conn.execute(
            "INSERT INTO customers (name, phone, email) VALUES (?, ?, ?)",
            (name, phone, email),
        )
        return cur.lastrowid


def get_all_customers(search=""):
    with db_session() as conn:
        if search:
            like = f"%{search.strip()}%"
            return conn.execute(
                "SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? "
                "OR email LIKE ? ORDER BY customer_id",
                (like, like, like),
            ).fetchall()
        return conn.execute("SELECT * FROM customers ORDER BY customer_id").fetchall()


def update_customer(customer_id, name, phone, email=""):
    name = _clean_text(name, "Customer name")
    phone = _clean_text(phone, "Phone", required=False)
    email = _validate_email(email)
    with db_session() as conn:
        cur = conn.execute(
            "UPDATE customers SET name=?, phone=?, email=? WHERE customer_id=?",
            (name, phone, email, customer_id),
        )
        if cur.rowcount == 0:
            raise DatabaseError("Customer not found.")


def delete_customer(customer_id):
    with db_session() as conn:
        used = conn.execute(
            "SELECT COUNT(*) FROM sales WHERE customer_id = ?", (customer_id,)
        ).fetchone()[0]
        if used:
            raise DatabaseError(
                f"This customer has {used} recorded sale(s) and cannot be deleted."
            )
        conn.execute("DELETE FROM customers WHERE customer_id = ?", (customer_id,))


# ----------------------------------------------------------------- CSV import
def _import_csv(path, required, row_action):
    """Import rows from a CSV file. Valid rows are added; bad rows are reported.

    Returns (added_count, errors) where errors is a list of 'Row N: message'.
    """
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            reader.fieldnames = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
            missing = [c for c in required if c not in reader.fieldnames]
            if missing:
                raise DatabaseError(
                    "Missing column(s): " + ", ".join(missing)
                    + ". Expected header: " + ", ".join(required)
                )
            added, errors = 0, []
            for n, row in enumerate(reader, start=2):  # row 1 is the header
                if not any((v or "").strip() for v in row.values()):
                    continue  # skip blank lines
                try:
                    row_action(row)
                    added += 1
                except DatabaseError as exc:
                    errors.append(f"Row {n}: {exc}")
            return added, errors
    except OSError as exc:
        raise DatabaseError(f"Could not read the file: {exc}")
    except (csv.Error, UnicodeDecodeError):
        raise DatabaseError("The file is not a valid UTF-8 CSV file.")


def import_products_csv(path):
    cols = ["name", "category", "price", "stock_quantity", "cost_price"]
    return _import_csv(path, cols, lambda r: add_product(*[r[c] for c in cols]))


def import_customers_csv(path):
    return _import_csv(
        path, ["name", "phone", "email"],
        lambda r: add_customer(r["name"], r["phone"], r["email"]),
    )


def import_sales_csv(path):
    """Columns: product_name, customer_name (blank = walk-in), quantity, sale_date (YYYY-MM-DD)."""
    def add_row(r):
        pname = (r["product_name"] or "").strip()
        cname = (r["customer_name"] or "").strip()
        cid = None
        with db_session() as conn:
            p = conn.execute("SELECT product_id FROM products WHERE lower(name) = lower(?)",
                             (pname,)).fetchone()
            if cname and cname.lower() not in ("walk-in", "walk-in customer"):
                c = conn.execute("SELECT customer_id FROM customers WHERE lower(name) = lower(?)",
                                 (cname,)).fetchone()
                if c is None:
                    raise DatabaseError(f"Customer '{cname}' not found.")
                cid = c["customer_id"]
        if p is None:
            raise DatabaseError(f"Product '{pname}' not found.")
        date = (r["sale_date"] or "").strip()
        if date:
            try:
                date = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d 12:00:00")
            except ValueError:
                raise DatabaseError("sale_date must look like 2026-10-31.")
        record_sale(p["product_id"], cid, r["quantity"], date or None)

    return _import_csv(path, ["product_name", "customer_name", "quantity", "sale_date"], add_row)


# ---------------------------------------------------------------------- sales
def record_sale(product_id, customer_id, quantity, sale_date=None, total_price=None):
    """Record a sale atomically.

    * The total is computed from the product's price (never trusted from the UI)
      unless an explicit `total_price` (e.g. a discount) is supplied.
    * Stock is decremented in the same transaction and can never go negative.
    * `customer_id` may be None for a walk-in customer.
    """
    quantity = _number(quantity, "Quantity", integer=True, strictly_positive=True)
    sale_date = sale_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with db_session() as conn:
        product = conn.execute(
            "SELECT * FROM products WHERE product_id = ?", (product_id,)
        ).fetchone()
        if product is None:
            raise DatabaseError("Product not found.")
        if customer_id is not None:
            exists = conn.execute(
                "SELECT 1 FROM customers WHERE customer_id = ?", (customer_id,)
            ).fetchone()
            if exists is None:
                raise DatabaseError("Customer not found.")

        if total_price is None:
            total = round(product["price"] * quantity, 2)
        else:
            total = _number(total_price, "Total price")

        # Conditional UPDATE avoids a race between check and decrement.
        cur = conn.execute(
            "UPDATE products SET stock_quantity = stock_quantity - ? "
            "WHERE product_id = ? AND stock_quantity >= ?",
            (quantity, product_id, quantity),
        )
        if cur.rowcount == 0:
            raise DatabaseError(
                f"Insufficient stock for '{product['name']}': "
                f"only {product['stock_quantity']} left."
            )
        cur = conn.execute(
            "INSERT INTO sales (product_id, customer_id, quantity, total_price, "
            "unit_cost, sale_date) VALUES (?, ?, ?, ?, ?, ?)",
            (product_id, customer_id, quantity, total, product["cost_price"], sale_date),
        )
        return cur.lastrowid


def get_sales_history(limit=200):
    with db_session() as conn:
        return conn.execute(
            """
            SELECT s.sale_id, COALESCE(p.name, '(deleted)') AS product_name,
                   COALESCE(c.name, 'Walk-in') AS customer_name,
                   s.quantity, s.total_price, s.sale_date
            FROM sales s
            LEFT JOIN products  p ON p.product_id  = s.product_id
            LEFT JOIN customers c ON c.customer_id = s.customer_id
            ORDER BY s.sale_id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()


def get_sales_analytics(start_date=None, end_date=None):
    """All sales with cost and profit. Dates are 'YYYY-MM-DD' (inclusive)."""
    sql = """
        SELECT s.sale_id, COALESCE(p.name, '(deleted)') AS product_name,
               s.quantity, s.total_price,
               COALESCE(s.unit_cost, p.cost_price, 0) * s.quantity AS total_cost,
               s.total_price - COALESCE(s.unit_cost, p.cost_price, 0) * s.quantity
                   AS net_profit,
               s.sale_date
        FROM sales s LEFT JOIN products p ON p.product_id = s.product_id
        WHERE 1=1
    """
    params = []
    if start_date:
        sql += " AND date(s.sale_date) >= date(?)"
        params.append(start_date)
    if end_date:
        sql += " AND date(s.sale_date) <= date(?)"
        params.append(end_date)
    sql += " ORDER BY s.sale_id"
    with db_session() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_profit_by_product():
    """Aggregated revenue/profit per product, best first."""
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT COALESCE(p.name, '(deleted)') AS product_name,
                   SUM(s.quantity) AS units,
                   SUM(s.total_price) AS revenue,
                   SUM(s.total_price - COALESCE(s.unit_cost, p.cost_price, 0) * s.quantity)
                       AS profit
            FROM sales s LEFT JOIN products p ON p.product_id = s.product_id
            GROUP BY s.product_id ORDER BY profit DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_dashboard_summary(low_stock_threshold=5):
    with db_session() as conn:
        total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        total_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        count, revenue = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(total_price), 0) FROM sales"
        ).fetchone()
        low_stock = conn.execute(
            "SELECT name, stock_quantity FROM products WHERE stock_quantity <= ? "
            "ORDER BY stock_quantity ASC LIMIT 8",
            (low_stock_threshold,),
        ).fetchall()
        recent = conn.execute(
            """
            SELECT s.sale_id, COALESCE(p.name, '(deleted)'), s.quantity,
                   s.total_price, s.sale_date
            FROM sales s LEFT JOIN products p ON p.product_id = s.product_id
            ORDER BY s.sale_id DESC LIMIT 5
            """
        ).fetchall()
    return {
        "total_products": total_products,
        "total_customers": total_customers,
        "total_sales_count": count,
        "total_revenue": revenue,
        "low_stock_items": low_stock,
        "recent_sales": recent,
    }


# Make sure the schema exists no matter which entry point is used.
init_database()
