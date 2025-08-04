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


###---------------Preprocessing Text---------------###


def preprocess_cleaning(sentence):

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


# Lemmatisation (optionnel, souvent TF-IDF suffit)

def preprocess_nltk(text):
    lemmatizer = WordNetLemmatizer()

    if not text:
        return ""
    tokens = word_tokenize(text)
    lemmas = [lemmatizer.lemmatize(token) for token in tokens if len(token) > 1]
    return ' '.join(lemmas)


def preprocess(df):

    print('Application du cleaning...')
    df['comments_clean'] = df['comments'].apply(preprocess_cleaning)

    print('Application du nltk')
    df['comments_processed'] = df['comments_clean'].apply(preprocess_nltk)

    label_encoder = LabelEncoder()
    df['state_encoded'] = label_encoder.fit_transform(df['state'])
    print(f"Classes encodées: {label_encoder.classes_}")

    return df[['comments_processed', 'state_encoded']]
