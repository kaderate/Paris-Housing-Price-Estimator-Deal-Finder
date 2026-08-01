import logging

import numpy as np
import pandas as pd
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import cross_val_predict

import config

logger = logging.getLogger(__name__)


def nettoyage_donnees(file=config.RAW_CSV):
    df = pd.read_csv(file)
    df = df.dropna(subset=["Prix", "Surface", "Arrondissement", "Pieces", "DPE"])
    df['Arrondissement'] = df['Arrondissement'].astype(int)
    df['Pieces'] = df['Pieces'].astype(int)
    df['DPE'] = df['DPE'].astype(int)
    df['Prix m2'] = df['Prix']/df['Surface']
    df = df[df["Prix"] <= config.PRIX_MAX]
    df = df[(df["Prix m2"] >= config.PRIX_M2_MIN) & (df["Prix m2"] <= config.PRIX_M2_MAX)]
    df["Surface par pieces"] = df["Surface"]/df["Pieces"]
    return df

def model_entrainement(df):
    encoder = OneHotEncoder(handle_unknown="ignore")
    y = np.log1p(df["Prix"])
    x = df[["Surface", "Arrondissement", "Pieces", "DPE", "Surface par pieces"]]

    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2, random_state=0)

    preprocessor = ColumnTransformer(
        transformers=[('cat', encoder, ["Arrondissement"])],
        remainder='passthrough')

    model = Pipeline(steps=[('preprocessor', preprocessor),
                            ('regressor', RandomForestRegressor(n_estimators=100, max_depth=12, random_state=0))
                     ])

    model.fit(x_train, y_train)

    return model, x, y

def filtrer_criteres(df, surface_min=None, surface_max=None, budget_min=None, budget_max=None):
    """Restreint `df` aux annonces respectant les critères de recherche fournis (bornes incluses)."""
    if surface_min is not None:
        df = df[df["Surface"] >= surface_min]
    if surface_max is not None:
        df = df[df["Surface"] <= surface_max]
    if budget_min is not None:
        df = df[df["Prix"] >= budget_min]
    if budget_max is not None:
        df = df[df["Prix"] <= budget_max]
    return df


def bon_plan(model, x, y, df, surface_min=None, surface_max=None, budget_min=None, budget_max=None):
    df = df.copy()
    y_pred_log = cross_val_predict(model, x, y, cv=5)
    df['Estimation'] = np.expm1(y_pred_log)
    mae = mean_absolute_error(df['Prix'], df['Estimation'])
    r2 = r2_score(df['Prix'], df['Estimation'])
    logger.info("MAE : %.2f €", mae)
    logger.info("R² : %.3f", r2)
    df["Decote"] = ((df["Prix"] - df["Estimation"]) / df["Estimation"])*100
    df = df[df["Decote"] <= config.DECOTE_SEUIL]
    df = filtrer_criteres(df, surface_min, surface_max, budget_min, budget_max)
    df = df.sort_values(by=["Decote"], ascending=True)
    df.to_csv(config.DEALS_CSV, index=False)

    return config.DEALS_CSV, df

if "__main__" == __name__:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    df = nettoyage_donnees()
    model, x, y = model_entrainement(df)
    chemin_csv, df_deals = bon_plan(model, x, y, df)
    print(chemin_csv)
