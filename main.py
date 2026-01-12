import os
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox
import requests
from PIL import Image, ImageTk, ImageDraw, ImageFilter
import subprocess
import shutil

# ============================================================
# CONFIG
# ============================================================

API_BASE = "https://mctiers.com/api/v2"
SITE_BASE = "https://mctiers.com"

ICON_MODES = ["overall", "vanilla", "uhc", "pot", "nethop", "smp", "sword", "axe", "mace"]
GAMEMODES = ["vanilla", "uhc", "pot", "nethop", "smp", "sword", "axe", "mace"]

TIER_POINTS = {
    "LT5": 1,  "HT5": 2,
    "LT4": 3,  "HT4": 4,
    "LT3": 6,  "HT3": 10,
    "LT2": 20, "HT2": 30,
    "LT1": 45, "HT1": 60
}
TIERS = list(TIER_POINTS.keys())

TOP_N = 10_000
PAGE_SIZE = 50

BASE_DIR = os.path.dirname(__file__)
ASSETS = os.path.join(BASE_DIR, "assets")
ICON_DIR = os.path.join(ASSETS, "icons")
CACHE_DIR = os.path.join(ASSETS, "cache")
os.makedirs(ICON_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) MCTiersRankTool/Official",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
})

# ============================================================
# THEME
# ============================================================

BG = "#070c12"
TOPBAR = "#060a10"
CARD = "#0c1420"
BORDER = "#1b2a3d"
TEXT = "#e7f0ff"
MUTED = "#8fa6c2"

ACCENT = "#4ea1ff"
ACCENT_HOVER = "#79bbff"

GREEN = "#39d98a"
GREEN_HOVER = "#66e9ae"

RED = "#ff4e4e"

CHIP_BG = "#05090f"
CHIP_BORDER = "#1d3149"

# ============================================================
# FONT
# ============================================================

MINECRAFT_FONT_NAME = "Minecraftia"

def minecraft_font_available():
    try:
        return MINECRAFT_FONT_NAME in tkfont.families()
    except Exception:
        return False

def F(size=10, bold=False):
    fam = MINECRAFT_FONT_NAME if minecraft_font_available() else "Segoe UI"
    return (fam, size, "bold") if bold else (fam, size)

# ============================================================
# API
# ============================================================

def api_get(path: str, params=None):
    url = f"{API_BASE}{path}"
    r = SESSION.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_top_overall(top_n=TOP_N, progress_cb=None):
    out = []
    offset = 0
    while len(out) < top_n:
        batch = api_get("/mode/overall", params={"count": PAGE_SIZE, "from": offset})
        if not isinstance(batch, list) or not batch:
            break
        out.extend(batch)
        offset += len(batch)
        if progress_cb:
            progress_cb(len(out))
        if len(batch) < PAGE_SIZE:
            break
    return out[:top_n]

def fetch_player(name: str):
    return api_get(f"/profile/by-name/{name}")

# ============================================================
# RANK
# ============================================================

def compute_user_score(tiers: dict):
    score = 0
    for m in GAMEMODES:
        t = tiers.get(m, "")
        if t in TIER_POINTS:
            score += TIER_POINTS[t]
    return score

def compute_rank(user_score: int, leaderboard: list[dict]):
    higher = sum(1 for p in leaderboard if int(p.get("points", 0)) > user_score)
    return higher + 1

# ============================================================
# ICONS
# ============================================================

def tier_icon_url(mode: str) -> str:
    return f"{SITE_BASE}/tier_icons/{mode}.svg"

def magick_bin():
    return shutil.which("magick") or shutil.which("convert")

