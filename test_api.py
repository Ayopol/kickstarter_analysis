#Basics
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from datetime import datetime


from fastapi import FastAPI
import uvicorn
import joblib
from pydantic import BaseModel

app = FastAPI()

# Define a root `/` endpoint
@app.get('/') # enregistre la fonction juste en dessous (index) comme un endpoint HTTP de type GET, à la route / (la racine du site).

def index():
    return {'ok': True}


@app.get('/predict')
def predict():
    return {'wait': 64}


from pydantic import BaseModel

# 1. Charger le modèle pré-entraîné

model = joblib.load('model pkl/kickstarter_model.pkl')


# 2. Création de l'app FastAPI
app = FastAPI()

# 3. Modèle de données en entrée
class PredictInput(BaseModel):
    project_name: str
    country: str
    main_category: str

    usd_goal : float
    launch_date : datetime
    deadline : datetime


# 4. Définir la route de prédiction
@app.post("/predict")

def predict(input: PredictInput):
    # Convertir en tableau numpy
    features = np.array([[
        input.project_name,
        input.country,
        input.main_category,
        input.usd_goal,
        input.launch_date,
        input.deadline,
    ]])

    # Faire la prédiction
    prediction = model.predict(features)[0]

    return {
        "Prediction": int(prediction)
    }
