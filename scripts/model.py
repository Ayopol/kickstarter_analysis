###---------------Imports---------------###

# Basics
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Machine Learning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
import string
import re
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.model_selection import learning_curve

from sklearn.naive_bayes import MultinomialNB
from collections import Counter

from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier
from sklearn.pipeline import Pipeline
from sklearn.model_selection import RandomizedSearchCV
import joblib


###---------------Functions---------------###


def model_creation(df) :

    X = df['comments_processed']
    y = df['state_encoded']


    # Train/Test Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )

    # 8. Vectorisation TF-IDF pour sentiment analysis

    vectorizer = TfidfVectorizer(
        max_features=5000,          # Plus de features
        ngram_range=(1, 3),         # Unigrammes + bigrammes + trigrammes (pour "not very good")
        min_df=2,                   # Minimum 2 documents (évite les mots trop rares)
        max_df=0.95,               # Maximum 95% des documents (évite les mots trop communs)
        lowercase=True,
        stop_words=None,           # GARDER les stop words pour le sentiment ! A definir
        token_pattern=r'\b[a-zA-Z][a-zA-Z]+\b'  # Mots de 2+ lettres seulement A definir
    )

    X_train_transformed = vectorizer.fit_transform(X_train)
    X_test_transformed = vectorizer.transform(X_test)


    # 9. TESTS DE BASELINE AVANT LE MODÈLE PRINCIPAL

    # Test 1: Naive Bayes (souvent bon pour le texte)
    nb = MultinomialNB()
    nb.fit(X_train_transformed, y_train)
    nb_pred = nb.predict(X_test_transformed)
    print("\n=== NAIVE BAYES ===")
    print(classification_report(y_test, nb_pred))

    # Test 2: Logistic Regression
    model = LogisticRegression(
        random_state=42,
        max_iter=1000,
        C=1,
        class_weight=None,          # Pas besoin avec 42/58
        solver='liblinear'          # Bon pour les petits datasets
    )

    # Entraînement du modèle simple
    model.fit(X_train_transformed, y_train)

    # Prédictions
    y_pred = model.predict(X_test_transformed)

    # Évaluation détaillée
    print("\n=== RÉSULTATS ===")
    print("\nRapport de classification:")
    print(classification_report(y_test, y_pred))

    return model, vectorizer



    filter = ['ID', 'name', 'main_category', 'currency', 'deadline', 'launched', 'state', 'country',
          'usd_pledged_real', 'usd_goal_real']

    df_filtered = df[filter]
    df_filtered['deadline'] = pd.to_datetime(df_filtered['deadline'])
    df_filtered['launched'] = pd.to_datetime(df_filtered['launched'])
    df_filtered = df_filtered.dropna()

    # Creating the delta time feature
    df_filtered['delta_time'] = df_filtered['deadline'] - df_filtered['launched']
    df_filtered['delta_time'] = df_filtered['delta_time'].dt.days

    # Creating the practicability feature

    df_filtered['practicability'] = df_filtered['usd_goal_real'] / df_filtered['delta_time']


    # Ratio de usd_goal_real par rapport à la moyenne des objectifs de la même main_category
    df_filtered['ratio_goal_by_main_category'] = (df_filtered['usd_goal_real']
        / df_filtered.groupby('main_category')['usd_goal_real'].transform('mean'))

    # Ratio de usd_goal_real par rapport à la moyenne des objectifs par country
    df_filtered['ratio_goal_by_country'] = ( df_filtered['usd_goal_real']
                                            / df_filtered.groupby('country')['usd_goal_real'].transform('mean'))

    # Longueur du titre : nombre de mots
    df_filtered['title_word_count'] = df_filtered['name'].str.split().str.len()

    # Keeping the only two valid state
    df_final = df_filtered[df_filtered['state'].isin(['failed', 'successful'])]

    return df_final

def model_training_saving(df) :


    y = df['state'].map({'successful':1, 'failed':0})
    X = df.drop(columns=["state"])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)


    # Building the pipeline
    numeric_features = ['usd_goal_real', 'ratio_goal_by_main_category', 'ratio_goal_by_country', 'title_word_count', 'delta_time']
    categorical_features = ['main_category', 'country']


    num_transformer = Pipeline(
        steps = [
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ])

    cat_transformer = Pipeline(
        steps = [
            ('imputer', SimpleImputer(strategy='most_frequent')),
            ('onehot', OneHotEncoder(handle_unknown='ignore'))
        ])

    preprocessor = ColumnTransformer(
        transformers = [
            ('num', num_transformer, numeric_features),
            ('cat', cat_transformer, categorical_features)
        ], remainder='drop')

    xgb_pipeline = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('clf', XGBClassifier(
        use_label_encoder=False,    # désactive l'ancien label encoder
        eval_metric='logloss',      # métrique par défaut pour classif binaire
        random_state=42
    ))])

    param_dist = {
    'clf__n_estimators':    [100, 200, 300],
    'clf__max_depth':       [3, 6, 9],
    'clf__learning_rate':   [0.01, 0.1, 0.2],
    'clf__subsample':       [0.7, 1.0],
    'clf__colsample_bytree':[0.7, 1.0]}

    search_acc = RandomizedSearchCV(
    xgb_pipeline, param_dist,
    n_iter=10, cv=5, scoring='accuracy', n_jobs=-1, random_state=42)

    # not sure of the following actions
    search_acc.fit(X_train, y_train)
    print("Meilleurs paramètres :", search_acc.best_params_)

    best_model = search_acc.best_estimator_
    joblib.dump(best_model, 'kickstarter_model.pkl')
    print('Model saved !')

    #

    y_pred  = best_model.predict(X_test)

    print(classification_report(y_test, y_pred))

    return

###---------------Diagnostic---------------###


def important_words(model, vectorizer):
        # 12. Analyse des mots les plus importants dans le modèle
    feature_names = vectorizer.get_feature_names_out()
    coefficients = model.coef_[0]

    # Mots les plus indicatifs de succès
    success_words = [(feature_names[i], coefficients[i])
                    for i in coefficients.argsort()[-20:][::-1]]
    print("\nMots les plus indicatifs de SUCCÈS:")
    for word, coef in success_words:
        print(f"{word}: {coef:.3f}")

    # Mots les plus indicatifs d'échec
    failure_words = [(feature_names[i], coefficients[i])
                    for i in coefficients.argsort()[:20]]
    print("\nMots les plus indicatifs d'ÉCHEC:")
    for word, coef in failure_words:
        print(f"{word}: {coef:.3f}")

    return

def show_learning_curve(model, X_train_transformed, y_train, train_size_max, train_size_step):
    train_sizes = np.arange(100, train_size_max, train_size_step)

    # Get train scores (R2), train sizes, and validation scores using `learning_curve`
    train_sizes, train_scores, test_scores = learning_curve(
        estimator=model, X=X_train_transformed, y=y_train, train_sizes=train_sizes, cv=5, scoring='accuracy')

    # Take the mean of cross-validated train scores and validation scores
    train_scores_mean = np.mean(train_scores, axis=1)
    test_scores_mean = np.mean(test_scores, axis=1)

    plt.plot(train_sizes, train_scores_mean, label='Training score')
    plt.plot(train_sizes, test_scores_mean, label='Test score')
