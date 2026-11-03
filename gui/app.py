import csv
import os
import sys
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from config import (  # noqa: E402
    APP_NAME, APP_VERSION, APPEARANCE_MODE, COLOR_THEME, CURRENCY, LOW_STOCK_THRESHOLD,
)
from database.db_operations import (  # noqa: E402
    DatabaseError, add_customer, add_product, delete_customer, delete_product,
    get_all_customers, get_all_products, get_dashboard_summary, get_profit_by_product,
    get_sales_analytics, get_sales_history, import_customers_csv, import_products_csv, import_sales_csv,
    record_sale, update_customer, update_product,
)
from gui import theme as t  # noqa: E402

ctk.set_appearance_mode(APPEARANCE_MODE)
ctk.set_default_color_theme(COLOR_THEME)


def money(v):
    return f"{CURRENCY}{v:,.2f}"


def safe(action, *args, **kwargs):
    """Run a DB action; show a dialog instead of crashing. Returns (ok, result)."""
    try:
        return True, action(*args, **kwargs)
    except DatabaseError as exc:
        messagebox.showerror("Can't complete this action", str(exc))
    except Exception as exc:
        messagebox.showerror("Unexpected error", f"{type(exc).__name__}: {exc}")
    return False, None


def stock_chip(qty):
    if qty <= 0:
        return ("Out", t.BAD)
    if qty <= LOW_STOCK_THRESHOLD:
        return ("Low", t.WARN)
    return ("In stock", t.OK)


