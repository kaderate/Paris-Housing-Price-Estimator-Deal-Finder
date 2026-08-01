from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from model import nettoyage_donnees, bon_plan, filtrer_criteres
import config


@pytest.fixture
def csv_brut(tmp_path):
    df = pd.DataFrame({
        "Prix": [1200.0, 5000.0, 900.0, 1000.0],   # 5000 dépasse PRIX_MAX -> filtré
        "Surface": [30.0, 50.0, 100.0, 25.0],       # ligne 3 (Prix m2=9) hors bornes -> filtrée
        "Arrondissement": [15, 8, 12, None],        # dernière ligne incomplète -> dropna
        "Pieces": [1, 2, 3, 1],
        "DPE": [4, 5, 3, 4],
    })
    chemin = tmp_path / "brut.csv"
    df.to_csv(chemin, index=False)
    return str(chemin)


def test_nettoyage_donnees_filtre_outliers_et_incomplets(csv_brut):
    df = nettoyage_donnees(csv_brut)

    assert len(df) == 1
    assert df.iloc[0]["Prix"] == 1200.0
    assert "Surface par pieces" in df.columns
    assert df.iloc[0]["Surface par pieces"] == 30.0


def test_nettoyage_donnees_types(csv_brut):
    df = nettoyage_donnees(csv_brut)

    assert df["Arrondissement"].dtype == int
    assert df["Pieces"].dtype == int
    assert df["DPE"].dtype == int


class ModeleFictif:
    """Simule un estimateur scikit-learn pour tester bon_plan sans entraînement réel."""

    def fit(self, x, y):
        return self

    def predict(self, x):
        return np.log1p(pd.Series([1000.0] * len(x)))

    def get_params(self, deep=True):
        return {}

    def set_params(self, **params):
        return self


def test_bon_plan_filtre_sur_le_seuil_de_decote(monkeypatch, tmp_path):
    df = pd.DataFrame({
        "Prix": [1200.0, 700.0, 1000.0],  # décotes vs estimation=1000 : +20%, -30%, 0%
        "Surface": [30.0, 30.0, 30.0],
        "Arrondissement": [15, 15, 15],
        "Pieces": [1, 1, 1],
        "DPE": [4, 4, 4],
    })
    x = df[["Surface", "Arrondissement", "Pieces", "DPE"]]
    y = np.log1p(df["Prix"])

    monkeypatch.setattr(
        "model.cross_val_predict",
        lambda model, x, y, cv: np.log1p(pd.Series([1000.0] * len(x))),
    )
    monkeypatch.setattr(config, "DEALS_CSV", str(tmp_path / "test_bonnes_affaires.csv"))

    _, df_deals = bon_plan(ModeleFictif(), x, y, df)

    assert len(df_deals) == 1
    assert df_deals.iloc[0]["Prix"] == 700.0
    assert df_deals.iloc[0]["Decote"] < config.DECOTE_SEUIL


def test_bon_plan_applique_les_criteres_de_recherche(monkeypatch, tmp_path):
    df = pd.DataFrame({
        "Prix": [700.0, 650.0],   # tous deux en décote (-30%, -35% vs estimation=1000)
        "Surface": [20.0, 60.0],  # seul le premier respecte surface_max=40
        "Arrondissement": [15, 15],
        "Pieces": [1, 1],
        "DPE": [4, 4],
    })
    x = df[["Surface", "Arrondissement", "Pieces", "DPE"]]
    y = np.log1p(df["Prix"])

    monkeypatch.setattr(
        "model.cross_val_predict",
        lambda model, x, y, cv: np.log1p(pd.Series([1000.0] * len(x))),
    )
    monkeypatch.setattr(config, "DEALS_CSV", str(tmp_path / "test_bonnes_affaires.csv"))

    _, df_deals = bon_plan(ModeleFictif(), x, y, df, surface_min=10, surface_max=40)

    assert len(df_deals) == 1
    assert df_deals.iloc[0]["Surface"] == 20.0


def test_filtrer_criteres_bornes():
    df = pd.DataFrame({
        "Prix": [800.0, 1200.0, 2000.0],
        "Surface": [15.0, 30.0, 50.0],
    })

    resultat = filtrer_criteres(df, surface_min=20, surface_max=40, budget_min=1000, budget_max=1500)

    assert len(resultat) == 1
    assert resultat.iloc[0]["Prix"] == 1200.0


def test_filtrer_criteres_sans_bornes_ne_filtre_rien():
    df = pd.DataFrame({"Prix": [800.0, 1200.0], "Surface": [15.0, 30.0]})

    resultat = filtrer_criteres(df)

    assert len(resultat) == len(df)


def test_bon_plan_ne_remonte_que_les_annonces_du_jour(monkeypatch, tmp_path):
    hier = (date.today() - timedelta(days=1)).isoformat()
    aujourdhui = date.today().isoformat()
    df = pd.DataFrame({
        "Prix": [700.0, 650.0],  # tous deux en décote vs estimation=1000
        "Surface": [30.0, 30.0],
        "Arrondissement": [15, 15],
        "Pieces": [1, 1],
        "DPE": [4, 4],
        "Date_scraping": [hier, aujourdhui],
    })
    x = df[["Surface", "Arrondissement", "Pieces", "DPE"]]
    y = np.log1p(df["Prix"])

    monkeypatch.setattr(
        "model.cross_val_predict",
        lambda model, x, y, cv: np.log1p(pd.Series([1000.0] * len(x))),
    )
    monkeypatch.setattr(config, "DEALS_CSV", str(tmp_path / "test_bonnes_affaires.csv"))

    _, df_deals = bon_plan(ModeleFictif(), x, y, df)

    assert len(df_deals) == 1
    assert df_deals.iloc[0]["Prix"] == 650.0  # l'annonce d'hier est exclue malgré sa décote
