import streamlit as st
from scripts.predict import predict_project_success

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
    launched = st.date_input("Date de lancement du projet")
    deadline = st.date_input("Date de fin du projet")
    country = st.selectbox("Pays", ["US", "GB", "CA", "DE", "FR", "AU", "NL", "SE", "IT", "ES"])
    usd_pledged_real = st.number_input("Montant déjà récolté (USD)", min_value=0.0)
    usd_goal_real = st.number_input("Objectif total (USD)", min_value=1.0)

    if st.button("Prédire depuis formulaire", key="predict_from_form"):
        user_input = {
            "name": name,
            "main_category": main_category,
            "currency": currency,
            "launched": launched.strftime("%d/%m/%Y"),
            "deadline": deadline.strftime("%d/%m/%Y"),
            "country": country,
            "usd_pledged_real": usd_pledged_real,
            "usd_goal_real": usd_goal_real
        }
        prediction = predict_project_success(user_input)
        st.success(f"Résultat : **{prediction}**")



# --- Onglet 2 : URL d'un projet existant ---

with tab2:
    st.subheader("Analyser un projet déjà en ligne")
    st.markdown(
        """
        **Télécharge** notre repository GitHub et **exécute** en local le fichier [`streamlit_app_old`](https://github.com/Ayopol/kickstarter_analysis)
        depuis notre repository GitHub. ;)
        """,
        unsafe_allow_html=True
    )
