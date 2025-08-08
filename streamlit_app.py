import streamlit as st
from scripts.predict import predict_project_success


st.title("Kickstarter Project Success Predictor")

st.markdown("Remplis les informations de ton projet Kickstarter pour obtenir une prédiction.")

# --- Formulaire utilisateur ---
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

# --- Construction du dictionnaire ---
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

# --- Lancement de la prédiction ---
if st.button("Prédire le succès du projet"):
    prediction = predict_project_success(user_input)
    st.success(f"Le projet est prédit comme : **{prediction}**")
