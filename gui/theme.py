"""Design tokens and small reusable widgets. Colors are (light, dark) pairs."""
import customtkinter as ctk

FONT = "Segoe UI"

INK = ("#1F2A30", "#E6ECEA")
MUTED = ("#6B7780", "#8FA0A8")
BG = ("#F3F5F4", "#14191C")
CARD = ("#FFFFFF", "#1D252A")
LINE = ("#E1E6E4", "#2A353B")
ZEBRA = ("#F7F9F8", "#222C32")
SIDEBAR = ("#17363A", "#0F2326")
SIDE_TEXT = "#CFE3E0"
SIDE_ACTIVE = "#0F766E"
SIDE_HOVER = "#1F4A4F"
PRIMARY = ("#0F766E", "#14958A")
PRIMARY_HOVER = ("#0B5F59", "#0F766E")
OK, WARN, BAD = "#2F855A", "#C77700", "#C0392B"


def font(size=13, weight="normal"):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


def card(parent, **kw):
    return ctk.CTkFrame(parent, fg_color=CARD, corner_radius=12,
                        border_width=1, border_color=LINE, **kw)


def button(parent, text, command, kind="primary", width=110):
    styles = {
        "primary": dict(fg_color=PRIMARY, hover_color=PRIMARY_HOVER, text_color="white"),
        "ghost": dict(fg_color="transparent", hover_color=ZEBRA, text_color=INK,
                      border_width=1, border_color=LINE),
        "danger": dict(fg_color="transparent", hover_color=("#FBE9E7", "#3A2321"),
                       text_color=BAD, border_width=1, border_color=BAD),
    }
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=34,
                         corner_radius=8, font=font(13, "bold" if kind == "primary" else "normal"),
                         **styles[kind])


def entry(parent, placeholder, width=200):
    return ctk.CTkEntry(parent, placeholder_text=placeholder, width=width, height=36,
                        corner_radius=8, fg_color=CARD, border_color=LINE, text_color=INK,
                        font=font(13))


def combo(parent, values, width=260, command=None):
    return ctk.CTkComboBox(parent, values=values, width=width, height=36, corner_radius=8,
                           state="readonly", fg_color=CARD, border_color=LINE,
                           button_color=PRIMARY, button_hover_color=PRIMARY_HOVER,
                           text_color=INK, font=font(13), command=command)


def page_header(parent, title, subtitle=""):
    box = ctk.CTkFrame(parent, fg_color="transparent")
    box.pack(fill="x", pady=(0, 14))
    ctk.CTkLabel(box, text=title, font=font(26, "bold"), text_color=INK).pack(anchor="w")
    if subtitle:
        ctk.CTkLabel(box, text=subtitle, font=font(13), text_color=MUTED).pack(anchor="w")
    return box


def stat_card(parent, title, value, color=PRIMARY, hint=""):
    c = card(parent)
    ctk.CTkFrame(c, width=4, height=1, fg_color=color, corner_radius=2).pack(side="left", fill="y", padx=(10, 0), pady=12)
    inner = ctk.CTkFrame(c, fg_color="transparent")
    inner.pack(side="left", fill="both", expand=True, padx=14, pady=12)
    ctk.CTkLabel(inner, text=title, font=font(12), text_color=MUTED).pack(anchor="w")
    ctk.CTkLabel(inner, text=value, font=font(24, "bold"), text_color=INK).pack(anchor="w")
    if hint:
        ctk.CTkLabel(inner, text=hint, font=font(11), text_color=MUTED).pack(anchor="w")
    return c


def chip(parent, text, color):
    return ctk.CTkLabel(parent, text=text, font=font(11, "bold"), text_color="white",
                        fg_color=color, corner_radius=9, height=20, width=70)


def data_table(parent, columns, rows, actions=None, empty="Nothing here yet."):
    """columns: [(title, width, 'w'|'e')]; a cell given as (text, color) renders as a chip.
    actions(i) -> [(label, kind, callback)] adds buttons at the end of row i."""
    head = ctk.CTkFrame(parent, fg_color="transparent")
    head.pack(fill="x", padx=8, pady=(6, 2))
    for title, width, anchor in columns:
        ctk.CTkLabel(head, text=title, width=width, anchor=anchor, font=font(12, "bold"),
                     text_color=MUTED).pack(side="left", padx=6)
    ctk.CTkFrame(parent, height=1, fg_color=LINE).pack(fill="x", padx=8)
    if not rows:
        ctk.CTkLabel(parent, text=empty, font=font(13), text_color=MUTED).pack(pady=30)
        return
    for i, values in enumerate(rows):
        row = ctk.CTkFrame(parent, fg_color=ZEBRA if i % 2 else "transparent", corner_radius=6)
        row.pack(fill="x", padx=8, pady=1)
        for (title, width, anchor), v in zip(columns, values):
            if isinstance(v, tuple):
                holder = ctk.CTkFrame(row, width=width, height=30, fg_color="transparent")
                holder.pack_propagate(False)
                holder.pack(side="left", padx=6)
                chip(holder, *v).pack(side="left", pady=5)
            else:
                ctk.CTkLabel(row, text=str(v), width=width, anchor=anchor, font=font(13),
                             text_color=INK, height=34).pack(side="left", padx=6)
        if actions:
            for label, kind, cb in reversed(actions(i)):
                button(row, label, cb, kind, width=64).pack(side="right", padx=4, pady=3)