class FormDialog(ctk.CTkToplevel):
    """Modal form used for adding and editing. fields = [(label, initial)]."""

    def __init__(self, parent, title, fields, on_save, save_label="Save changes"):
        super().__init__(parent, fg_color=t.BG)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.on_save, self.entries = on_save, []
        ctk.CTkLabel(self, text=title, font=t.font(18, "bold"), text_color=t.INK).grid(
            row=0, column=0, columnspan=2, padx=20, pady=(18, 8), sticky="w")
        for i, (label, value) in enumerate(fields, start=1):
            ctk.CTkLabel(self, text=label, font=t.font(13), text_color=t.MUTED).grid(
                row=i, column=0, padx=(20, 10), pady=6, sticky="w")
            e = t.entry(self, "", 260)
            e.insert(0, "" if value is None else str(value))
            e.grid(row=i, column=1, padx=(0, 20), pady=6)
            self.entries.append(e)
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=len(fields) + 1, column=0, columnspan=2, pady=16, padx=20, sticky="e")
        t.button(bar, "Cancel", self.destroy, "ghost", 90).pack(side="left", padx=6)
        t.button(bar, save_label, self._save, "primary", 130).pack(side="left")
        self.bind("<Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.after(150, self._focus)

    def _focus(self):
        self.grab_set()
        self.entries[0].focus()

    def _save(self):
        ok, _ = safe(self.on_save, *[e.get() for e in self.entries])
        if ok:
            self.destroy()


class SmartSalesApp(ctk.CTk):
    NAV = [("Dashboard", "Dashboard"), ("Products", "Products"), ("Customers", "Customers"),
           ("Sales", "New sale"), ("Analytics", "Analytics")]

    def __init__(self):
        super().__init__(fg_color=t.BG)
        self.title(f"{APP_NAME} - v{APP_VERSION}")
        self.geometry("1280x780")
        self.minsize(1100, 680)
        self.current_tab = "Dashboard"
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        side = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=t.SIDEBAR)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="Smart Sales", font=t.font(22, "bold"),
                     text_color="white").pack(anchor="w", padx=22, pady=(26, 0))
        ctk.CTkLabel(side, text="Inventory & analytics", font=t.font(12),
                     text_color=t.SIDE_TEXT).pack(anchor="w", padx=22, pady=(0, 24))
        self.nav_buttons = {}
        for key, label in self.NAV:
            b = ctk.CTkButton(side, text=label, anchor="w", height=40, corner_radius=8,
                              font=t.font(14), fg_color="transparent",
                              hover_color=t.SIDE_HOVER, text_color=t.SIDE_TEXT,
                              command=lambda k=key: self.select_tab(k))
            b.pack(fill="x", padx=14, pady=3)
            self.nav_buttons[key] = b
        self.dark_switch = ctk.CTkSwitch(side, text="Dark mode", text_color=t.SIDE_TEXT,
                                         font=t.font(13), command=self.toggle_mode,
                                         progress_color=t.SIDE_ACTIVE)
        self.dark_switch.pack(side="bottom", anchor="w", padx=22, pady=22)
        if APPEARANCE_MODE.lower() == "dark":
            self.dark_switch.select()

        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
        self.select_tab("Dashboard")

    # ------------------------------------------------------------ navigation
    def toggle_mode(self):
        ctk.set_appearance_mode("Dark" if self.dark_switch.get() else "Light")
        self.select_tab(self.current_tab)  # redraw charts with matching colors

    def select_tab(self, name):
        self.current_tab = name
        for w in self.main.winfo_children():
            w.destroy()
        for key, b in self.nav_buttons.items():
            b.configure(fg_color=t.SIDE_ACTIVE if key == name else "transparent",
                        text_color="white" if key == name else t.SIDE_TEXT)
        getattr(self, f"build_{name.lower()}")()

    def toast(self, message):
        lbl = ctk.CTkLabel(self, text=f"  {message}  ", font=t.font(13, "bold"),
                           text_color="white", fg_color=t.OK, corner_radius=8, height=38)
        lbl.place(relx=0.98, rely=0.97, anchor="se")
        self.after(2600, lbl.destroy)

    def _scroll(self, parent):
        frame = ctk.CTkScrollableFrame(parent, fg_color=t.CARD, corner_radius=12,
                                       border_width=1, border_color=t.LINE)
        frame.pack(fill="both", expand=True)
        return frame

    # -------------------------------------------------------------- dashboard
    def build_dashboard(self):
        ok, s = safe(get_dashboard_summary, LOW_STOCK_THRESHOLD)
        if not ok:
            return
        t.page_header(self.main, "Overview", datetime.now().strftime("%A, %d %B %Y"))
        row = ctk.CTkFrame(self.main, fg_color="transparent")
        row.pack(fill="x")
        stats = [("Revenue", money(s["total_revenue"]), t.OK, "all recorded sales"),
                 ("Sales", str(s["total_sales_count"]), t.PRIMARY, "transactions"),
                 ("Products", str(s["total_products"]), t.PRIMARY, "in the catalog"),
                 ("Customers", str(s["total_customers"]), t.PRIMARY, "registered")]
        for i, (a, b, c, h) in enumerate(stats):
            row.grid_columnconfigure(i, weight=1, uniform="k")
            t.stat_card(row, a, b, c, h).grid(row=0, column=i, padx=6, pady=4, sticky="ew")

        bar = ctk.CTkFrame(self.main, fg_color="transparent")
        bar.pack(side="bottom", fill="x", pady=(14, 0))
        t.button(bar, "New sale", lambda: self.select_tab("Sales")).pack(side="left", padx=6)
        t.button(bar, "Add product", lambda: self.add_product_ui(True), "ghost").pack(side="left")

        body = ctk.CTkFrame(self.main, fg_color="transparent")
        body.pack(fill="both", expand=True, pady=(14, 0))
        body.grid_columnconfigure((0, 1), weight=1, uniform="b")
        body.grid_rowconfigure(0, weight=1)

        left = t.card(body)
        left.grid(row=0, column=0, padx=(6, 8), sticky="nsew")
        ctk.CTkLabel(left, text=f"Running low (stock {LOW_STOCK_THRESHOLD} or less)",
                     font=t.font(15, "bold"), text_color=t.INK).pack(anchor="w", padx=16, pady=(14, 4))
        t.data_table(left, [("Product", 230, "w"), ("Left", 70, "e")],
                     [(n, q) for n, q in s["low_stock_items"]],
                     empty="Every product is well stocked.")

        right = t.card(body)
        right.grid(row=0, column=1, padx=(8, 6), sticky="nsew")
        ctk.CTkLabel(right, text="Latest sales", font=t.font(15, "bold"),
                     text_color=t.INK).pack(anchor="w", padx=16, pady=(14, 4))
        t.data_table(right, [("Product", 190, "w"), ("Qty", 40, "e"), ("Total", 90, "e")],
                     [(r[1], r[2], money(r[3])) for r in s["recent_sales"]],
                     empty="No sales yet. Record the first one.")

    # --------------------------------------------------------------- products
    def build_products(self):
        t.page_header(self.main, "Products", "Prices, costs and stock levels")
        bar = ctk.CTkFrame(self.main, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 10))
        self.search_prod = t.entry(bar, "Search by name or category", 320)
        self.search_prod.pack(side="left")
        self.search_prod.bind("<KeyRelease>", lambda _e: self.load_products())
        t.button(bar, "Add product", self.add_product_ui).pack(side="right")
        t.button(bar, "Import CSV", lambda: self.import_ui(import_products_csv, self.load_products),
                 "ghost").pack(side="right", padx=8)
        self.prod_frame = self._scroll(self.main)
        self.load_products()

    def load_products(self):
        for w in self.prod_frame.winfo_children():
            w.destroy()
        ok, items = safe(get_all_products, self.search_prod.get())
        if not ok:
            return
        cols = [("ID", 40, "w"), ("Name", 200, "w"), ("Category", 130, "w"), ("Price", 90, "e"),
                ("Cost", 90, "e"), ("Stock", 60, "e"), ("Status", 90, "w")]
        rows = [(p["product_id"], p["name"], p["category"], money(p["price"]),
                 money(p["cost_price"]), p["stock_quantity"], stock_chip(p["stock_quantity"]))
                for p in items]
        t.data_table(self.prod_frame, cols, rows, empty="No products found. Add your first one.",
                     actions=lambda i: [("Edit", "ghost", lambda p=items[i]: self.edit_product_ui(p)),
                                        ("Delete", "danger", lambda p=items[i]: self.remove_product_ui(p))])

    def add_product_ui(self, from_dashboard=False):
        def save(name, cat, price, stock, cost):
            add_product(name, cat, price, stock, cost)
            self.toast("Product added")
            self.select_tab("Products")
        FormDialog(self, "Add product", [("Name", ""), ("Category", ""), ("Price", ""),
                                         ("Stock", ""), ("Cost price", "")], save, "Add product")

    def edit_product_ui(self, p):
        def save(name, cat, price, stock, cost):
            update_product(p["product_id"], name, cat, price, stock, cost)
            self.toast("Product updated")
            self.load_products()
        FormDialog(self, f"Edit product #{p['product_id']}",
                   [("Name", p["name"]), ("Category", p["category"]), ("Price", p["price"]),
                    ("Stock", p["stock_quantity"]), ("Cost price", p["cost_price"])], save)

    def remove_product_ui(self, p):
        if messagebox.askyesno("Delete product", f"Delete '{p['name']}'? This can't be undone."):
            ok, _ = safe(delete_product, p["product_id"])
            if ok:
                self.toast("Product deleted")
                self.load_products()

    def import_ui(self, importer, reload):
        path = filedialog.askopenfilename(title="Choose a CSV file",
                                          filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        ok, result = safe(importer, path)
        if not ok:
            return
        added, errors = result
        reload()
        if errors:
            shown = "\n".join(errors[:10]) + (f"\n... and {len(errors) - 10} more" if len(errors) > 10 else "")
            messagebox.showwarning("Import finished with problems",
                                   f"Added {added} row(s). Skipped {len(errors)}:\n\n{shown}")
        else:
            self.toast(f"Imported {added} row(s)")

    # -------------------------------------------------------------- customers
    def build_customers(self):
        t.page_header(self.main, "Customers", "People you sell to")
        bar = ctk.CTkFrame(self.main, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 10))
        self.search_cust = t.entry(bar, "Search by name, phone or email", 320)
        self.search_cust.pack(side="left")
        self.search_cust.bind("<KeyRelease>", lambda _e: self.load_customers())
        t.button(bar, "Add customer", self.add_customer_ui).pack(side="right")
        t.button(bar, "Import CSV", lambda: self.import_ui(import_customers_csv, self.load_customers),
                 "ghost").pack(side="right", padx=8)
        self.cust_frame = self._scroll(self.main)
        self.load_customers()

    def load_customers(self):
        for w in self.cust_frame.winfo_children():
            w.destroy()
        ok, items = safe(get_all_customers, self.search_cust.get())
        if not ok:
            return
        cols = [("ID", 40, "w"), ("Name", 220, "w"), ("Phone", 150, "w"), ("Email", 240, "w")]
        rows = [(c["customer_id"], c["name"], c["phone"] or "-", c["email"] or "-") for c in items]
        t.data_table(self.cust_frame, cols, rows, empty="No customers found. Add your first one.",
                     actions=lambda i: [("Edit", "ghost", lambda c=items[i]: self.edit_customer_ui(c)),
                                        ("Delete", "danger", lambda c=items[i]: self.remove_customer_ui(c))])

    def add_customer_ui(self):
        def save(name, phone, email):
            add_customer(name, phone, email)
            self.toast("Customer added")
            self.load_customers()
        FormDialog(self, "Add customer", [("Name", ""), ("Phone", ""), ("Email", "")], save, "Add customer")

    def edit_customer_ui(self, c):
        def save(name, phone, email):
            update_customer(c["customer_id"], name, phone, email)
            self.toast("Customer updated")
            self.load_customers()
        FormDialog(self, f"Edit customer #{c['customer_id']}",
                   [("Name", c["name"]), ("Phone", c["phone"]), ("Email", c["email"])], save)

    def remove_customer_ui(self, c):
        if messagebox.askyesno("Delete customer", f"Delete '{c['name']}'? This can't be undone."):
            ok, _ = safe(delete_customer, c["customer_id"])
            if ok:
                self.toast("Customer deleted")
                self.load_customers()

    # ------------------------------------------------------------------ sales
    def build_sales(self):
        t.page_header(self.main, "New sale", "Pick a product and quantity. The total is calculated for you.")
        ok, products = safe(get_all_products)
        ok2, customers = safe(get_all_customers)
        if not (ok and ok2):
            return
        self._sale_products = {
            f"{p['product_id']} - {p['name']} ({p['stock_quantity']} left)": p
            for p in products if p["stock_quantity"] > 0}
        self._sale_customers = {"Walk-in customer": None}
        self._sale_customers.update({f"{c['customer_id']} - {c['name']}": c["customer_id"] for c in customers})

        wrap = ctk.CTkFrame(self.main, fg_color="transparent")
        wrap.pack(fill="both", expand=True)
        wrap.grid_columnconfigure(1, weight=1)
        wrap.grid_rowconfigure(0, weight=1)

        form = t.card(wrap, width=340)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        form.grid_propagate(False)

        def field(label, widget):
            ctk.CTkLabel(form, text=label, font=t.font(12), text_color=t.MUTED).pack(anchor="w", padx=20, pady=(16, 3))
            widget.pack(padx=20, anchor="w")

        self.cmb_product = t.combo(form, list(self._sale_products) or ["No products in stock"],
                                   300, lambda _v: self.update_total())
        self.cmb_product.set("Select a product")
        field("Product", self.cmb_product)
        self.cmb_customer = t.combo(form, list(self._sale_customers), 300)
        self.cmb_customer.set("Walk-in customer")
        field("Customer", self.cmb_customer)
        self.ent_qty = t.entry(form, "1", 120)
        self.ent_qty.bind("<KeyRelease>", lambda _e: self.update_total())
        field("Quantity", self.ent_qty)
        ctk.CTkFrame(form, height=1, fg_color=t.LINE).pack(fill="x", padx=20, pady=(22, 10))
        ctk.CTkLabel(form, text="Total", font=t.font(12), text_color=t.MUTED).pack(anchor="w", padx=20)
        self.lbl_total = ctk.CTkLabel(form, text=money(0), font=t.font(30, "bold"), text_color=t.INK)
        self.lbl_total.pack(anchor="w", padx=20)
        t.button(form, "Complete sale", self.checkout, width=300).pack(padx=20, pady=20)

        hist = t.card(wrap)
        hist.grid(row=0, column=1, sticky="nsew")
        head = ctk.CTkFrame(hist, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 0))
        ctk.CTkLabel(head, text="Sales history", font=t.font(15, "bold"),
                     text_color=t.INK).pack(side="left")
        t.button(head, "Import CSV", lambda: self.import_ui(
            import_sales_csv, lambda: self.select_tab("Sales")), "ghost").pack(side="right")
        frame = ctk.CTkScrollableFrame(hist, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=4, pady=4)
        ok, sales = safe(get_sales_history)
        if ok:
            t.data_table(frame, [("#", 40, "w"), ("Product", 170, "w"), ("Customer", 130, "w"),
                                 ("Qty", 40, "e"), ("Total", 90, "e"), ("Date", 140, "w")],
                         [(s["sale_id"], s["product_name"], s["customer_name"], s["quantity"],
                           money(s["total_price"]), s["sale_date"][:16]) for s in sales],
                         empty="No sales recorded yet.")

    def update_total(self):
        p = self._sale_products.get(self.cmb_product.get())
        try:
            q = int(self.ent_qty.get())
        except ValueError:
            q = 0
        self.lbl_total.configure(text=money(p["price"] * q if p and q > 0 else 0))

    def checkout(self):
        p = self._sale_products.get(self.cmb_product.get())
        if p is None:
            messagebox.showerror("Select a product", "Choose a product from the list first.")
            return
        ok, _ = safe(record_sale, p["product_id"], self._sale_customers.get(self.cmb_customer.get()),
                     self.ent_qty.get())
        if ok:
            self.select_tab("Sales")
            self.toast("Sale recorded")

    # -------------------------------------------------------------- analytics
    def build_analytics(self):
        t.page_header(self.main, "Analytics", "Revenue, cost and profit")
        ok, sales = safe(get_sales_analytics)
        ok2, by_product = safe(get_profit_by_product)
        ok3, products = safe(get_all_products)
        if not (ok and ok2 and ok3):
            return
        rev = sum(s["total_price"] for s in sales)
        cost = sum(s["total_cost"] for s in sales)
        profit = sum(s["net_profit"] for s in sales)
        row = ctk.CTkFrame(self.main, fg_color="transparent")
        row.pack(fill="x")
        for i, (a, b, c) in enumerate([("Revenue", money(rev), t.PRIMARY), ("Cost", money(cost), t.WARN),
                                       ("Net profit", money(profit), t.OK),
                                       ("Margin", f"{profit / rev * 100:.1f}%" if rev else "0.0%", t.PRIMARY)]):
            row.grid_columnconfigure(i, weight=1, uniform="k")
            t.stat_card(row, a, b, c).grid(row=0, column=i, padx=6, pady=4, sticky="ew")

        dark = ctk.get_appearance_mode() == "Dark"
        bg, fg, grid, accent, second = (("#1D252A", "#E6ECEA", "#33414A", "#14958A", "#5B8DB8") if dark
                                        else ("#FFFFFF", "#1F2A30", "#E1E6E4", "#0F766E", "#5B8DB8"))
        fig = Figure(figsize=(9, 3.6), dpi=100, facecolor=bg)
        axes = fig.subplots(1, 2)
        for ax, title, data, color in [
            (axes[0], "Profit by product", [(r["product_name"], r["profit"]) for r in by_product], accent),
            (axes[1], "Stock levels", [(p["name"], p["stock_quantity"]) for p in products], second)]:
            ax.set_facecolor(bg)
            ax.set_title(title, color=fg, fontsize=11, loc="left")
            ax.tick_params(colors=fg, labelsize=8)
            ax.grid(axis="y", color=grid, linewidth=0.8)
            ax.set_axisbelow(True)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            for sp in ("left", "bottom"):
                ax.spines[sp].set_color(grid)
            if data:
                ax.bar([d[0] for d in data], [d[1] for d in data], color=color, width=0.55)
            else:
                ax.text(0.5, 0.5, "No data yet", color=fg, ha="center", transform=ax.transAxes)
            for lbl in ax.get_xticklabels():
                lbl.set_rotation(25)
                lbl.set_ha("right")
        fig.tight_layout()
        box = t.card(self.main)
        box.pack(fill="both", expand=True, pady=(12, 8), padx=6)
        canvas = FigureCanvasTkAgg(fig, master=box)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)
        t.button(self.main, "Export sales to CSV", self.export_csv, "ghost", 170).pack(anchor="e", padx=6)

    def export_csv(self):
        ok, sales = safe(get_sales_analytics)
        if not ok:
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")],
                                            initialfile=f"sales_{datetime.now():%Y%m%d}.csv")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.DictWriter(fh, fieldnames=["sale_id", "product_name", "quantity", "total_price",
                                                   "total_cost", "net_profit", "sale_date"])
                w.writeheader()
                w.writerows(sales)
            self.toast(f"Exported {len(sales)} sales")
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc))


if __name__ == "__main__":
    SmartSalesApp().mainloop()
