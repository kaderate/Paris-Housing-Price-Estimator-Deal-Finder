import pandas as pd
import pytest
from playwright.sync_api import Error as PlaywrightError

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


class PageAvecErreurReseau:
    """Simule une page Playwright dont goto() échoue systématiquement avec une erreur réseau Chromium."""

    def __init__(self, message):
        self.message = message
        self.appels = 0

    def goto(self, url, wait_until=None):
        self.appels += 1
        raise PlaywrightError(self.message)


def test_goto_avec_retry_echoue_immediatement_sur_erreur_reseau():
    page = PageAvecErreurReseau("net::ERR_NAME_NOT_RESOLVED at https://www.paruvendu.fr/")

    with pytest.raises(scrap.ErreurReseau):
        scrap._goto_avec_retry(page, "https://www.paruvendu.fr/")

    assert page.appels == 1  # aucune tentative gaspillée : on échoue dès la première erreur réseau


def test_goto_avec_retry_reessaie_sur_simple_timeout(monkeypatch):
    monkeypatch.setattr(config, "RETRY_DELAY_SECONDS", 0)
    page = PageAvecErreurReseau("Timeout 30000ms exceeded.")

    resultat = scrap._goto_avec_retry(page, "https://www.paruvendu.fr/")

    assert resultat is False
    assert page.appels == config.MAX_PAGE_RETRIES  # un timeout applicatif est bien réessayé
