import argparse
import logging

import config
from scrap import run_scraping
from model import nettoyage_donnees, model_entrainement, bon_plan
from report import generer_rapport

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Scrape les annonces de location à Paris et détecte les bonnes affaires."
    )
    parser.add_argument("--surface-min", type=float, default=None, help="Surface minimale souhaitée (m²)")
    parser.add_argument("--surface-max", type=float, default=None, help="Surface maximale souhaitée (m²)")
    parser.add_argument("--budget-min", type=float, default=None, help="Budget minimum souhaité (€)")
    parser.add_argument("--budget-max", type=float, default=None, help="Budget maximum souhaité (€)")
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
