"""Génère un rapport lisible (Markdown) résumant les meilleures affaires détectées."""
import logging
from datetime import date

import pandas as pd

import config

logger = logging.getLogger(__name__)


def _decrire_criteres(criteres):
    if not criteres or not any(v is not None for v in criteres.values()):
        return None
    parties = []
    if criteres.get("surface_min") is not None or criteres.get("surface_max") is not None:
        smin = criteres.get("surface_min")
        smax = criteres.get("surface_max")
        parties.append(f"Surface : {smin if smin is not None else '…'} – {smax if smax is not None else '…'} m²")
    if criteres.get("budget_min") is not None or criteres.get("budget_max") is not None:
        bmin = criteres.get("budget_min")
        bmax = criteres.get("budget_max")
        parties.append(f"Budget : {bmin if bmin is not None else '…'} – {bmax if bmax is not None else '…'} €")
    return " | ".join(parties)


def generer_rapport(df, chemin=config.DEALS_REPORT_MD, top_n=20, criteres=None):
    """Écrit un résumé Markdown des `top_n` meilleures décotes à partir du DataFrame `df`."""
    description_criteres = _decrire_criteres(criteres)
    entete_criteres = f"\n*Critères de recherche : {description_criteres}*\n" if description_criteres else ""

    if df.empty:
        contenu = (
            f"# Bonnes affaires — {date.today().isoformat()}\n{entete_criteres}"
            "\nAucune annonce sous-évaluée détectée pour ces critères.\n"
        )
    else:
        top = df.head(top_n)
        lignes = [
            f"# Bonnes affaires — {date.today().isoformat()}",
            entete_criteres,
            f"{len(df)} annonce(s) sous-évaluée(s) détectée(s) (décote >= {abs(config.DECOTE_SEUIL)}%).",
            "",
            "| Décote | Prix | Estimation | Surface (m²) | Pièces | Arrondissement | DPE | Description | Annonce |",
            "|---:|---:|---:|---:|---:|---:|---:|---|---|",
        ]
        for _, row in top.iterrows():
            description = row["Description"] if "Description" in row and pd.notna(row["Description"]) else "—"
            lien = row["Lien"] if "Lien" in row and pd.notna(row["Lien"]) else None
            annonce = f"[Voir l'annonce]({lien})" if lien else "—"
            lignes.append(
                f"| {row['Decote']:.1f}% | {row['Prix']:.0f}€ | {row['Estimation']:.0f}€ "
                f"| {row['Surface']:.0f} | {int(row['Pieces'])} | {int(row['Arrondissement'])} | {int(row['DPE'])} "
                f"| {description} | {annonce} |"
            )
        contenu = "\n".join(lignes) + "\n"

    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)
    logger.info("Rapport écrit dans %s", chemin)
    return chemin
