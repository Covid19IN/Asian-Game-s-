"""
Asian Games 2026 — India medalists
Vertical 1080×1920 · 30fps · HLS-ready frame sequence
"""
import json, os, sys, math
from pathlib import Path
import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ─────────── Config ───────────
W, H        = 1080, 1920
FPS         = 30
DATA_IN     = "docs/data/athletes.json"
PHOTO_DIR   = "docs/video-photos"
FRAME_DIR   = "build/frames"
MAX_CARDS   = 12                # top N athletes to feature

INTRO_FRAMES  = 90              # 3.0 s
CARD_FRAMES   = 75              # 2.5 s each
OUTRO_FRAMES  = 120             # 4.0 s
TRANS_FRAMES  = 18              # slide-in duration

# ─────────── Palette ───────────
BG_TOP    = (5,  8,  22)
BG_BOT    = (14, 10, 40)
CARD_BG   = (18, 25, 52)
CARD_BR   = (48, 60, 100)
GOLD      = (255, 207, 77)
SILVER    = (205, 214, 232)
BRONZE    = (227, 154, 90)
WHITE     = (255, 255, 255)
MUTED     = (140, 150, 180)
DIM       = (90, 100, 130)

MEDAL_COLOR = {"gold": GOLD, "silver": SILVER, "bronze": BRONZE}

# ─────────── Fonts ───────────
FONT_DIRS = [
    "/usr/share/fonts/truetype/roboto/hinted/",
    "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/",
    "/usr/share/fonts/truetype/inter/",
    "/usr/share/fonts/truetype/dejavu/",
]
def _find(names):
    for d in FONT_DIRS:
        for n in names:
            p = d + n
            if os.path.exists(p): return p
    return None

F_BOLD = _find(["Roboto-Bold.ttf", "Inter-Bold.ttf", "DejaVuSans-Bold.ttf"])
F_MED  = _find(["Roboto-Medium.ttf", "Inter-SemiBold.ttf", "DejaVuSans-Bold.ttf"])
F_REG  = _find(["Roboto-Regular.ttf", "Inter-Regular.ttf", "DejaVuSans.ttf"])

def font(size, w="reg"):
    return ImageFont.truetype({"bold": F_BOLD, "med": F_MED, "reg": F_REG}[w], size)

# ─────────── Background (cached) ───────────
_bg = None
def background():
    global _bg
    if _bg is None:
        t   = np.linspace(0, 1, H).reshape(-1, 1, 1)
        top = np.array(BG_TOP).reshape(1, 1, 3).astype(np.float32)
        bot = np.array(BG_BOT).reshape(1, 1, 3).astype(np.float32)
        arr = (top * (1 - t) + bot * t).astype(np.uint8)
        arr = np.repeat(arr, W, axis=1)
        _bg = Image.fromarray(arr, "RGB")
    return _bg.copy()

# ─────────── Easing ───────────
def ease_out(t):    return 1 - (1 - t) ** 3
def ease_io(t):     return t * t * (3 - 2 * t)
def lerp(a, b, t):  return a + (b - a) * t
def clamp(v, lo=0, hi=1): return max(lo, min(hi, v))

# ─────────── Photos ───────────
_photo_cache = {}
def load_photo(url):
    if not url: return None
    if url in _photo_cache: return _photo_cache[url]
    fn   = url.rsplit("/", 1)[-1]
    path = f"{PHOTO_DIR}/{fn}"
    if not os.path.exists(path):
        try:
            r = requests.get(url, timeout=15)
            if r.ok and r.headers.get("content-type", "").startswith("image"):
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                with open(path, "wb") as f: f.write(r.content)
        except Exception:
            pass
    try:
        img = Image.open(path).convert("RGBA")
        _photo_cache[url] = img
        return img
    except Exception:
        _photo_cache[url] = None
        return None

