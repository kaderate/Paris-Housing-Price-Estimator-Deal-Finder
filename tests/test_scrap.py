import pandas as pd
import pytest
import requests

import config
import scrap


def test_sauvegarder_historique_dedoublonne(monkeypatch, tmp_path):
    historique = tmp_path / "historique.csv"
    monkeypatch.setattr(config, "HISTORY_CSV", str(historique))

    ancien = pd.DataFrame({
        "Prix": [1200.0], "Surface": [30.0], "Arrondissement": [15],
        "Pieces": [1], "DPE": [4], "Lien": ["https://www.paruvendu.fr/annonce/1"],
        "Date_scraping": ["2026-07-01"],
    })
    ancien.to_csv(historique, index=False)

    nouveau = pd.DataFrame({
        "Prix": [1200.0, 900.0], "Surface": [30.0, 20.0], "Arrondissement": [15, 5],
        "Pieces": [1, 1], "DPE": [4, 5],
        "Lien": ["https://www.paruvendu.fr/annonce/1", "https://www.paruvendu.fr/annonce/2"],
        "Date_scraping": ["2026-08-01", "2026-08-01"],
    })

    scrap._sauvegarder_historique(nouveau)

    resultat = pd.read_csv(historique)
    assert len(resultat) == 2  # l'annonce en doublon (Prix=1200...) n'est comptée qu'une fois
    assert resultat.iloc[0]["Date_scraping"] == "2026-07-01"  # la première occurrence est conservée


class ReponseFactice:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


def test_get_avec_retry_echoue_immediatement_sur_erreur_http(monkeypatch):
    appels = []

    def faux_get(url, headers=None, timeout=None):
        appels.append(url)
        return ReponseFactice(403)

    monkeypatch.setattr(scrap.requests, "get", faux_get)

    with pytest.raises(scrap.ErreurHTTP):
        scrap._get_avec_retry("https://www.paruvendu.fr/")

    assert len(appels) == 1  # aucune tentative gaspillée : un statut HTTP d'erreur n'est pas transitoire


def test_get_avec_retry_reessaie_sur_erreur_de_connexion(monkeypatch):
    monkeypatch.setattr(config, "RETRY_DELAY_SECONDS", 0)
    appels = []

    def faux_get(url, headers=None, timeout=None):
        appels.append(url)
        raise requests.exceptions.ConnectionError("boom")

    monkeypatch.setattr(scrap.requests, "get", faux_get)

    with pytest.raises(scrap.ErreurReseau):
        scrap._get_avec_retry("https://www.paruvendu.fr/")

    assert len(appels) == config.MAX_PAGE_RETRIES  # une erreur de connexion transitoire est bien réessayée


def test_get_avec_retry_retourne_la_reponse_si_succes(monkeypatch):
    def faux_get(url, headers=None, timeout=None):
        return ReponseFactice(200, text="<html></html>")

    monkeypatch.setattr(scrap.requests, "get", faux_get)

    reponse = scrap._get_avec_retry("https://www.paruvendu.fr/")

    assert reponse.status_code == 200
