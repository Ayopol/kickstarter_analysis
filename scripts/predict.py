import sys
import joblib
import pandas as pd

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
 