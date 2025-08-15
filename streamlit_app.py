import streamlit as st
from scripts.predict import predict_project_success
# from scripts.scraping import scrape_project  # en attente de fonction py bruno

st.title("🚀 Kickstarter Project Success Predictor")
st.markdown("Choisis un mode d'entrée pour prédire la réussite d'un projet Kickstarter.")

# Création des deux onglets
tab1, tab2 = st.tabs(["📎 Projet existant (URL)", "✍️ Ton futur projet"])

# --- Onglet 1 : URL d'un projet existant ---
with tab1:
    st.subheader("Analyser un projet déjà en ligne")
    url = st.text_input("URL du projet Kickstarter")

    if st.button("Prédire depuis l'URL", key="predict_from_url"):
        if url.strip():
            try:
                data_dict = scrape_project(url)  # Doit retourner un dict formaté
                prediction = predict_project_success(data_dict)
                st.success(f"Résultat : **{prediction}**")
            except Exception as e:
                st.error(f"Erreur lors du scraping : {e}")
        else:
            st.warning("⚠️ Veuillez entrer une URL valide.")

# --- Onglet 2 : Formulaire manuel ---
with tab2:
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
