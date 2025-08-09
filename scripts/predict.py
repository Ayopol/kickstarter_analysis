import sys
import joblib
import pandas as pd


def predict():
    mean_goal_by_cat = joblib.load('save_pkl/mean_goal_by_cat.pkl')
    mean_goal_by_country = joblib.load('save_pkl/mean_goal_by_country.pkl')

    def apply_main_category_ratio(df: pd.DataFrame, goal_column: str = 'usd_goal_real', category_column: str = 'main_category', mapping_path: str = 'artifacts/mean_goal_by_main_category.pkl') -> pd.DataFrame:
    """
    Charge le mapping sauvegardé et ajoute la colonne de ratio à un nouveau DataFrame.
    """
    mean_by_cat = joblib.load(mapping_path)

    df[f'ratio_goal_by_{category_column}'] = df.apply(
        lambda row: row[goal_column] / mean_by_cat.get(row[category_column], 1),
        axis=1
    )

    return df

import joblib
import pandas as pd

def predict_project_success(user_input: dict):
    """
    Prend en entrée un dictionnaire avec les infos du projet Kickstarter et renvoie la prédiction.
    """

    # === 1. Charger les objets nécessaires ===
    model = joblib.load("save_pkl/model_pkl/kickstarter_model.pkl")
    vectorizer = joblib.load("models/tfidf_vectorizer.pkl")
    mean_goal_by_cat = joblib.load("save_pkl/mean_pkl/mean_goal_by_cat.pkl")
    mean_goal_by_country = joblib.load("save_pkl/mean_pkl/mean_goal_by_country.pkl")

    # === 2. Construire le DataFrame utilisateur ===
    df = pd.DataFrame([user_input])

    # === 3. Recréer les features ===
    df['ratio_goal_by_main_category'] = df.apply(
        lambda row: row['usd_goal_real'] / mean_goal_by_cat.get(row['main_category'], 1),
        axis=1)
    df['ratio_goal_by_country'] = df.apply(
        lambda row: row['usd_goal_real'] / mean_goal_by_country.get(row['country'], 1),
        axis=1)


    # === 4. Transformer les colonnes texte ===
    # df['comments_cleaned'] = df['comments'].apply(preprocess_text)  # À définir si pas encore fait

    # X_text = vectorizer.transform(df['comments_cleaned'])


    # Tu dois les encoder comme dans ton entraînement (OneHotEncoder ou OrdinalEncoder)
    # Ici, on suppose que tu as tout préparé avant pour les features finales
    # Exemple :
    # X_final = hstack([X_text, encoded_features])

    # Si ton modèle ne prend que le texte :
    X_final = X_text

    # === 6. Prédiction ===
    prediction = model.predict(X_final)[0]
    proba = model.predict_proba(X_final)[0]

    return {
        "prediction": prediction,
        "probability": proba
    }




def main(model_path, data_path):
    # 1. Charger le modèle
    model = joblib.load(model_path)

    # 2. Charger de nouvelles données (mêmes colonnes qu’à l’entraînement)
    df = pd.read_csv(data_path)

    # 3. Faire la prédiction
    preds = model.predict(df)
    proba = model.predict_proba(df)[:,1]

    # 4. Afficher ou enregistrer
    df['pred_success'] = preds
    df['proba_success'] = proba
    print(df[['pred_success','proba_success']])
    # ou df.to_csv('predictions.csv', index=False)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python predict.py kickstarter_model.pkl new_data.csv")
    else:
        main(sys.argv[1], sys.argv[2])
