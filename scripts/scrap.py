import re, json, requests
from urllib.parse import urlsplit, urlunsplit
from datetime import datetime, timedelta, timezone
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

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

def scrape_kickstarter_metadata(url):
    # Chrome headless (langue forcée en EN, devise UI en $ via ton paramétrage sur le site)
    opts = Options()
    opts.add_experimental_option("prefs", {"intl.accept_languages": "en-US,en"})
    opts.add_argument("--lang=en-US")
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,768")
    opts.add_argument("--disable-dev-shm-usage"); opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=opts)
    wait = WebDriverWait(driver, 10)

    try:
        # Ouvre la page
        driver.get(url)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

        # Header text pour cat / location / goal / pledged
        header_text = driver.execute_script("""
          const head = document.querySelector("[data-test-id='hero__stats']") ||
                        document.querySelector("[data-test-id='hero__content']") ||
                        document.querySelector("main") || document.body;
          return (head.innerText || "").trim();
        """) or ""
        header_text = header_text.replace("\u00A0"," ").replace("\u202f"," ")
        header_text = re.sub(r"\s+"," ", header_text)

        # TITLE
        title = driver.execute_script("""
          const m = document.querySelector("meta[property='og:title']");
          return m ? m.getAttribute("content") : null;
        """)
        if not title:
            title = driver.title.replace(" — Kickstarter", "").strip()

        # MAIN_CATEGORY
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

        # COUNTRY (uniquement le pays)
        lines = [l.strip() for l in (driver.execute_script("""
          const head = document.querySelector("[data-test-id='hero__stats']") ||
                      document.querySelector("[data-test-id='hero__content']") ||
                      document.querySelector("main") || document.body;
          return (head.innerText || "").trim();
        """) or "").split("\n") if l.strip()]
        location_text = next((l.split(",")[-1].strip() for l in lines if "," in l), None)

        # GOAL (on suppose USD déjà affiché)
        m_goal = re.search(r"of\s*([$€¥£])\s*([\d\s.,]+)\s*goal", header_text, flags=re.I)
        if not m_goal:
            m_goal = re.search(r"\bGoal\b[^$€¥£]*([$€¥£])\s*([\d\s.,]+)", header_text, flags=re.I)
        currency_symbol = m_goal.group(1) if m_goal else None
        goal_amount = _parse_amount(m_goal.group(2)) if m_goal else None
        usd_goal_real = goal_amount

        # --- Fallback DOM (page entière) pour le goal ---
        if usd_goal_real is None:
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

        # PLEDGED d’abord via le header (UI en $)
        usd_pledged_real = None
        m_pledged = re.search(r"\$[\s]*([\d\s.,]+)\s*pledged\b", header_text, flags=re.I)
        if not m_pledged:
            # FR (au cas où)
            m_pledged = re.search(r"([\d\s.,]+)\s*\$\s*engag", header_text, flags=re.I)
        if m_pledged:
            usd_pledged_real = _parse_amount(m_pledged.group(1))

        # Si toujours pas trouvé, chercher dans TOUTE la page (parfois l’info est ailleurs)
        if usd_pledged_real is None:
            full_text = driver.execute_script("return document.body ? document.body.innerText : ''") or ""
            full_text = full_text.replace("\u00A0"," ").replace("\u202f"," ")
            full_text = re.sub(r"\s+"," ", full_text)
            m2 = re.search(r"\$[\s]*([\d\s.,]+)\s*pledged\b", full_text, flags=re.I)
            if not m2:
                m2 = re.search(r"([\d\s.,]+)\s*\$\s*engag", full_text, flags=re.I)
            if m2:
                usd_pledged_real = _parse_amount(m2.group(1))

        # DEADLINE
        deadline_text = driver.execute_script("""
          const el = document.querySelector("[data-test-id='deadline-exists']");
          return el ? (el.textContent||"").trim() : null;
        """)
        deadline_iso, deadline_unix = _parse_deadline(deadline_text or header_text)

    finally:
        try: driver.quit()
        except: pass

    # LAUNCH DATE + PLEDGED + GOAL fallback via /stats.json
    base = _base_url(url)
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": base,
    })
    launch_iso_utc = launch_unix_utc = None
    try:
        sj = s.get(base + "/stats.json", timeout=10).json()
        proj = (sj.get("data", {}).get("project")
                or sj.get("project")
                or (sj if isinstance(sj, dict) else {}))

        # PLEDGED en USD (API) si DOM n'a pas donné
        if usd_pledged_real is None:
            val_usd_direct = proj.get("usd_pledged") or proj.get("usd_pledged_real")
            if val_usd_direct is not None:
                try:
                    usd_pledged_real = round(float(val_usd_direct), 2)
                except Exception:
                    usd_pledged_real = _parse_amount(str(val_usd_direct))
        if usd_pledged_real is None:
            pledged_val = proj.get("pledged")
            fx_rate = proj.get("fx_rate") or proj.get("static_usd_rate") or proj.get("usd_rate")
            try:
                if pledged_val is not None and fx_rate:
                    usd_pledged_real = round(float(pledged_val) * float(fx_rate), 2)
            except Exception:
                pass

        # --- GOAL via API : champs USD direct, sinon conversion ---
        if usd_goal_real is None:
            val_goal_usd = proj.get("usd_goal") or proj.get("usd_goal_real")
            if val_goal_usd is not None:
                try:
                    usd_goal_real = round(float(val_goal_usd), 2)
                except Exception:
                    usd_goal_real = _parse_amount(str(val_goal_usd))
        if usd_goal_real is None:
            goal_local = proj.get("goal")
            usd_rate = proj.get("fx_rate") or proj.get("static_usd_rate") or proj.get("usd_rate")
            try:
                if goal_local is not None and usd_rate:
                    usd_goal_real = round(float(goal_local) * float(usd_rate), 2)
                elif goal_local is not None:
                    usd_goal_real = round(float(goal_local), 2)  # dernier recours (devise locale)
            except Exception:
                pass

        # Launch date
        state = proj.get("state")
        launched_ts = proj.get("launched_at") or (proj.get("state_changed_at") if state == "live" else None)
        if launched_ts:
            launch_unix_utc = int(launched_ts)
            launch_iso_utc = datetime.fromtimestamp(launch_unix_utc, tz=timezone.utc).isoformat()
    except Exception:
        pass

    dico_du_cul = {
        "title": title,
        "main_category": main_category,          # ex: 'Crafts'
        "country": location_text,                # ex: 'Japan'
        "usd_goal_real": usd_goal_real,          # ex: 2031.0
        "usd_pledged_real": usd_pledged_real,    # -> devrait refléter l’affichage en $
        "deadline": (
            datetime.utcfromtimestamp(deadline_unix).strftime('%d-%m-%Y')
             if deadline_unix is not None else None),
        "launched": (
            datetime.utcfromtimestamp(launch_unix_utc).strftime('%d-%m-%Y')
            if launch_unix_utc is not None else None),
    }

    return dico_du_cul