def svg_to_png(svg_path: str, png_path: str):
    m = magick_bin()
    if not m:
        raise RuntimeError("ImageMagick missing. Install: sudo pacman -S imagemagick")

    cmd = [
        m,
        "-density", "600",
        "-background", "none",
        svg_path,
        "-alpha", "set",
        "-define", "png:color-type=6",
        "-resize", "512x512",
        png_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def is_svg_bytes(data: bytes) -> bool:
    head = data[:1400].decode("utf-8", errors="ignore").lower()
    if "<html" in head:
        return False
    return "<svg" in head

def download_svg(mode: str) -> bytes:
    url = tier_icon_url(mode)
    headers = {
        "Referer": "https://mctiers.com/rankings/overall",
        "Origin": "https://mctiers.com",
        "Accept": "image/svg+xml,image/*,*/*;q=0.8",
    }

    last = None
    for _ in range(6):
        try:
            r = SESSION.get(url, headers=headers, timeout=25)
            r.raise_for_status()
            if is_svg_bytes(r.content):
                return r.content
            last = RuntimeError("non-svg content")
        except Exception as e:
            last = e
        time.sleep(0.35)
    raise RuntimeError(f"Failed icon {mode}: {last}")

def fallback_icon(png_path: str, mode: str):
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((18, 18, 238, 238), fill=(12, 20, 32, 255), outline=(28, 60, 98, 255), width=10)
    d.text((118, 104), mode[0].upper(), fill=(200, 235, 255, 220))
    img.save(png_path, "PNG")

def ensure_icons_safely():
    warnings = []
    for mode in ICON_MODES:
        svg_path = os.path.join(ICON_DIR, f"{mode}.svg")
        png_path = os.path.join(ICON_DIR, f"{mode}.png")

        if os.path.exists(png_path):
            try:
                Image.open(png_path).verify()
                continue
            except Exception:
                try:
                    os.remove(png_path)
                except Exception:
                    pass

        try:
            svg_bytes = download_svg(mode)
            with open(svg_path, "wb") as f:
                f.write(svg_bytes)

            svg_to_png(svg_path, png_path)
            img = Image.open(png_path).convert("RGBA")
            if img.getbbox() is None:
                raise RuntimeError("blank png")

        except Exception as e:
            warnings.append(f"{mode}: {e}")
            fallback_icon(png_path, mode)

    return "\n".join(warnings)

def make_circle_chip(icon: Image.Image, size=44):
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    d.ellipse((1, 1, size-2, size-2), fill=CHIP_BG, outline=CHIP_BORDER, width=2)

    icon_size = int(size * 0.62)
    ic = icon.convert("RGBA").resize((icon_size, icon_size), Image.LANCZOS)

    glow = ic.copy().filter(ImageFilter.GaussianBlur(radius=2))
    tint = Image.new("RGBA", glow.size, (120, 190, 255, 150))
    glow = Image.alpha_composite(tint, glow)

    x = (size - icon_size) // 2
    y = (size - icon_size) // 2
    base.alpha_composite(glow, (x, y))
    base.alpha_composite(ic, (x, y))
    return base

def load_chip_photo(mode: str, chip_size=44):
    p = os.path.join(ICON_DIR, f"{mode}.png")
    icon = Image.open(p).convert("RGBA")
    chip = make_circle_chip(icon, size=chip_size)
    return ImageTk.PhotoImage(chip)

# ============================================================
# BADGES (gold/retired)
# ============================================================

badge_cache = {}

def make_badge_image(text: str, retired: bool):
    W, H = 56, 24
    r = 9

    if retired:
        top = (126, 130, 136, 255)
        bottom = (85, 90, 98, 255)
        border = (25, 30, 38, 255)
        txt = (10, 12, 14, 255)
    else:
        top = (255, 211, 95, 255)
        bottom = (196, 138, 20, 255)
        border = (35, 24, 8, 255)
        txt = (10, 10, 10, 255)

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(H):
        t = y / (H - 1)
        col = (
            int(top[0] + (bottom[0] - top[0]) * t),
            int(top[1] + (bottom[1] - top[1]) * t),
            int(top[2] + (bottom[2] - top[2]) * t),
            255
        )
        gd.line((0, y, W, y), fill=col)

    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, W-1, H-1), r, fill=255)
    img = Image.composite(grad, img, mask)

    bd = ImageDraw.Draw(img)
    bd.rounded_rectangle((0, 0, W-1, H-1), r, outline=border, width=2)

    hi = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hid = ImageDraw.Draw(hi)
    hid.rounded_rectangle((2, 2, W-3, H//2), r-2, fill=(255, 255, 255, 45))
    img = Image.alpha_composite(img, hi)

    td = ImageDraw.Draw(img)
    td.text((W//2, H//2), text, anchor="mm", fill=txt)
    return ImageTk.PhotoImage(img)

# ============================================================
# SKINS
# ============================================================

def skin_head_url(name: str, size=64):
    return f"https://minotar.net/helm/{name}/{size}.png"

def get_cached_image(url: str, key: str):
    p = os.path.join(CACHE_DIR, key)
    if os.path.exists(p):
        try:
            return Image.open(p).convert("RGBA")
        except Exception:
            pass
    r = SESSION.get(url, timeout=20)
    r.raise_for_status()
    with open(p, "wb") as f:
        f.write(r.content)
    return Image.open(p).convert("RGBA")

# ============================================================
# UI Widgets
# ============================================================

def rr_points(x1, y1, x2, y2, r):
    return [
        x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
        x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
        x1, y2, x1, y2-r, x1, y1+r, x1, y1
    ]

class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, w, h, radius=18, bg=ACCENT, hover=ACCENT_HOVER, fg="#07121f"):
        super().__init__(parent, width=w, height=h, bg=parent["bg"], highlightthickness=0, bd=0)
        self.command = command
        self.w, self.h, self.r = w, h, radius
        self.bg = bg
        self.hover = hover
        self.fg = fg
        self.text = text
        self.cur = bg
        self.draw()
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", lambda e: self._enter())
        self.bind("<Leave>", lambda e: self._leave())

    def _enter(self):
        self.cur = self.hover
        self.draw()

    def _leave(self):
        self.cur = self.bg
        self.draw()

    def draw(self):
        self.delete("all")
        self.create_polygon(rr_points(0, 0, self.w, self.h, self.r), smooth=True, fill=self.cur, outline="")
        self.create_text(self.w//2, self.h//2, text=self.text, fill=self.fg, font=F(11, True))

class Card(tk.Canvas):
    def __init__(self, parent, w, h):
        super().__init__(parent, width=w, height=h, bg=BG, highlightthickness=0, bd=0)
        self.w, self.h = w, h
        self.draw()

    def draw(self):
        self.delete("all")
        self.create_polygon(rr_points(2, 2, self.w-2, self.h-2, 22), smooth=True, fill=BORDER, outline="")
        self.create_polygon(rr_points(4, 4, self.w-4, self.h-4, 20), smooth=True, fill=CARD, outline="")

class VScrollFrame(tk.Frame):
    """vertical scroll container so button never disappears"""
    def __init__(self, parent, bg=CARD):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.scroll = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)

        self.inner = tk.Frame(self.canvas, bg=bg)
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")

        self.inner.bind("<Configure>", self._on_configure)
        self.canvas.bind("<Configure>", self._on_canvas)

        # natural scrolling
        self.canvas.bind_all("<MouseWheel>", self._wheel)

    def _on_configure(self, _):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, e):
        self.canvas.itemconfig(self.window, width=e.width)

    def _wheel(self, e):
        # scroll only when cursor over this frame
        if self.winfo_containing(root.winfo_pointerx(), root.winfo_pointery()) in (self.canvas, self.inner):
            self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

class HScrollRow(tk.Frame):
    def __init__(self, parent, bg=CARD):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, height=150)
        self.scroll = tk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.scroll.set)

        self.inner = tk.Frame(self.canvas, bg=bg)
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.canvas.pack(fill="x", expand=True)
        self.scroll.pack(fill="x")

        self.inner.bind("<Configure>", self._on_configure)

        # normal wheel sideways when pointer over row
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind_all("<Shift-MouseWheel>", self._shift_wheel)

    def _on_configure(self, _):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _wheel(self, e):
        # vertical wheel moves sideways in this row
        self.canvas.xview_scroll(int(-1 * (e.delta / 120)) * 2, "units")

    def _shift_wheel(self, e):
        self.canvas.xview_scroll(int(-1 * (e.delta / 120)) * 5, "units")

    def clear(self):
        for w in self.inner.winfo_children():
            w.destroy()