def circular_photo(img, size, ring_color, ring_w=10):
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if img is None:
        d = ImageDraw.Draw(out)
        d.ellipse((0, 0, size, size), fill=(40, 50, 90))
        d.text((size/2, size/2), "?", font=font(int(size*0.4), "bold"),
               fill=(140, 150, 180), anchor="mm")
    else:
        w, h = img.size
        s = min(w, h)
        img = img.crop(((w-s)//2, (h-s)//2, (w+s)//2, (h+s)//2)).resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
        out.paste(img, (0, 0), mask)

    d = ImageDraw.Draw(out)
    d.ellipse((0, 0, size-1, size-1), outline=ring_color + (255,), width=ring_w)
    return out

# ─────────── Data prep ───────────
def is_numeric(r): return str(r or "").isdigit()

def pick_athletes(data):
    rank = {"gold": 3, "silver": 2, "bronze": 1}
    out = []
    for a in data:
        if not is_numeric(a.get("reg")): continue
        if not a.get("photo_url"): continue
        medals = a.get("medals") or []
        if not medals: continue

        golds   = sum(1 for m in medals if m["medal"] == "gold")
        silvers = sum(1 for m in medals if m["medal"] == "silver")
        bronzes = sum(1 for m in medals if m["medal"] == "bronze")
        score   = golds * 100 + silvers * 10 + bronzes

        top = sorted(medals, key=lambda m: rank.get(m["medal"], 0), reverse=True)[0]
        out.append({
            "reg": a["reg"],
            "name": a["name"],
            "disc_desc": a["disc_desc"],
            "event": top["event"],
            "medal": top["medal"],
            "score": score,
            "photo_url": a["photo_url"],
            "medal_count": len(medals),
        })

    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:MAX_CARDS]

# ─────────── Scenes ───────────
def draw_intro(img, prog, total, bd):
    d = ImageDraw.Draw(img, "RGBA")
    p = ease_out(clamp(prog))

    d.text((W/2, lerp(600, 520, p)), "INDIA",
           font=font(150, "bold"), fill=WHITE + (int(255*p),), anchor="mt")
    d.text((W/2, lerp(810, 760, p)), "ASIAN GAMES 2026",
           font=font(42, "med"), fill=GOLD + (int(255*p),), anchor="mt")

    if p > 0.3:
        cp = clamp((p - 0.3) / 0.4)
        shown = int(total * cp)
        d.text((W/2, 1000), str(shown),
               font=font(240, "bold"), fill=WHITE + (int(255*p),), anchor="mt")
        d.text((W/2, 1280), "MEDALS",
               font=font(48, "med"), fill=MUTED + (int(255*p),), anchor="mt")

    if p > 0.7:
        bp = clamp((p - 0.7) / 0.3)
        items = [("GOLD", bd["gold"], GOLD), ("SILVER", bd["silver"], SILVER), ("BRONZE", bd["bronze"], BRONZE)]
        x0 = (W - (3*260 + 2*20)) // 2
        for i, (label, n, col) in enumerate(items):
            x = x0 + i * 280
            d.rounded_rectangle((x, 1400, x+260, 1540), radius=24,
                fill=(20, 28, 56, int(230*bp)), outline=col + (int(180*bp),), width=2)
            d.text((x+130, 1430), str(n), font=font(64, "bold"),
                   fill=col + (int(255*bp),), anchor="mt")
            d.text((x+130, 1505), label, font=font(22, "med"),
                   fill=MUTED + (int(255*bp),), anchor="mt")

def draw_card(img, ath, photo, prog, idx, total):
    d  = ImageDraw.Draw(img, "RGBA")
    p  = ease_out(clamp(prog))

    # progress bar
    bar_w = int(W * ((idx + clamp(prog)) / total))
    d.rectangle((0, 0, W, 8), fill=(30, 40, 70, 255))
    d.rectangle((0, 0, bar_w, 8), fill=GOLD + (255,))

    # counter
    d.text((W-50, 50), f"{idx+1}/{total}",
           font=font(30, "med"), fill=MUTED + (255,), anchor="rt")

    y_slide = int((1 - p) * 120)
    cx, cy  = 80, 480 + y_slide
    cw, ch  = W - 160, 940
    mc = MEDAL_COLOR[ath["medal"]]

    # card panel
    d.rounded_rectangle((cx, cy, cx+cw, cy+ch), radius=52,
        fill=CARD_BG + (int(245*clamp(p*1.4)),),
        outline=CARD_BR + (int(255*clamp(p*1.4)),), width=2)

    # medal strip top
    sp = clamp(p * 1.6)
    d.rounded_rectangle((cx+36, cy+36, cx+36+int((cw-72)*sp), cy+60),
        radius=14, fill=mc + (255,))

    # photo
    psize = 380
    px = cx + (cw - psize) // 2
    py = cy + 130
    cp = circular_photo(photo, psize, mc, ring_w=12)
    img.paste(cp, (px, py), cp)

    # medal pill
    if p > 0.35:
        bp = clamp((p - 0.35) / 0.35)
        bw, bh = 240, 72
        bx = cx + (cw - bw) // 2
        by = py + psize + 40
        d.rounded_rectangle((bx, by, bx+bw, by+bh), radius=36,
            fill=mc + (int(255*bp),))
        label = ath["medal"].upper()
        if ath["medal_count"] > 1: label += f"  ×{ath['medal_count']}"
        d.text((bx+bw/2, by+bh/2+2), label, font=font(30, "bold"),
               fill=(5, 8, 22, int(255*bp)), anchor="mm")
    else:
        by = py + psize + 40

    # name
    if p > 0.5:
        np_ = clamp((p - 0.5) / 0.35)
        name = ath["name"]
        fname = font(64, "bold")
        ny = by + 130
        if d.textlength(name, font=fname) > cw - 120:
            words = name.split()
            mid = len(words)//2 if len(words) > 2 else 1
            l1, l2 = " ".join(words[:mid]), " ".join(words[mid:])
            d.text((cx+cw/2, ny), l1, font=fname, fill=WHITE + (int(255*np_),), anchor="mt")
            d.text((cx+cw/2, ny+76), l2, font=fname, fill=WHITE + (int(255*np_),), anchor="mt")
            ny += 76
        else:
            d.text((cx+cw/2, ny), name, font=fname, fill=WHITE + (int(255*np_),), anchor="mt")
        sy = ny + 110
    else:
        sy = by + 240

    # sport
    if p > 0.65:
        sp_ = clamp((p - 0.65) / 0.35)
        d.text((cx+cw/2, sy), ath["disc_desc"].upper(), font=font(34, "med"),
               fill=MUTED + (int(255*sp_),), anchor="mt")

    # event
    if p > 0.78:
        ep = clamp((p - 0.78) / 0.22)
        ev = ath["event"]
        fe = font(26, "reg")
        while d.textlength(ev, font=fe) > cw - 100 and len(ev) > 5:
            ev = ev[:-2] + "…"
        d.text((cx+cw/2, sy+60), ev, font=fe, fill=DIM + (int(255*ep),), anchor="mt")

def draw_outro(img, prog, total, bd):
    d = ImageDraw.Draw(img, "RGBA")
    p = ease_out(clamp(prog))

    d.text((W/2, 720), "INDIA", font=font(140, "bold"),
           fill=WHITE + (int(255*p),), anchor="mt")
    d.text((W/2, 900), f"{total} MEDALS", font=font(72, "bold"),
           fill=GOLD + (int(255*p),), anchor="mt")

    y = 1180
    for label, n, col in [("GOLD", bd["gold"], GOLD),
                          ("SILVER", bd["silver"], SILVER),
                          ("BRONZE", bd["bronze"], BRONZE)]:
        d.text((W/2-80, y), label, font=font(42, "med"),
               fill=col + (int(255*p),), anchor="rm")
        d.text((W/2+80, y), str(n), font=font(54, "bold"),
               fill=WHITE + (int(255*p),), anchor="lm")
        y += 110

    d.text((W/2, 1750), "FOLLOW FOR LIVE UPDATES", font=font(30, "med"),
           fill=MUTED + (int(255*p),), anchor="mt")

# ─────────── Render ───────────
def render():
    print("Loading athletes…")
    with open(DATA_IN, encoding="utf-8") as f:
        data = json.load(f)

    athletes = pick_athletes(data)
    if not athletes:
        print("No athletes with photos. Aborting."); sys.exit(1)

    # totals
    seen = set(); bd = {"gold": 0, "silver": 0, "bronze": 0}
    for a in data:
        for m in a.get("medals", []):
            k = m["medal"] + "|" + m["event"]
            if k in seen: continue
            seen.add(k)
            if m["medal"] in bd: bd[m["medal"]] += 1
    total = sum(bd.values())
    print(f"Total medals: {total}  {bd}")
    print(f"Cards: {len(athletes)}")

    # preload
    print("Loading photos…")
    for a in athletes:
        a["_photo"] = load_photo(a["photo_url"])

    # clean
    import shutil
    shutil.rmtree(FRAME_DIR, ignore_errors=True)
    Path(FRAME_DIR).mkdir(parents=True, exist_ok=True)

    n = 0
    def save(img):
        nonlocal n
        img.convert("RGB").save(f"{FRAME_DIR}/f_{n:05d}.png")
        n += 1

    # INTRO
    print("Intro…")
    for f in range(INTRO_FRAMES):
        img = background().convert("RGBA")
        draw_intro(img, f / (INTRO_FRAMES - 1), total, bd)
        save(img)

    # CARDS
    print(f"Cards ({len(athletes)})…")
    for i, ath in enumerate(athletes):
        for f in range(CARD_FRAMES):
            img = background().convert("RGBA")
            if f < TRANS_FRAMES:
                prog = (f / TRANS_FRAMES) * 0.5
            else:
                prog = 0.5 + ((f - TRANS_FRAMES) / (CARD_FRAMES - TRANS_FRAMES)) * 0.5
            draw_card(img, ath, ath["_photo"], prog, i, len(athletes))
            save(img)

    # OUTRO
    print("Outro…")
    for f in range(OUTRO_FRAMES):
        img = background().convert("RGBA")
        draw_outro(img, f / (OUTRO_FRAMES - 1), total, bd)
        save(img)

    print(f"✅ {n} frames → {FRAME_DIR}")

if __name__ == "__main__":
    render()
