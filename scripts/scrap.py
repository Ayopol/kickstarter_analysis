import re, json, requests
from urllib.parse import urlsplit, urlunsplit
from datetime import datetime, timedelta, timezone

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

DEFAULT_CONVERSION_TO_USD = {
    "USD": 1.0,
    "GBP": 1.28,   # 1 GBP = 1.28 USD
    "EUR": 1.09,   # 1 EUR = 1.09 USD
    "CAD": 0.74,   # 1 CAD = 0.74 USD
    "AUD": 0.67,   # 1 AUD = 0.67 USD
    "SEK": 0.094,  # 1 SEK = 0.094 USD
    "MXN": 0.058,  # 1 MXN = 0.058 USD
    "NZD": 0.61,   # 1 NZD = 0.61 USD
    "DKK": 0.15,   # 1 DKK = 0.15 USD
    "CHF": 1.14,   # 1 CHF = 1.14 USD
    "NOK": 0.094,  # 1 NOK = 0.094 USD
    "HKD": 0.13,   # 1 HKD = 0.13 USD
    "SGD": 0.74,   # 1 SGD = 0.74 USD
    "JPY": 0.0069, # 1 JPY = 0.0069 USD
}



#Transforme la string extraite en montant d'argent
def _parse_amount(s):
    if not s: return None
    s = (s.replace("\u202f"," ").replace("\xa0"," ").replace("’","").replace("'","")
           .replace(" ", "").replace(",", ""))
    try: return float(re.sub(r"[^0-9.]", "", s))
    except: return None


#Convertit la string date en ISO et Unix
def _parse_deadline(text):
    if not text: return None, None
    # ex: "Sun, Aug 31 2025 2:32 PM CEST" ou "Sun, August 31 2025 2:32 PM CEST"
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


#Nettoie une url kickstarter pour obtenir : protocole - domaine - chemin
def _base_url(url: str) -> str:
    # urlsplit découpe l'url en morceaux ((scheme='https', netloc='www.kickstarter.com', path='/projects/696521197/cerafilter',
    # query='ref=section-homepage', fragment=''))
    parts = list(urlsplit(url))
    parts[3] = ""  # drop query (on supprime les parametres (?ref=...))
    parts[2] = parts[2].rstrip("/")
    return urlunsplit(parts)



####       ___MAIN___        ####

'''Recupère en scraping toutes les infos nécessaire au modèle à partir d'une url'''

