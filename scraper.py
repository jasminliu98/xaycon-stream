import requests
import json
import hashlib
import re
import time
import os
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# ─────────────────────────────────────────────────────────────────────────────
# TIMEZONE
# ─────────────────────────────────────────────────────────────────────────────

VN_TZ = timezone(timedelta(hours=7))


def now_vn() -> datetime:
    return datetime.now(tz=VN_TZ)


def parse_kickoff(start_time_str: str) -> datetime | None:
    """Parse ISO UTC startTime từ API → datetime VN."""
    if not start_time_str:
        return None
    try:
        s = start_time_str.strip().replace("Z", "+00:00")
        dt_utc = datetime.fromisoformat(s)
        return dt_utc.astimezone(VN_TZ)
    except Exception:
        return None


def format_time_hhmm(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.strftime("%H:%M")


def format_date_ddmm(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.strftime("%d/%m")


def parse_time_sort(dt: datetime | None) -> int:
    if dt is None:
        return 999_999_999
    return dt.month * 10_000_000 + dt.day * 10_000 + dt.hour * 100 + dt.minute


def is_within_48h(dt: datetime | None) -> bool:
    """Lọc trận trong khoảng -6h đến +48h so với hiện tại."""
    if dt is None:
        return True
    now   = now_vn()
    lower = now - timedelta(hours=6)
    upper = now + timedelta(hours=48)
    return lower <= dt <= upper


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    "https://sv2.xaycon3.live/",
    "Origin":     "https://sv2.xaycon3.live",
}

BASE_URL         = "https://sv2.xaycon3.live"
API_BASE         = "https://sv.xaycontv.xyz/api/v1/external/fixtures"
API_UNFINISHED   = f"{API_BASE}/unfinished"
API_FINISHED     = f"{API_BASE}/finished"

THUMBS_DIR    = "thumbs"
REPO_RAW      = os.environ.get("REPO_RAW", "")
THUMB_VERSION = "v1"

SPORT_MAP = {
    "bong-da":     "⚽ Bóng Đá",
    "bong-chuyen": "🏐 Bóng Chuyền",
    "billiards":   "🎱 Billiards",
    "cau-long":    "🏸 Cầu Lông",
    "bong-ro":     "🏀 Bóng Rổ",
    "tennis":      "🎾 Tennis",
    "esport":      "🎮 Esport",
    "dua-xe-f1":   "🏎️ Đua Xe F1",
    "bong-ban":    "🏓 Bóng Bàn",
    "boxing-mma":  "🥊 Boxing MMA",
}

SPORT_ORDER = [
    "bong-da", "bong-chuyen", "billiards", "cau-long",
    "bong-ro", "tennis", "esport", "dua-xe-f1", "bong-ban", "boxing-mma",
]


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def make_id(text: str, prefix: str) -> str:
    h = hashlib.md5(text.encode()).hexdigest()[:10]
    return f"{prefix}-{h}"


def fetch_image(url: str):
    try:
        res = requests.get(url, headers=HEADERS, timeout=8)
        return Image.open(BytesIO(res.content)).convert("RGBA")
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# THUMBNAIL
# ─────────────────────────────────────────────────────────────────────────────

def make_thumbnail(match: dict, channel_id: str) -> str:
    os.makedirs(THUMBS_DIR, exist_ok=True)
    cache_key = match.get("logo_a", "") + match.get("logo_b", "") + THUMB_VERSION
    logo_hash = hashlib.md5(cache_key.encode()).hexdigest()[:8]
    date_str  = now_vn().strftime("%Y%m%d")
    out_path  = f"{THUMBS_DIR}/{channel_id}_{logo_hash}_{date_str}.png"

    if os.path.exists(out_path):
        return out_path

    W, H = 1600, 1200
    HEADER_H = 180
    FOOTER_H = 160

    bg   = Image.new("RGB", (W, H), (245, 245, 248))
    draw = ImageDraw.Draw(bg)

    for y in range(HEADER_H, H - FOOTER_H):
        ratio = (y - HEADER_H) / (H - FOOTER_H - HEADER_H)
        gray  = int(248 - ratio * 18)
        draw.line([(0, y), (W, y)], fill=(gray, gray, gray + 4))

    draw.rectangle([(0, 0),            (W, HEADER_H)],  fill=(13, 20, 40))
    draw.rectangle([(0, H - FOOTER_H), (W, H)],         fill=(13, 20, 40))

    ACCENT = (220, 30, 40)
    draw.rectangle([(0, HEADER_H),         (W, HEADER_H + 5)],    fill=ACCENT)
    draw.rectangle([(0, H - FOOTER_H - 5), (W, H - FOOTER_H)],    fill=ACCENT)

    FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    try:
        font_vs   = ImageFont.truetype(FONT_BOLD, 160)
        font_time = ImageFont.truetype(FONT_BOLD, 100)
        font_team = ImageFont.truetype(FONT_BOLD, 58)
    except Exception:
        font_vs = font_time = font_team = ImageFont.load_default()

    content_top = HEADER_H + 5
    content_bot = H - FOOTER_H - 5
    content_h   = content_bot - content_top

    logo_size     = 360
    name_h        = 120
    time_h        = 110
    gap_logo_name = 40
    gap_name_time = 60

    total_block_h = logo_size + gap_logo_name + name_h + gap_name_time + time_h
    block_top     = content_top + (content_h - total_block_h) // 2

    logo_y       = block_top
    name_block_y = logo_y + logo_size + gap_logo_name
    name_center  = name_block_y + name_h // 2
    time_y       = name_block_y + name_h + gap_name_time + time_h // 2

    if match.get("logo_a"):
        img = fetch_image(match["logo_a"])
        if img:
            img = img.resize((logo_size, logo_size), Image.LANCZOS)
            x   = W // 4 - logo_size // 2
            bg.paste(img, (x, logo_y), img)

    if match.get("logo_b"):
        img = fetch_image(match["logo_b"])
        if img:
            img = img.resize((logo_size, logo_size), Image.LANCZOS)
            x   = W * 3 // 4 - logo_size // 2
            bg.paste(img, (x, logo_y), img)

    draw.text((W // 2, logo_y + logo_size // 2), "VS",
              fill=ACCENT, font=font_vs, anchor="mm")

    def draw_team_name(text, cx):
        max_width = W // 2 - 60
        font_size = 58
        f = font_team
        while font_size >= 28:
            try:
                f = ImageFont.truetype(FONT_BOLD, font_size)
            except Exception:
                f = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), text, font=f)
            if (bbox[2] - bbox[0]) <= max_width:
                break
            font_size -= 3
        draw.text((cx, name_center), text, fill=(20, 20, 20), font=f, anchor="mm")

    if match.get("team_a"):
        draw_team_name(match["team_a"], W // 4)
    if match.get("team_b"):
        draw_team_name(match["team_b"], W * 3 // 4)

    dt = match.get("kickoff_dt")
    time_fmt = format_time_hhmm(dt)
    date_fmt = format_date_ddmm(dt)
    time_display = f"{time_fmt} {date_fmt}".strip() if time_fmt else ""

    if time_display:
        font_size = 100
        f_time = font_time
        while font_size >= 40:
            try:
                f_time = ImageFont.truetype(FONT_BOLD, font_size)
            except Exception:
                f_time = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), time_display, font=f_time)
            if (bbox[2] - bbox[0]) <= W - 100:
                break
            font_size -= 4
        draw.text((W // 2 + 4, time_y + 4), time_display,
                  fill=ACCENT, font=f_time, anchor="mm")
        draw.text((W // 2, time_y), time_display,
                  fill=(15, 15, 15), font=f_time, anchor="mm")

    if match.get("league"):
        league_text = match["league"].upper()
        font_size   = 62
        f           = None
        while font_size >= 28:
            try:
                f = ImageFont.truetype(FONT_BOLD, font_size)
            except Exception:
                f = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), league_text, font=f)
            if (bbox[2] - bbox[0]) <= W - 60:
                break
            font_size -= 3
        draw.text((W // 2, HEADER_H // 2), league_text,
                  fill=(255, 255, 255), font=f, anchor="mm")

    draw.rectangle([(0, 0), (W - 1, H - 1)], outline=(180, 180, 180), width=3)
    bg.save(out_path, "PNG", optimize=True)
    return out_path


def cleanup_old_thumbs(days: int = 3):
    if not os.path.exists(THUMBS_DIR):
        return
    cutoff  = now_vn() - timedelta(days=days)
    removed = 0
    for fname in os.listdir(THUMBS_DIR):
        if not fname.endswith(".png"):
            continue
        m = re.search(r'_(\d{8})\.png$', fname)
        if not m:
            fpath = os.path.join(THUMBS_DIR, fname)
            try:
                os.remove(fpath)
                removed += 1
            except Exception:
                pass
            continue
        try:
            file_date = datetime.strptime(m.group(1), "%Y%m%d").replace(tzinfo=VN_TZ)
        except ValueError:
            continue
        if file_date < cutoff:
            fpath = os.path.join(THUMBS_DIR, fname)
            try:
                os.remove(fpath)
                removed += 1
            except Exception:
                pass
    if removed:
        print(f"Da xoa {removed} thumbnail cu (>{days} ngay)")


# ─────────────────────────────────────────────────────────────────────────────
# FETCH API
# ─────────────────────────────────────────────────────────────────────────────

def fetch_fixtures(url: str) -> list:
    """Gọi API lấy danh sách trận, trả về list item thô."""
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        data = res.json()
        if data.get("success") and isinstance(data.get("data"), list):
            return data["data"]
        return []
    except Exception as e:
        print(f"  Loi fetch {url}: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# PARSE MATCHES
# ─────────────────────────────────────────────────────────────────────────────

def get_stream_url(commentators: list) -> str | None:
    """
    Lấy stream URL từ commentator có priority thấp nhất.
    Ưu tiên quality: FHD > HD > SD theo priority.
    """
    if not commentators:
        return None

    # Sắp xếp commentator theo priority tăng dần
    sorted_commentators = sorted(commentators, key=lambda c: c.get("priority", 999))

    for fc in sorted_commentators:
        commentator = fc.get("commentator", {})
        streams = commentator.get("streams", [])
        if not streams:
            continue

        # Sắp xếp stream theo priority
        sorted_streams = sorted(streams, key=lambda s: s.get("priority", 999))

        # Ưu tiên FHD
        for s in sorted_streams:
            if s.get("name", "").upper() == "FHD" and s.get("sourceUrl"):
                return s["sourceUrl"]
        # Fallback HD
        for s in sorted_streams:
            if s.get("name", "").upper() == "HD" and s.get("sourceUrl"):
                return s["sourceUrl"]
        # Fallback bất kỳ
        for s in sorted_streams:
            if s.get("sourceUrl"):
                return s["sourceUrl"]

    return None


def get_blv_names(commentators: list) -> str:
    """Lấy tên BLV, sắp xếp theo priority."""
    sorted_commentators = sorted(commentators, key=lambda c: c.get("priority", 999))
    names = []
    for fc in sorted_commentators:
        nickname = fc.get("commentator", {}).get("nickname", "")
        if nickname:
            names.append(nickname)
    return ", ".join(names)


def get_matches() -> list:
    print("Lay tran chua ket thuc (unfinished)...")
    raw_items = fetch_fixtures(API_UNFINISHED)
    matches   = []

    for item in raw_items:
        slug        = item.get("slug", "")
        is_live     = item.get("isLive", False)
        start_time  = item.get("startTime", "")
        sport_data  = item.get("sport") or {}
        league_data = item.get("league") or {}
        home_team   = item.get("homeTeam") or {}
        away_team   = item.get("awayTeam") or {}
        commentators = item.get("fixtureCommentators") or []

        if not slug:
            continue

        # Bỏ qua trận không có BLV / stream
        if not commentators:
            continue

        kickoff_dt = parse_kickoff(start_time)

        # Lọc theo thời gian
        if not is_within_48h(kickoff_dt):
            continue

        sport_slug = sport_data.get("slug", "unknown")
        team_a     = home_team.get("name", "").strip()
        team_b     = away_team.get("name", "").strip()
        name       = item.get("title", "") or (f"{team_a} vs {team_b}" if team_a and team_b else slug[:50])

        matches.append({
            "match_id":   slug,
            "sport_slug": sport_slug,
            "name":       name,
            "kickoff_dt": kickoff_dt,
            "time_sort":  parse_time_sort(kickoff_dt),
            "team_a":     team_a,
            "team_b":     team_b,
            "logo_a":     home_team.get("logoUrl", ""),
            "logo_b":     away_team.get("logoUrl", ""),
            "league":     league_data.get("name", ""),
            "blv":        get_blv_names(commentators),
            "stream_url": get_stream_url(commentators),
            "is_live":    is_live,
            "is_hot":     item.get("isHot", False),
        })

    # LIVE lên đầu, sau đó sắp theo giờ
    matches.sort(key=lambda m: (0 if m["is_live"] else 1, m["time_sort"]))
    return matches


# ─────────────────────────────────────────────────────────────────────────────
# BUILD CHANNEL JSON
# ─────────────────────────────────────────────────────────────────────────────

def build_channel(match: dict, thumb_url: str = "") -> dict:
    uid    = make_id(match["match_id"], "xc")
    src_id = make_id(match["match_id"], "src")
    ct_id  = make_id(match["match_id"], "ct")
    st_id  = make_id(match["match_id"], "st")

    stream_url   = match.get("stream_url")
    stream_links = []
    if stream_url:
        lnk_id = make_id(stream_url, "lnk")
        stream_links.append({
            "id":      lnk_id,
            "name":    "Link FHD",
            "type":    "hls",
            "default": True,
            "url":     stream_url,
            "request_headers": [
                {"key": "Referer",    "value": "https://sv2.xaycon3.live/"},
                {"key": "Origin",     "value": "https://sv2.xaycon3.live"},
                {"key": "User-Agent", "value": "Mozilla/5.0"},
            ],
        })

    label_text  = "● LIVE" if match["is_live"] else "🕐 Sắp"
    label_color = "#ff4444" if match["is_live"] else "#aaaaaa"

    dt       = match.get("kickoff_dt")
    time_fmt = format_time_hhmm(dt)
    date_fmt = format_date_ddmm(dt)

    display_name = match["name"]
    if time_fmt and date_fmt:
        display_name = f"{match['name']} | {time_fmt} {date_fmt}"
    elif time_fmt:
        display_name = f"{match['name']} | {time_fmt}"

    channel = {
        "id":            uid,
        "name":          display_name,
        "type":          "single",
        "display":       "thumbnail-only",
        "enable_detail": False,
        "labels": [{"text": label_text, "position": "top-left",
                    "color": "#00000080", "text_color": label_color}],
        "sources": [{
            "id":   src_id,
            "name": "XayConTV",
            "contents": [{
                "id":   ct_id,
                "name": match["name"],
                "streams": [{"id": st_id, "name": "XC", "stream_links": stream_links}],
            }],
        }],
        "org_metadata": {
            "league":     match.get("league",      ""),
            "team_a":     match.get("team_a",      ""),
            "team_b":     match.get("team_b",      ""),
            "logo_a":     match.get("logo_a",      ""),
            "logo_b":     match.get("logo_b",      ""),
            "time":       time_fmt,
            "date":       date_fmt,
            "blv":        match.get("blv",         ""),
            "is_live":    match["is_live"],
            "sport_slug": match.get("sport_slug",  ""),
        },
    }

    if thumb_url:
        channel["image"] = {
            "padding":          1,
            "background_color": "#ffffff",
            "display":          "contain",
            "url":              thumb_url,
            "width":            1600,
            "height":           1200,
        }

    return channel


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(THUMBS_DIR, exist_ok=True)
    cleanup_old_thumbs(days=3)
    print(f"Gio VN hien tai : {now_vn().strftime('%H:%M %d/%m/%Y')}")

    matches = get_matches()

    live_count = sum(1 for m in matches if m["is_live"])
    print(f"Tong: {len(matches)} | LIVE: {live_count} | Sap: {len(matches) - live_count}\n")

    sport_channels: dict[str, list] = {s: [] for s in SPORT_ORDER}

    for i, match in enumerate(matches):
        sport_slug = match["sport_slug"]
        status     = "LIVE" if match["is_live"] else "SAP"
        time_fmt   = format_time_hhmm(match.get("kickoff_dt"))
        date_fmt   = format_date_ddmm(match.get("kickoff_dt"))
        stream_log = match["stream_url"] or "CHUA CO LINK"
        print(f"[{status} {i+1}/{len(matches)}] {match['name']} ({time_fmt} {date_fmt}) | BLV: {match['blv']} | stream: {stream_log[:60]}")

        uid       = make_id(match["match_id"], "xc")
        cache_key = match.get("logo_a", "") + match.get("logo_b", "") + THUMB_VERSION
        logo_hash = hashlib.md5(cache_key.encode()).hexdigest()[:8]

        thumb_path = make_thumbnail(match, uid)
        thumb_url  = f"{REPO_RAW}/{thumb_path}?v={logo_hash}" if REPO_RAW else ""

        channel = build_channel(match, thumb_url)

        if sport_slug not in sport_channels:
            sport_channels[sport_slug] = []
        sport_channels[sport_slug].append(channel)

        time.sleep(0.1)

    groups = []
    for sport_slug in SPORT_ORDER:
        channels = sport_channels.get(sport_slug, [])
        if not channels:
            continue

        sport_label = SPORT_MAP.get(sport_slug, "🏅 Thể Thao")
        live_cnt    = sum(1 for ch in channels
                         if ch.get("org_metadata", {}).get("is_live", False))
        sport_name  = f"{sport_label} ({live_cnt} LIVE)" if live_cnt > 0 else sport_label

        groups.append({
            "id":            f"sport_{sport_slug}",
            "name":          sport_name,
            "display":       "vertical",
            "grid_number":   2,
            "enable_detail": False,
            "channels":      channels,
        })

    # Các môn không có trong SPORT_ORDER
    for sport_slug, channels in sport_channels.items():
        if sport_slug not in SPORT_ORDER and channels:
            live_cnt   = sum(1 for ch in channels
                             if ch.get("org_metadata", {}).get("is_live", False))
            sport_name = f"🏅 Thể Thao ({live_cnt} LIVE)" if live_cnt > 0 else "🏅 Thể Thao"
            groups.append({
                "id":            f"sport_{sport_slug}",
                "name":          sport_name,
                "display":       "vertical",
                "grid_number":   2,
                "enable_detail": False,
                "channels":      channels,
            })

    output = {
        "id":          "xaycon",
        "url":         BASE_URL,
        "name":        "XayConTV",
        "color":       "#3b82f6",
        "grid_number": 3,
        "image":       {"type": "cover", "url": "https://sv2.xaycon3.live/favicon.ico"},
        "groups":      groups,
    }

    staging = "output_staging.json"
    with open(staging, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total = sum(len(g["channels"]) for g in groups)

    def normalize(path):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            return json.dumps(d, sort_keys=True, ensure_ascii=False)
        except Exception:
            return ""

    old_norm = normalize("output.json")
    new_norm = normalize(staging)

    if old_norm != new_norm:
        os.replace(staging, "output.json")
        print(f"\nXong! {total} kenh, {len(groups)} mon the thao -> output.json (DA CAP NHAT)")
    else:
        os.remove(staging)
        print(f"\nXong! {total} kenh, {len(groups)} mon the thao -> Khong co thay doi, giu nguyen output.json")


if __name__ == "__main__":
    main()
