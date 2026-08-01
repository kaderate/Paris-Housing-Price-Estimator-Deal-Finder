import pandas as pd

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