def scrape_kickstarter_metadata(url):
    # CONFIGURE ET LANCE CHROME EN MODE HEADLESS
    # # On force l’anglais pour être raccord avec notre Df d'entrainement
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
        # Ouvre la page et attend son chargement complet
        driver.get(url)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

        # Récupère header text = source pour parser cat/location/goal
        header_text = driver.execute_script("""
          const head = document.querySelector("[data-test-id='hero__stats']") ||
                        document.querySelector("[data-test-id='hero__content']") ||
                        document.querySelector("main") || document.body;
          return (head.innerText || "").trim();
        """) or ""
        # Normalise les espaces pour des Regex opti
        header_text = header_text.replace("\u00A0"," ").replace("\u202f"," ")
        header_text = re.sub(r"\s+"," ", header_text)

        #Récupérer TITLE
        title = driver.execute_script("""
        const m = document.querySelector("meta[property='og:title']");
        return m ? m.getAttribute("content") : null;
        """)
        if not title:
            # fallback: titre de l’onglet (souvent "Nom du projet — Kickstarter")
            title = driver.title.replace(" — Kickstarter", "").strip()

        # Récupérer MAIN_CATEGORY (exacte parmi CATS)
        # breadcrumb = chemin de navigation rapide vers un élément d'une page : On tente de récupérer la categorie via lui
        cat_text = driver.execute_script("""
          const el = document.querySelector("nav[aria-label='breadcrumb'] a[href*='/categories/']");
          return el ? (el.textContent || "").trim() : null;
        """)
        main_category = None
        if cat_text:
            for c in CATS:
                if cat_text.strip().lower() == c.lower():
                    main_category = c; break

        # Si la recherche via le breadcrumb n'a pas marché on cherche la premiere occurence d'un des CATS
        if not main_category:
            hits = []
            for c in CATS:
                m = re.search(rf"\b{re.escape(c)}\b", header_text, flags=re.I)
                if m: hits.append((m.start(), c))
            main_category = min(hits)[1] if hits else None


        # Récupérer LOCATION COUNTRY depuis l'en-tête
        lines = [l.strip() for l in (driver.execute_script("""
          const head = document.querySelector("[data-test-id='hero__stats']") ||
                      document.querySelector("[data-test-id='hero__content']") ||
                      document.querySelector("main") || document.body;
          return (head.innerText || "").trim();
        """) or "").split("\n") if l.strip()]
        location_text = next((l.split(",")[-1].strip() for l in lines if "," in l),None)

        # Récupérer GOAL : format "of $ 2,031 goal", ou sinon "Goal $ 2,031"
        m_goal = re.search(r"of\s*([$€¥£])\s*([\d\s.,]+)\s*goal", header_text, flags=re.I)
        if not m_goal:
            m_goal = re.search(r"\bGoal\b[^$€¥£]*([$€¥£])\s*([\d\s.,]+)", header_text, flags=re.I)
        currency_symbol = m_goal.group(1) if m_goal else None
        goal_amount = _parse_amount(m_goal.group(2)) if m_goal else None
        currency_guess = {"$":"USD","€":"EUR","¥":"JPY","£":"GBP"}.get(currency_symbol)

        # Récupérer PLEDGED (montant engagé) et convertir en USD
        m_pledged = re.search(r"\b([$€¥£])\s*([\d\s.,]+)\s*pledged\b", header_text, flags=re.I)
        if not m_pledged:
            m_pledged = re.search(r"\b([\d\s.,]+)\s*([$€¥£])\s*pledged\b", header_text, flags=re.I)
        if not m_pledged:
            # fallback FR : "... engagés ..."
            m_pledged = (re.search(r"\b([$€¥£])\s*([\d\s.,]+)\s*engag", header_text, flags=re.I)
                         or re.search(r"\b([\d\s.,]+)\s*([$€¥£])\s*engag", header_text, flags=re.I))

        pledged_currency_symbol = None
        pledged_amount = None
        if m_pledged:
            g1, g2 = m_pledged.group(1), m_pledged.group(2)
            if g1 in "$€¥£":
                pledged_currency_symbol = g1
                pledged_amount = _parse_amount(g2)
            else:
                pledged_currency_symbol = g2 if g2 in "$€¥£" else None
                pledged_amount = _parse_amount(g1)

        pledged_currency_guess = {"$":"USD","€":"EUR","¥":"JPY","£":"GBP"}.get(pledged_currency_symbol)
        usd_pledged_real = None
        if pledged_amount is not None:
            rate = DEFAULT_CONVERSION_TO_USD.get(pledged_currency_guess or "USD", 1.0)
            usd_pledged_real = round(pledged_amount * rate, 2)


        # Récupérer DEADLINE (Iso et Unix)
        # On scrap la phrase complete qui parle de la deadline et on récupère juste les valeurs avec parse_deadline()
        deadline_text = driver.execute_script("""
          const el = document.querySelector("[data-test-id='deadline-exists']");
          return el ? (el.textContent||"").trim() : null;
        """)
        deadline_iso, deadline_unix = _parse_deadline(deadline_text or header_text)

    finally:
        try: driver.quit()
        except: pass


    # Récupérer LAUNCH_DATE
    # Plus technique car pas sur l'URL de base du projet
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
        state = proj.get("state")
        # si dispo, launched_at direct ; sinon, si live, state_changed_at ≈ passage en live
        launched_ts = proj.get("launched_at") or (proj.get("state_changed_at") if state == "live" else None)
        if launched_ts:
            launch_unix_utc = int(launched_ts)
            launch_iso_utc = datetime.fromtimestamp(launch_unix_utc, tz=timezone.utc).isoformat()
    except Exception:
        pass

    dico_du_cul = {
        "title" : title,
        "main_category": main_category,               # ex: 'Crafts'
        "country": location_text,               # ex: 'Saga, Japan'
        "usd_goal_real": goal_amount,                   # ex: 2031.0
        "usd_pledged_real": usd_pledged_real,
        "deadline": datetime.utcfromtimestamp(deadline_unix).strftime('%d-%m-%Y'),
        "launched": datetime.utcfromtimestamp(launch_unix_utc).strftime('%d-%m-%Y')
    }

    return dico_du_cul

# --------- exemple ----------
data = scrape_kickstarter_metadata("https://www.kickstarter.com/projects/696521197/cerafilter-revolutionizing-coffee-with-arita-ceramic-tech")
print(json.dumps(data, indent=2))