# ============================================================
# APP STATE
# ============================================================

leaderboard = []
leaderboard_loaded = False

chip_photos = {}
gm_icon_labels = {}
tier_vars = {}

# ============================================================
# ACTIONS
# ============================================================

def set_status(msg, ok=True):
    status_lbl.config(text=msg, fg=(GREEN if ok else RED))
    root.update_idletasks()

def refresh_top10k():
    def run():
        global leaderboard, leaderboard_loaded
        try:
            prog_lbl.config(text="Loading...", fg=MUTED)
            set_status("Refreshing Top 10k...", True)

            def progress(n):
                prog_lbl.config(text=f"Loaded {n}/{TOP_N}")

            lb = fetch_top_overall(TOP_N, progress_cb=progress)
            if not lb:
                raise RuntimeError("No leaderboard data returned.")
            leaderboard = lb
            leaderboard_loaded = True

            top1 = lb[0]
            prog_lbl.config(text="")
            set_status(f"Loaded {len(lb)} • #1 {top1.get('name')} ({top1.get('points')} pts)", True)
        except Exception as e:
            leaderboard_loaded = False
            prog_lbl.config(text="")
            set_status("Leaderboard refresh failed", False)
            messagebox.showerror("Error", str(e))
    threading.Thread(target=run, daemon=True).start()

