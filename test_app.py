"""Self-contained tests: run against a temporary database, never the real one."""
import os
import tempfile

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["SMART_SALES_DB"] = _tmp.name  # must be set before importing the app code

from database.db_operations import (  # noqa: E402
    DatabaseError, add_customer, add_product, delete_customer, delete_product,
    get_all_customers, get_all_products, get_dashboard_summary,
    get_profit_by_product, get_sales_analytics, record_sale, update_product,
)


def expect_error(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except DatabaseError as exc:
        return str(exc)
    raise AssertionError(f"{fn.__name__} should have failed")


def run_test():
    pid = add_product("Laptop Dell XPS", "Electronics", 1200.0, 10, 950.0)
    cid = add_customer("Faisal Ahmed", "01012345678", "faisal@example.com")

    # validation
    expect_error(add_product, "", "x", 1, 1, 1)
    expect_error(add_product, "x", "x", -5, 1, 1)
    expect_error(add_product, "x", "x", "abc", 1, 1)
    expect_error(add_customer, "A", "1", "not-an-email")

    # sale: total computed from price, stock reduced
    record_sale(pid, cid, 2)
    assert get_all_products()[0]["stock_quantity"] == 8
    assert get_sales_analytics()[0]["total_price"] == 2400.0
    assert get_sales_analytics()[0]["net_profit"] == 500.0

    # overselling and bad ids are rejected, stock untouched
    expect_error(record_sale, pid, cid, 999)
    expect_error(record_sale, 12345, cid, 1)
    expect_error(record_sale, pid, 12345, 1)
    expect_error(record_sale, pid, cid, 0)
    assert get_all_products()[0]["stock_quantity"] == 8

    # changing cost later must not rewrite historical profit
    update_product(pid, "Laptop Dell XPS", "Electronics", 1200.0, 8, 1000.0)
    assert get_sales_analytics()[0]["net_profit"] == 500.0
    assert get_profit_by_product()[0]["profit"] == 500.0

    # referential integrity
    expect_error(delete_product, pid)
    expect_error(delete_customer, cid)
    other = add_product("Mouse", "Accessories", 10, 3, 4)
    delete_product(other)

    summary = get_dashboard_summary()
    assert summary["total_sales_count"] == 1 and summary["total_revenue"] == 2400.0
    assert len(get_all_customers()) == 1
    print("[SUCCESS] All tests passed.")


if __name__ == "__main__":
    try:
        run_test()
    finally:
        os.unlink(_tmp.name)
