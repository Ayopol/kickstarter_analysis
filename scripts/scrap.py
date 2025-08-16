# scrap.py
import re, json, requests, html
from urllib.parse import urlsplit, urlunsplit
from datetime import datetime, timedelta, timezone

# ---------- constants ----------
MONTHS = {
    "jan":1,"january":1, "feb":2,"february":2, "mar":3,"march":3, "apr":4,"april":4,
    "may":5, "jun":6,"june":6, "jul":7,"july":7, "aug":8,"august":8,
    "sep":9,"sept":9,"september":9, "oct":10,"october":10, "nov":11,"november":11,
    "dec":12,"december":12
}
TZ_OFFSETS = {"UTC":0,"GMT":0,"CET":1,"CEST":2,"BST":1,"PST":-8,"PDT":-7,"EST":-5,"EDT":-4}

CATS = [
    "Film & Video","Music","Publishing","Games","Technology","Design","Art","Food",
    "Fashion","Theater","Comics","Photography","Crafts","Journalism","Dance"
]

# ---------- small helpers ----------
def _parse_amount(s):
    if not s: return None
    s = (s.replace("\u202f"," ").replace("\xa0"," ").replace("’","").replace("'","")
           .replace(" ", "").replace(",", ""))
    try: return float(re.sub(r"[^0-9.]", "", s))
    except: return None

def _parse_deadline(text):
    if not text: return None, None
    m = re.search(
        r"([A-Za-z]{3,9})\s+(\d{1,2})(?:,)?\s+(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)?\s*([A-Z]{2,4})",
        text, re.I
    )
    if not m: return None, None
    mon_token = m.group(1).lower()
    mon = MONTHS.get(mon_token) or MONTHS.get(mon_token[:3])
    if not mon: return None, None
    day, year = int(m.group(2)), int(m.group(3))
    hh, mm = int(m.group(4)), int(m.group(5))
    ampm = (m.group(6) or "").upper()
    if ampm == "PM" and hh < 12: hh += 12
    if ampm == "AM" and hh == 12: hh = 0
    tz = (m.group(7) or "UTC").upper()
    offset = TZ_OFFSETS.get(tz, 0)
    dt_utc = datetime(year, mon, day, hh, mm) - timedelta(hours=offset)
    dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc.isoformat(), int(dt_utc.timestamp())

def _base_url(url: str) -> str:
    parts = list(urlsplit(url))
    parts[3] = ""      # drop query
    parts[2] = parts[2].rstrip("/")
    return urlunsplit(parts)

def _deep_find_first(obj, want_keys):
    """Traverse dict/list; return first (key, value) where key in want_keys (case-insensitive)."""
    seen = set()
    stack = [obj]
    want = {k.lower() for k in want_keys}
    while stack:
        cur = stack.pop()
        if id(cur) in seen: continue
        seen.add(id(cur))
        if isinstance(cur, dict):
            for k, v in cur.items():
                if str(k).lower() in want:
                    return k, v
            for v in cur.values():
                stack.append(v)
        elif isinstance(cur, list):
            for v in cur: stack.append(v)
    return None, None

def _coerce_float(x):
    if x is None: return None
    try:
        return float(x)
    except Exception:
        try:
            return float(re.sub(r"[^0-9.\-]", "", str(x)))
        except Exception:
            return None

def _deep_get(d, keys):
    if not isinstance(d, dict): return None
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None

def _extract_usd_goal_usd(proj: dict, next_json: dict | None) -> float | None:
    """Try direct USD fields → cents → goal*rate → __NEXT_DATA__ fallbacks."""
    if not isinstance(proj, dict):
        proj = {}

    # 1) Direct USD names
    for key in ["usd_goal", "usd_goal_real", "goal_usd", "goal_usd_real", "converted_goal_usd"]:
        v = _coerce_float(proj.get(key))
        if v and v > 0:
            return round(v, 2)

    # 2) Cents variants
    for key in ["usd_goal_cents", "goal_usd_cents"]:
        v = _coerce_float(proj.get(key))
        if v and v > 0:
            return round(v/100.0, 2)

    # 3) Local goal * rate
    goal_local = _coerce_float(_deep_get(proj, ["goal", "goal_local"]))
    if goal_local and goal_local > 0:
        rate = _coerce_float(_deep_get(proj, ["fx_rate", "static_usd_rate", "usd_rate", "fx_rate_static"]))
        if rate and rate > 0:
            return round(goal_local * rate, 2)

    # 4) __NEXT_DATA__ fallback
    if next_json and isinstance(next_json, dict):
        _, g = _deep_find_first(next_json, {"usdGoal","usd_goal","usd_goal_real","goal_usd","goal"})
        g = _coerce_float(g)
        if g and g > 0:
            return round(g, 2)
        _, r = _deep_find_first(next_json, {"fx_rate","usd_rate","static_usd_rate","fxRate","usdRate","staticUsdRate"})
        r = _coerce_float(r)
        if g and g > 0 and r and r > 0:
            return round(g * r, 2)
        _, g2 = _deep_find_first(next_json, {"goal","goal_local"})
        g2 = _coerce_float(g2)
        if g2 and g2 > 0 and r and r > 0:
            return round(g2 * r, 2)

    return None