def live_score_update(*_):
    tiers = {gm: tier_vars[gm].get() for gm in GAMEMODES}
    score = compute_user_score(tiers)
    live_score_lbl.config(text=f"Live score: {score} pts")

def calc_rank():
    try:
        if not leaderboard_loaded:
            raise RuntimeError("Refresh Top 10k first.")
        user_tiers = {gm: tier_vars[gm].get() for gm in GAMEMODES}
        if any(v == "" for v in user_tiers.values()):
            raise RuntimeError("Pick a tier for every mode.")

        score = compute_user_score(user_tiers)
        rank = compute_rank(score, leaderboard)
        cutoff = int(leaderboard[-1].get("points", 0))

        trophy_icon.config(image=chip_photos["overall"])
        trophy_icon.image = chip_photos["overall"]

        result_text.config(
            text=f"Score: {score} pts\nRank vs loaded Top {len(leaderboard)}: #{rank}\nTop10k cutoff: {cutoff} pts"
        )
    except Exception as e:
        messagebox.showerror("Error", str(e))

def copy_results():
    txt = result_text.cget("text").strip()
    if not txt:
        return
    root.clipboard_clear()
    root.clipboard_append(txt)
    set_status("Copied results to clipboard ✅", True)

def lookup_player():
    name = lookup_var.get().strip()
    if not name:
        messagebox.showerror("Error", "Enter a username.")
        return

    def run():
        try:
            set_status(f"Looking up {name}...", True)
            prof = fetch_player(name)

            pname = prof.get("name", name)
            points = prof.get("points")
            overall = prof.get("overall")
            region = prof.get("region", "??")

            head = get_cached_image(skin_head_url(pname, 96), f"skin_{pname}.png")
            head = head.resize((76, 76), Image.LANCZOS)
            ph = ImageTk.PhotoImage(head)
            skin_lbl.config(image=ph)
            skin_lbl.image = ph

            player_info_lbl.config(text=f"{pname} [{region}] • {points} points • Overall rank #{overall}",
                                   wraplength=380)

            tiers_row.clear()
            rankings = prof.get("rankings", {})
            if isinstance(rankings, dict):
                for gm in GAMEMODES:
                    r = rankings.get(gm)
                    if not r:
                        continue
                    tier = r.get("tier")
                    pos = r.get("pos")
                    retired = bool(r.get("retired", False))
                    if tier is None or pos is None:
                        continue

                    tier_str = f"{'HT' if pos == 0 else 'LT'}{tier}"

                    cell = tk.Frame(tiers_row.inner, bg=CARD)
                    cell.pack(side="left", padx=10, pady=10)

                    tk.Label(cell, image=chip_photos[gm], bg=CARD).pack()

                    key = (tier_str, retired)
                    if key not in badge_cache:
                        badge_cache[key] = make_badge_image(tier_str, retired)
                    tk.Label(cell, image=badge_cache[key], bg=CARD).pack(pady=(8, 0))

            set_status("Lookup complete ✅", True)
        except Exception as e:
            set_status("Lookup failed", False)
            messagebox.showerror("Lookup Error", str(e))

    threading.Thread(target=run, daemon=True).start()

