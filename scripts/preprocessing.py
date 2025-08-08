###---------------Imports---------------###

# Basics
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd


import joblib
from pathlib import Path

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
from sklearn.naive_bayes import MultinomialNB
from collections import Counter


###---------------Functions---------------###

def df_create_state_comments(url1,url2):

    # Importing clean the two datasets

    print("Étape 1 : Lecture des fichiers CSV...")

    df_comments = pd.read_csv(url1)
    df_comments = df_comments[df_comments['comments'].apply(lambda x: len(x) > 2)]  #dropping the empty [] comments

    df_projects = pd.read_csv(url2)
    df_projects = df_projects.dropna(subset=['name'])

    print("Étape 2 : Merging des datasets...")

    # Merging
    df_merged = pd.merge(df_projects[['ID','state']], df_comments, left_on='ID', right_on='id', how='inner')
    df_merged = df_merged.drop(columns=['id'])
    df_merged = df_merged[df_merged['state'].isin(['successful', 'failed'])]

    print("Distribution des classes:")
    print(df_merged['state'].value_counts())
    print(df_merged['state'].value_counts(normalize=True))

    print("Étape finale : Dataset ready avec ", len(df_merged), "lignes.")

    return df_merged

def df_clean_create(df):
    '''
    Create the adequate df with all the necessary features for a futur model training
    '''

    # Keeping only the variables of interest

    filter = ['ID', 'name', 'main_category', 'currency', 'deadline', 'launched', 'state', 'country',
          'usd_pledged_real', 'usd_goal_real']

    df_filtered = df[filter]

    # Converting the dates into datatime

    df_filtered['deadline'] = pd.to_datetime(df_filtered['deadline'])
    df_filtered['launched'] = pd.to_datetime(df_filtered['launched'])
    df_filtered = df_filtered.dropna()

    # Creating the delta time feature
    df_filtered['delta_time'] = df_filtered['deadline'] - df_filtered['launched']
    df_filtered['delta_time'] = df_filtered['delta_time'].dt.days

    # Creating the practicability feature
    df_filtered['practicability'] = df_filtered['usd_goal_real'] / df_filtered['delta_time']


    # Creating the mean goal dicts
    mean_goal_by_cat = df_filtered.groupby('main_category')['usd_goal_real'].mean().to_dict()
    mean_goal_by_country = df_filtered.groupby('country')['usd_goal_real'].mean().to_dict()


    # Sauvegarde les means

        # Créer le dossier s'il n'existe pas
    save_dir = Path('save_pkl/mean_pkl')
    save_dir.mkdir(parents=True, exist_ok=True)

        # Sauvegarder chaque dictionnaire dans un fichier différent
    joblib.dump(mean_goal_by_cat, save_dir / 'mean_goal_by_cat.pkl')
    joblib.dump(mean_goal_by_country, save_dir / 'mean_goal_by_country.pkl')


    # Creating the columns ratio from the mean dicts
    df_filtered['ratio_goal_by_main_category'] = df_filtered.apply(
        lambda row: row['usd_goal_real'] / mean_goal_by_cat.get(row['main_category'], 1), axis=1)
    df_filtered['ratio_goal_by_country'] = df_filtered.apply(
        lambda row: row['usd_goal_real'] / mean_goal_by_country.get(row['country'], 1), axis=1)

    # Longueur du titre : nombre de mots
    df_filtered['title_word_count'] = df_filtered['name'].str.split().str.len()

    # Keeping the only two valid state
    df_final = df_filtered[df_filtered['state'].isin(['failed', 'successful'])]

    return df_final




###---------------Preprocessing for the commenst---------------###

# Fonction finale
def preprocess(df):
    '''
    Fonction finale regroupant les differentes fonctions de preprocessing
    '''

    print('Application du cleaning...')
    df['comments_clean'] = df['comments'].apply(preprocess_cleaning)

    print('Application du nltk')
    df['comments_processed'] = df['comments_clean'].apply(preprocess_nltk)

    label_encoder = LabelEncoder()
    df['state_encoded'] = label_encoder.fit_transform(df['state'])
    print(f"Classes encodées: {label_encoder.classes_}")

    return df[['comments_processed', 'state_encoded']]


def preprocess_cleaning(sentence):
    '''
        Cleaning the text and doing the Basics
    '''
    if pd.isna(sentence):
        return ""

    # Convertir en minuscules
    sentence = sentence.lower()

    # IMPORTANT pour sentiment: garder ! et ? qui indiquent l'intensité émotionnelle
    # Garder aussi les - pour des mots comme "well-executed"
    sentence = re.sub(r'[^\w\s!?-]', ' ', sentence)

    # Garder les chiffres sous forme de token car "10/10" ou "5 stars" sont importants
    # sentence = re.sub(r'\b\d+\b', ' NUMBER ', sentence)

    # Nettoyer les espaces multiples mais garder ! et ?
    sentence = re.sub(r'\s+', ' ', sentence).strip()

    return sentence


def preprocess_nltk(text):
    '''
        Lemmatisation (optionnel, souvent TF-IDF suffit)
    '''

    lemmatizer = WordNetLemmatizer()

    if not text:
        return ""
    tokens = word_tokenize(text)
    lemmas = [lemmatizer.lemmatize(token) for token in tokens if len(token) > 1]
    return ' '.join(lemmas)
