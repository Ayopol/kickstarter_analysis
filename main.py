import numpy as np
import pandas as pd
import joblib
from scripts.preprocessing import df_clean_create
from scripts.predict import predict_project_success
from scripts.model import model_training_saving



def main():

    df = pd.read_csv('raw_data/ks-projects-201801.csv')
    df_clean = df_clean_create(df)
    model_training_saving(df_clean)

    user_input = {}
    my_dict = predict_project_success(user_input: dict):

    result = predict_project_success(my_dict)
    print(f"{result['prediction']} (Confiance : {result['probability']}%)")


    # A voir

# if __name__ == '__main__':
#     if len(sys.argv) != 3:
#         print("Usage: python predict.py kickstarter_model.pkl new_data.csv")
#     else:
#         main(sys.argv[1], sys.argv[2])