def startup():
    set_status("Loading icons...", True)
    warn = ensure_icons_safely()
    if warn:
        print("ICON WARNINGS:\n" + warn)

    for mode in ICON_MODES:
        try:
            chip_photos[mode] = load_chip_photo(mode, chip_size=46 if mode == "overall" else 44)
        except Exception:
            chip_photos[mode] = None

    for gm in GAMEMODES:
        if chip_photos.get(gm):
            gm_icon_labels[gm].config(image=chip_photos[gm])
            gm_icon_labels[gm].image = chip_photos[gm]

    set_status("Ready ✅", True)
    refresh_top10k()  # QoL: auto refresh on startup

# ============================================================
# GUI
# ============================================================

root = tk.Tk()
root.title("MCTiers Rank Tool")
root.geometry("1120x720")
root.configure(bg=BG)

# Top
top = tk.Frame(root, bg=TOPBAR)
top.pack(fill="x")

tk.Label(top, text="MCTiers Rank Tool", bg=TOPBAR, fg=TEXT, font=F(18, True)).pack(side="left", padx=18, pady=14)

status_lbl = tk.Label(top, text="Starting...", bg=TOPBAR, fg=MUTED, font=F(10))
status_lbl.pack(side="left", padx=14)

prog_lbl = tk.Label(top, text="", bg=TOPBAR, fg=MUTED, font=F(9))
prog_lbl.pack(side="left", padx=10)

RoundedButton(top, "Refresh Top 10k", refresh_top10k, w=200, h=44).pack(side="right", padx=18, pady=10)

# Content
content = tk.Frame(root, bg=BG)
content.pack(fill="both", expand=True, padx=18, pady=18)

left = Card(content, 520, 610)
left.pack(side="left", padx=(0, 14))
left_inner = VScrollFrame(left, bg=CARD)
left.create_window(0, 0, anchor="nw", window=left_inner, width=520, height=610)

right = Card(content, 520, 610)
right.pack(side="right", padx=(14, 0))
right_frame = tk.Frame(right, bg=CARD)
right.create_window(0, 0, anchor="nw", window=right_frame, width=520, height=610)

# LEFT
lf = left_inner.inner
tk.Label(lf, text="Your tiers", bg=CARD, fg=TEXT, font=F(13, True)).pack(anchor="w", padx=18, pady=(18, 8))
tk.Label(lf, text="Pick a tier for each mode to estimate your rank vs loaded Top 10k.",
         bg=CARD, fg=MUTED, font=F(9)).pack(anchor="w", padx=18, pady=(0, 10))

live_score_lbl = tk.Label(lf, text="Live score: 0 pts", bg=CARD, fg=MUTED, font=F(10, True))
live_score_lbl.pack(anchor="w", padx=18, pady=(0, 12))

