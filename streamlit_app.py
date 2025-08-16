import streamlit as st
from scripts.predict import predict_project_success
from scripts.scrap import scrape_kickstarter_metadata

st.title("🚀 Kickstarter Project Success Predictor")
st.markdown("Choisis un mode d'entrée pour prédire la réussite d'un projet Kickstarter.")

# Création des deux onglets
tab1, tab2 = st.tabs(["✍️ Ton futur projet","📎 Projet existant (URL)"])


# --- Onglet 1 : Formulaire manuel ---
with tab1:
    st.subheader("Entrer les informations manuellement")

    name = st.text_input("Nom du projet", value="Le Projet")
    main_category = st.selectbox("Catégorie principale", [
        "Art", "Comics", "Crafts", "Dance", "Design", "Fashion",
        "Film & Video", "Food", "Games", "Journalism", "Music",
        "Photography", "Publishing", "Technology", "Theater"
    ])
    currency = st.selectbox("Devise utilisée", ["USD", "GBP", "CAD", "EUR", "AUD"])
    deadline = st.date_input("Date de fin du projet")
    launched = st.date_input("Date de lancement du projet")
    country = st.selectbox("Pays", ["US", "GB", "CA", "DE", "FR", "AU", "NL", "SE", "IT", "ES"])
    usd_pledged_real = st.number_input("Montant déjà récolté (USD)", min_value=0.0)
    usd_goal_real = st.number_input("Objectif total (USD)", min_value=1.0)

    if st.button("Prédire depuis formulaire", key="predict_from_form"):
        user_input = {
            "name": name,
            "main_category": main_category,
            "currency": currency,
            "deadline": deadline.strftime("%d/%m/%Y"),
            "launched": launched.strftime("%d/%m/%Y"),
            "country": country,
            "usd_pledged_real": usd_pledged_real,
            "usd_goal_real": usd_goal_real
        }
        prediction = predict_project_success(user_input)
        st.success(f"Résultat : **{prediction}**")



# --- Onglet 2 : URL d'un projet existant ---

with tab2:
    st.subheader("Analyser un projet déjà en ligne")
    url = st.text_input("URL du projet Kickstarter")

    def _to_model_date(s: str | None) -> str | None:
        if not s: return None
        s = s.strip()
        from datetime import datetime as _dt
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return _dt.strptime(s, fmt).strftime("%d/%m/%Y")
            except Exception:
                pass
        return s

    def _country_to_iso2(country: str | None) -> str | None:
        if not country: return None
        c = country.strip()
        if len(c) == 2 and c.isalpha():
            return c.upper()
        MAP = {
            "United States":"US","USA":"US","US":"US",
            "United Kingdom":"GB","UK":"GB","Great Britain":"GB",
            "Canada":"CA","Germany":"DE","France":"FR","Spain":"ES","Italy":"IT",
            "Netherlands":"NL","Sweden":"SE","Denmark":"DK","Norway":"NO",
            "Switzerland":"CH","Australia":"AU","New Zealand":"NZ",
            "Japan":"JP","Hong Kong":"HK","Singapore":"SG","Mexico":"MX",
        }
        return MAP.get(c, c[:2].upper())

    if st.button("Prédire depuis l'URL", key="predict_from_url"):
        if not url.strip():
            st.warning("⚠️ Veuillez entrer une URL valide.")
        else:
            # 1) Scrape (sans try/except pour voir la trace si ça casse)
            data_dict = scrape_kickstarter_metadata(url)

            st.caption("Données brutes scrapées")
            st.json(data_dict)

            # 2) Normalisation vers le schéma du modèle
            payload = {
                "name": data_dict.get("title") or "",
                "main_category": data_dict.get("main_category"),
                "deadline": _to_model_date(data_dict.get("deadline")),
                "launched": _to_model_date(data_dict.get("launched")),
                "country": _country_to_iso2(data_dict.get("country")),
                "usd_pledged_real": float(data_dict.get("usd_pledged_real") or 0.0),
                "usd_goal_real": float(data_dict.get("usd_goal_real") or 0.0),
            }

            # 3) Validation stricte avant modèle (évite les None qui explosent dedans)
            missing = []
            if not payload["main_category"]: missing.append("main_category")
            if not payload["deadline"]: missing.append("deadline")
            if not payload["launched"]: missing.append("launched")
            if not payload["country"]: missing.append("country")
            if payload["usd_goal_real"] <= 0: missing.append("usd_goal_real")

            if missing:
                st.error(f"Champs manquants/invalides pour le modèle : {', '.join(missing)}")
                st.stop()

            st.caption("Payload envoyé au modèle")
            st.json(payload)

            # 4) Prédiction (sans try/except pour afficher la vraie stack en cas d'erreur)
            pred = predict_project_success(payload)
            st.success(f"Résultat : **{pred}**")
