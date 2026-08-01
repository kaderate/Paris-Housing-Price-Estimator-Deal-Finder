import argparse
import logging
import os

import config
from scrap import run_scraping
from model import nettoyage_donnees, model_entrainement, bon_plan
from report import generer_rapport

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _defaut_depuis_env(nom_variable):
    """Lit un critère de recherche depuis une variable d'environnement (ex. SURFACE_MIN),
    pour permettre de le régler sans toucher au code ni au prompt de la routine cloud."""
    valeur = os.environ.get(nom_variable)
    return float(valeur) if valeur else None


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Scrape les annonces de location à Paris et détecte les bonnes affaires."
    )
    parser.add_argument(
        "--surface-min", type=float, default=_defaut_depuis_env("SURFACE_MIN"),
        help="Surface minimale souhaitée (m²) [env: SURFACE_MIN]",
    )
    parser.add_argument(
        "--surface-max", type=float, default=_defaut_depuis_env("SURFACE_MAX"),
        help="Surface maximale souhaitée (m²) [env: SURFACE_MAX]",
    )
    parser.add_argument(
        "--budget-min", type=float, default=_defaut_depuis_env("BUDGET_MIN"),
        help="Budget minimum souhaité (€) [env: BUDGET_MIN]",
    )
    parser.add_argument(
        "--budget-max", type=float, default=_defaut_depuis_env("BUDGET_MAX"),
        help="Budget maximum souhaité (€) [env: BUDGET_MAX]",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    criteres = {
        "surface_min": args.surface_min,
        "surface_max": args.surface_max,
        "budget_min": args.budget_min,
        "budget_max": args.budget_max,
    }
    if any(v is not None for v in criteres.values()):
        logger.info("Critères de recherche : %s", criteres)

    logger.info("1. Lancement du Web Scraping...")
    fichier = run_scraping()

    if fichier:
        logger.info("2. Nettoyage des données (historique cumulé)...")
        df = nettoyage_donnees(config.HISTORY_CSV)

        logger.info("3. Entraînement du modèle Machine Learning...")
        model, x, y = model_entrainement(df)

        logger.info("4. Export des opportunités sous-évaluées...")
        chemin_csv, df_deals = bon_plan(model, x, y, df, **criteres)

        logger.info("5. Génération du rapport...")
        chemin_rapport = generer_rapport(df_deals, criteres=criteres)

        logger.info("Pipeline exécuté avec succès ! CSV : %s | Rapport : %s", chemin_csv, chemin_rapport)
    else:
        logger.error("Le scraping a échoué, pipeline interrompu.")