gm_icon_labels = {}
tier_vars = {}

for gm in GAMEMODES:
    row = tk.Frame(lf, bg=CARD)
    row.pack(fill="x", padx=18, pady=8)

    icon_lbl = tk.Label(row, bg=CARD)
    icon_lbl.pack(side="left", padx=(0, 12))
    gm_icon_labels[gm] = icon_lbl

    v = tk.StringVar(value="")
    v.trace_add("write", live_score_update)
    tier_vars[gm] = v

    dd = tk.Frame(row, bg="#0a0f16", highlightthickness=2, highlightbackground=BORDER)
    dd.pack(side="right")

    om = tk.OptionMenu(dd, v, *TIERS)
    om.config(bg="#0a0f16", fg=TEXT, activebackground="#0a0f16", activeforeground=TEXT,
              relief="flat", bd=0, font=F(10, True), width=9)
    om["menu"].config(bg="#0a0f16", fg=TEXT, activebackground=BORDER, activeforeground=TEXT, font=F(10, True))
    om.pack()

RoundedButton(lf, "Calculate My Rank", calc_rank, w=484, h=52, radius=18,
              bg=GREEN, hover=GREEN_HOVER).pack(padx=18, pady=(22, 12))

btnrow = tk.Frame(lf, bg=CARD)
btnrow.pack(fill="x", padx=18, pady=(0, 8))

RoundedButton(btnrow, "Copy Result", copy_results, w=160, h=40, radius=16, bg=ACCENT, hover=ACCENT_HOVER)\
    .pack(side="left")

outrow = tk.Frame(lf, bg=CARD)
outrow.pack(fill="x", padx=18, pady=(8, 24))

trophy_icon = tk.Label(outrow, bg=CARD)
trophy_icon.pack(side="left", padx=(0, 10))

result_text = tk.Label(outrow, text="", bg=CARD, fg=TEXT, font=F(11, True), justify="left")
result_text.pack(side="left", fill="x", expand=True)

# RIGHT
tk.Label(right_frame, text="Player lookup", bg=CARD, fg=TEXT, font=F(13, True)).pack(anchor="w", padx=18, pady=(18, 8))
tk.Label(right_frame, text="Search any username and view real points, overall rank, and tier icon row.",
         bg=CARD, fg=MUTED, font=F(9)).pack(anchor="w", padx=18, pady=(0, 14))

lookup_row = tk.Frame(right_frame, bg=CARD)
lookup_row.pack(fill="x", padx=18, pady=(0, 14))

lookup_var = tk.StringVar(value="")

entry_box = tk.Frame(lookup_row, bg="#0a0f16", highlightthickness=2, highlightbackground=BORDER)
entry_box.pack(side="left", fill="x", expand=True, padx=(0, 10))

tk.Label(entry_box, text="  ", bg="#0a0f16").pack(side="left")

entry = tk.Entry(entry_box, textvariable=lookup_var, bg="#0a0f16", fg=TEXT,
                 insertbackground=TEXT, relief="flat", bd=0, font=F(11, True))
entry.pack(side="left", fill="both", expand=True, ipady=12)

RoundedButton(lookup_row, "Lookup", lookup_player, w=140, h=50, radius=18).pack(side="right")
entry.bind("<Return>", lambda e: lookup_player())  # QoL: press Enter

player_header = tk.Frame(right_frame, bg=CARD)
player_header.pack(fill="x", padx=18, pady=(8, 10))

skin_lbl = tk.Label(player_header, bg=CARD)
skin_lbl.pack(side="left", padx=(0, 14))

player_info_lbl = tk.Label(player_header, text="", bg=CARD, fg=TEXT, font=F(10, True), justify="left")
player_info_lbl.pack(side="left", fill="x", expand=True)

tiers_row = HScrollRow(right_frame, bg=CARD)
tiers_row.pack(fill="x", padx=18, pady=(10, 0))

root.after(50, startup)
root.mainloop()