# ---------- Selenium driver (Firefox headless: OK sur Streamlit) ----------
def _make_driver():
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    opts = FirefoxOptions()
    opts.add_argument("--headless")
    # force english to stabilize UI strings like "goal"
    opts.set_preference("intl.accept_languages", "en-US,en")
    return webdriver.Firefox(options=opts)

# ---------- requests client ----------
def _make_session(base):
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": base,
        "Connection": "keep-alive",
    })
    return s

# ---------- requests-only fallback for metadata ----------
def _requests_fallback(base):
    s = _make_session(base)

    title = main_category = country_name = None
    usd_goal_real = usd_pledged_real = None
    deadline_iso = launched_iso = None
    deadline_unix = launched_unix = None

    # HTML
    html_text = ""
    try:
        r = s.get(base, timeout=15)
        if r.status_code == 403:
            r = s.get(base, timeout=15, headers={**s.headers, "Pragma": "no-cache", "Cache-Control": "no-cache"})
        r.raise_for_status()
        html_text = r.text
    except Exception:
        pass

    next_json = None
    if html_text:
        m = re.search(r'(?is)<script\s+id=["\']__NEXT_DATA__["\']\s+type=["\']application/json["\']\s*>(.*?)</script>', html_text)
        if m:
            try: next_json = json.loads(m.group(1))
            except Exception: next_json = None

        mtitle = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', html_text, re.I|re.S)
        if mtitle:
            title = html.unescape(mtitle.group(1)).strip()
        else:
            m2 = re.search(r'(?is)<title>(.*?)</title>', html_text)
            if m2:
                title = html.unescape(m2.group(1)).replace(" — Kickstarter", "").strip()

        m_dead = re.search(r'(?is)data-test-id=["\']deadline-exists["\'][^>]*>(.*?)</span>', html_text)
        if m_dead and not deadline_unix:
            dtext = html.unescape(re.sub(r'(?is)<[^>]+>', ' ', m_dead.group(1))).strip()
            deadline_iso, deadline_unix = _parse_deadline(dtext)

    # /stats.json
    proj = {}
    try:
        rj = s.get(base + "/stats.json", timeout=15, headers={
            **s.headers,
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
        })
        rj.raise_for_status()
        sj = rj.json()
        proj = (sj.get("data", {}).get("project")
                or sj.get("project")
                or (sj if isinstance(sj, dict) else {}))

        # pledged (USD if possible)
        val_usd_direct = proj.get("usd_pledged") or proj.get("usd_pledged_real") or proj.get("converted_pledged_amount")
        if val_usd_direct is not None:
            try: usd_pledged_real = round(float(val_usd_direct), 2)
            except Exception: usd_pledged_real = _parse_amount(str(val_usd_direct))
        if usd_pledged_real is None:
            pledged_val = proj.get("pledged")
            fx_rate = proj.get("fx_rate") or proj.get("static_usd_rate") or proj.get("usd_rate")
            try:
                if pledged_val is not None and fx_rate:
                    usd_pledged_real = round(float(pledged_val) * float(fx_rate), 2)
                elif pledged_val is not None:
                    usd_pledged_real = round(float(pledged_val), 2)
            except Exception:
                pass

        # goal (robust, USD if possible)
        if usd_goal_real is None:
            usd_goal_real = _extract_usd_goal_usd(proj, next_json)

        # country
        country_code = (proj.get("country") or proj.get("country_code"))
        if not country_code:
            loc = proj.get("location") or {}
            if isinstance(loc, dict):
                country_code = loc.get("country") or loc.get("country_code")
        if not country_code:
            creator = proj.get("creator") or {}
            if isinstance(creator, dict) and isinstance(creator.get("location"), dict):
                country_code = creator["location"].get("country")
        if country_code:
            ISO2_TO_NAME = {
                "US":"United States","GB":"United Kingdom","CA":"Canada","AU":"Australia","NZ":"New Zealand",
                "JP":"Japan","DE":"Germany","FR":"France","ES":"Spain","IT":"Italy","NL":"Netherlands",
                "SE":"Sweden","NO":"Norway","DK":"Denmark","CH":"Switzerland","HK":"Hong Kong","SG":"Singapore",
                "MX":"Mexico","BR":"Brazil","IE":"Ireland","BE":"Belgium","AT":"Austria","KR":"South Korea",
                "CN":"China","TW":"Taiwan"
            }
            country_name = ISO2_TO_NAME.get(str(country_code).upper(), country_code)

        # category
        cat_obj = proj.get("category") or {}
        if isinstance(cat_obj, dict):
            parent_name = cat_obj.get("parent_name")
            if parent_name:
                for c in CATS:
                    if parent_name.lower() == c.lower():
                        main_category = c; break
                if not main_category: main_category = parent_name
            if not main_category:
                slug = cat_obj.get("slug") or ""
                if "/" in slug:
                    main = slug.split("/", 1)[0]
                    mapping = {
                        "film & video":"Film & Video","music":"Music","publishing":"Publishing","games":"Games",
                        "technology":"Technology","design":"Design","art":"Art","food":"Food","fashion":"Fashion",
                        "theater":"Theater","comics":"Comics","photography":"Photography","crafts":"Crafts",
                        "journalism":"Journalism","dance":"Dance"
                    }
                    main_category = mapping.get(main.lower(), main.title())

        # launch + deadline
        state = proj.get("state")
        launched_ts = proj.get("launched_at") or (proj.get("state_changed_at") if state == "live" else None)
        if launched_ts:
            try:
                launched_unix = int(float(launched_ts))
                launched_iso = datetime.fromtimestamp(launched_unix, tz=timezone.utc).isoformat()
            except Exception:
                pass
        if not deadline_unix:
            for k in ("deadline","deadline_at","deadline_ts","deadline_time","deadline_unix"):
                if proj.get(k) is not None:
                    try:
                        deadline_unix = int(float(proj[k]))
                        deadline_iso = datetime.fromtimestamp(deadline_unix, tz=timezone.utc).isoformat()
                        break
                    except Exception:
                        pass
    except Exception:
        pass

    return {
        "title": title,
        "main_category": main_category,
        "country": country_name,
        "usd_goal_real": usd_goal_real,
        "usd_pledged_real": usd_pledged_real,
        "deadline": (datetime.fromtimestamp(deadline_unix, tz=timezone.utc).strftime('%d-%m-%Y')
                     if isinstance(deadline_unix, (int, float)) else None),
        "launched": (datetime.fromtimestamp(launched_unix, tz=timezone.utc).strftime('%d-%m-%Y')
                     if isinstance(launched_unix, (int, float)) else None),
    }

# ---------- public function ----------
def scrape_kickstarter_metadata(url):
    """
    Selenium (DOM) → stats.json → __NEXT_DATA__.
    On rétablit l’extraction DOM du GOAL (comme ta version Chrome),
    puis on comble via API / JSON si besoin.
    """
    base = _base_url(url)

    # 1) Try Selenium
    try:
        from selenium.webdriver.support.ui import WebDriverWait
        driver = _make_driver()
        wait = WebDriverWait(driver, 20)
        try:
            driver.get(base)
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

            # header text (for category/country/goal/pledged)
            header_text = driver.execute_script("""
              const head = document.querySelector("[data-test-id='hero__stats']") ||
                            document.querySelector("[data-test-id='hero__content']") ||
                            document.querySelector("main") || document.body;
              return (head.innerText || "").trim();
            """) or ""
            header_text = header_text.replace("\u00A0"," ").replace("\u202f"," ")
            header_text = re.sub(r"\s+"," ", header_text)

            # title
            title = driver.execute_script("""
              const m = document.querySelector("meta[property='og:title']");
              return m ? m.getAttribute("content") : null;
            """) or driver.title.replace(" — Kickstarter", "").strip()

            # category via breadcrumb
            cat_text = driver.execute_script("""
              const el = document.querySelector("nav[aria-label='breadcrumb'] a[href*='/categories/']");
              return el ? (el.textContent || "").trim() : null;
            """)
            main_category = None
            if cat_text:
                for c in CATS:
                    if cat_text.strip().lower() == c.lower():
                        main_category = c; break
            if not main_category:
                hits = []
                for c in CATS:
                    m = re.search(rf"\b{re.escape(c)}\b", header_text, flags=re.I)
                    if m: hits.append((m.start(), c))
                main_category = min(hits)[1] if hits else None

            # country (City, Country → keep Country)
            lines = [l.strip() for l in (driver.execute_script("""
              const head = document.querySelector("[data-test-id='hero__stats']") ||
                          document.querySelector("[data-test-id='hero__content']") ||
                          document.querySelector("main") || document.body;
              return (head.innerText || "").trim();
            """) or "").split("\n") if l.strip()]
            country_name = next((l.split(",")[-1].strip() for l in lines if "," in l), None)

            # --- GOAL (DOM, comme ta version Chrome) ---
            usd_goal_real = None
            m_goal = re.search(r"of\s*([$€¥£])\s*([\d\s.,]+)\s*goal", header_text, flags=re.I)
            if not m_goal:
                m_goal = re.search(r"\bGoal\b[^$€¥£]*([$€¥£])\s*([\d\s.,]+)", header_text, flags=re.I)
            if m_goal:
                usd_goal_real = _parse_amount(m_goal.group(2))

            if usd_goal_real is None:
                # Full page fallback patterns ($ … goal)
                full_text_goal = driver.execute_script("return document.body ? document.body.innerText : ''") or ""
                full_text_goal = full_text_goal.replace("\u00A0"," ").replace("\u202f"," ")
                full_text_goal = re.sub(r"\s+"," ", full_text_goal)
                m_goal2 = (
                    re.search(r"\$\s*([\d\s.,]+)\s*goal\b", full_text_goal, flags=re.I) or
                    re.search(r"\bgoal\b[^$€¥£]*\$\s*([\d\s.,]+)", full_text_goal, flags=re.I) or
                    re.search(r"\bobjectif\b[^$€¥£]*\$\s*([\d\s.,]+)", full_text_goal, flags=re.I)
                )
                if m_goal2:
                    usd_goal_real = _parse_amount(m_goal2.group(1))

            # pledged (DOM best-effort)
            usd_pledged_real = None
            m_pl = re.search(r"\$[\s]*([\d\s.,]+)\s*pledged\b", header_text, flags=re.I)
            if not m_pl:
                m_pl = re.search(r"([\d\s.,]+)\s*\$\s*engag", header_text, flags=re.I)  # FR
            if m_pl:
                usd_pledged_real = _parse_amount(m_pl.group(1))

            # deadline
            deadline_text = driver.execute_script("""
              const el = document.querySelector("[data-test-id='deadline-exists']");
              return el ? (el.textContent||"").trim() : null;
            """)
            _, deadline_unix = _parse_deadline(deadline_text or header_text)

            # augment with /stats.json (+ __NEXT_DATA__ if needed)
            s = _make_session(base)
            launch_unix = None
            next_json = None
            # Grab __NEXT_DATA__ from page (for last-resort goal)
            page_html = driver.page_source or ""
            mnext = re.search(r'(?is)<script\s+id=["\']__NEXT_DATA__["\']\s+type=["\']application/json["\']\s*>(.*?)</script>', page_html)
            if mnext:
                try: next_json = json.loads(mnext.group(1))
                except Exception: next_json = None

        finally:
            try: driver.quit()
            except: pass

        # call stats.json
        try:
            sj = s.get(base + "/stats.json", timeout=15, headers={
                **s.headers,
                "Accept": "application/json, text/plain, */*",
                "X-Requested-With": "XMLHttpRequest",
            }).json()
            proj = (sj.get("data", {}).get("project")
                    or sj.get("project")
                    or (sj if isinstance(sj, dict) else {}))

            # pledged (API) if DOM failed
            if usd_pledged_real is None:
                val_usd_direct = proj.get("usd_pledged") or proj.get("usd_pledged_real") or proj.get("converted_pledged_amount")
                if val_usd_direct is not None:
                    try: usd_pledged_real = round(float(val_usd_direct), 2)
                    except Exception: usd_pledged_real = _parse_amount(str(val_usd_direct))
                if usd_pledged_real is None:
                    pledged_val = proj.get("pledged")
                    fx_rate = proj.get("fx_rate") or proj.get("static_usd_rate") or proj.get("usd_rate")
                    try:
                        if pledged_val is not None and fx_rate:
                            usd_pledged_real = round(float(pledged_val) * float(fx_rate), 2)
                        elif pledged_val is not None:
                            usd_pledged_real = round(float(pledged_val), 2)
                    except Exception:
                        pass

            # --- goal (API / NEXT fallbacks) if DOM failed ---
            if usd_goal_real is None:
                usd_goal_real = _extract_usd_goal_usd(proj, next_json)

            # launch
            state = proj.get("state")
            launched_ts = proj.get("launched_at") or (proj.get("state_changed_at") if state == "live" else None)
            if launched_ts:
                try: launch_unix = int(float(launched_ts))
                except Exception: launch_unix = None
        except Exception:
            launch_unix = None

        return {
            "title": title,
            "main_category": main_category,
            "country": country_name,
            "usd_goal_real": usd_goal_real,
            "usd_pledged_real": usd_pledged_real,
            "deadline": (datetime.fromtimestamp(deadline_unix, tz=timezone.utc).strftime('%d-%m-%Y')
                         if isinstance(deadline_unix, (int, float)) else None),
            "launched": (datetime.fromtimestamp(launch_unix, tz=timezone.utc).strftime('%d-%m-%Y')
                         if isinstance(launch_unix, (int, float)) else None),
        }

    except Exception:
        # 2) Fallback sans Selenium
        return _requests_fallback(base)
