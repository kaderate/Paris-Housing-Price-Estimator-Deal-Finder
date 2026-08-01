import logging
import re
import time
from datetime import date

import pandas as pd
import requests
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": config.USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


class ErreurReseau(RuntimeError):
    """Levée quand le site cible est injoignable pour une raison réseau (DNS, timeout persistant, connexion refusée)."""

    def __init__(self, url, cause):
        message = (
            f"\n{'=' * 70}\n"
            f"ERREUR RÉSEAU : impossible de joindre {url}\n"
            "Vérifie la connectivité réseau (DNS, proxy, pare-feu) de l'environnement "
            "d'exécution avant de relancer le pipeline.\n"
            f"Détail technique : {cause}\n"
            f"{'=' * 70}"
        )
        super().__init__(message)


class ErreurHTTP(RuntimeError):
    """Levée quand le site répond mais refuse explicitement la requête (403, 429, 5xx...)."""

    def __init__(self, url, status_code):
        message = (
            f"\n{'=' * 70}\n"
            f"ERREUR HTTP {status_code} sur {url}\n"
            "Le site a répondu mais a refusé la requête — probable protection anti-bot "
            "(en-têtes suspects, limitation de débit, adresse IP bloquée). Ce n'est pas "
            "un problème réseau : réessayer immédiatement ne changera rien.\n"
            f"{'=' * 70}"
        )
        super().__init__(message)


def _normaliser_espaces(texte):
    """Réduit tout run d'espaces/retours à la ligne à un simple espace.

    `BeautifulSoup.get_text()` restitue les retours à la ligne bruts du HTML source
    (ex. "sur\\n151"), alors que nos regex sont écrites en supposant un espace simple
    (ex. "sur 151"), comme le ferait le texte "rendu" d'un navigateur.
    """
    return re.sub(r"\s+", " ", texte)


def ajout_DPE(card, liste_DPE):
    try:
        dpe_element = card.select_one('span[class*="NoteEnerg_"]')
        liste_DPE.append(dpe_element.get_text(strip=True) if dpe_element else None)
    except Exception as e:
        logger.warning("Erreur lors de l'ajout du DPE : %s", e)
        liste_DPE.append(None)


def ajout_pieces(card, liste_pieces):
    try:
        piece_tag = card.select_one(
            "li.text-xs.text-grey-600.py-1.px-2.border-1.border-grey-50.rounded-xl.bg-grey-50.font-normal"
        )
        piece = _normaliser_espaces(piece_tag.get_text()) if piece_tag else ""
        motif_piece = r"[-+]?\d+(?:[.,]\d+)?(?=\s*(?:pièce|piece|pièces|pieces))"
        piece_text = re.findall(motif_piece, piece)
        liste_pieces.append(int(piece_text[0]) if piece_text else None)
    except Exception:
        liste_pieces.append(None)


def ajout_prix(card, liste_prix):
    try:
        prix_tag = card.select_one("div.encoded-lnk")
        prix = re.sub(r"\s+", "", prix_tag.get_text()) if prix_tag else ""
        motif_prix = r"[-+]?\d+(?:\.\d+)?"
        prix_texte = re.findall(motif_prix, prix)
        liste_prix.append(float(prix_texte[0]) if prix_texte else None)
    except Exception as e:
        logger.warning("Erreur lors de l'ajout du prix : %s", e)
        liste_prix.append(None)


def ajout_surface(card, liste_surface):
    try:
        motif_surface = r"[-+]?\d+(?:[.,]\d+)?(?=\s*(?:m2|m²))"
        lien_tag = card.select_one("a.hover\\:no-underline")
        surface = _normaliser_espaces(lien_tag.get_text()) if lien_tag else ""
        surface_texte = re.findall(motif_surface, surface)
        liste_surface.append(int(surface_texte[0]) if surface_texte else None)
    except Exception as e:
        logger.warning("Erreur lors de l'ajout de la surface : %s", e)
        liste_surface.append(None)


def ajout_arrondissement(card, liste_arrondissement):
    try:
        motif_arrondissement = r"(?<=(?:Paris ))\s*[-+]?\d+(?:[.,]\d+)?"
        lien_tag = card.select_one("a.hover\\:no-underline")
        arrondissement = _normaliser_espaces(lien_tag.get_text()) if lien_tag else ""
        arrondissement_texte = re.findall(motif_arrondissement, arrondissement)
        liste_arrondissement.append(int(arrondissement_texte[0]) if arrondissement_texte else None)
    except Exception as e:
        logger.warning("Erreur lors de l'ajout de l'arrondissement : %s", e)
        liste_arrondissement.append(None)


def ajout_lien(card, liste_lien):
    try:
        lien_tag = card.select_one("a.hover\\:no-underline")
        href = lien_tag.get("href") if lien_tag else None
        if href:
            liste_lien.append(href if href.startswith("http") else f"{config.SITE_URL}{href}")
        else:
            liste_lien.append(None)
    except Exception as e:
        logger.warning("Erreur lors de l'ajout du lien : %s", e)
        liste_lien.append(None)


def ajout_description(card, liste_description):
    try:
        desc_tag = card.select_one("p.line-clamp-5")
        description = desc_tag.get_text(strip=True) if desc_tag else None
        if not description:
            liste_description.append(None)
            return
        description = re.sub(r"\s+", " ", description)
        mots = description.split(" ")
        suffixe = "…" if len(mots) > config.DESCRIPTION_NB_MOTS else ""
        liste_description.append(" ".join(mots[: config.DESCRIPTION_NB_MOTS]) + suffixe)
    except Exception:
        liste_description.append(None)


def _get_avec_retry(url):
    """Récupère `url` en HTTP, avec réessais en cas d'erreur de connexion/timeout transitoire.

    Un statut HTTP d'erreur (403, 429, 5xx...) n'est PAS réessayé : le serveur a bel et bien
    répondu, donc ce n'est pas transitoire — on échoue immédiatement avec un message explicite
    plutôt que de perdre du temps sur plusieurs tentatives.
    """
    derniere_erreur = None
    for tentative in range(1, config.MAX_PAGE_RETRIES + 1):
        try:
            reponse = requests.get(url, headers=HEADERS, timeout=15)
        except requests.exceptions.RequestException as e:
            derniere_erreur = e
            logger.warning(
                "Erreur de connexion sur %s (tentative %d/%d) : %s",
                url, tentative, config.MAX_PAGE_RETRIES, e,
            )
            time.sleep(config.RETRY_DELAY_SECONDS)
            continue

        if reponse.status_code >= 400:
            raise ErreurHTTP(url, reponse.status_code)
        return reponse

    raise ErreurReseau(url, derniere_erreur)


def _sauvegarder_historique(df):
    """Ajoute les lignes scrapées aujourd'hui à l'historique, sans dupliquer les annonces déjà connues."""
    try:
        historique = pd.read_csv(config.HISTORY_CSV)
        combine = pd.concat([historique, df], ignore_index=True)
    except FileNotFoundError:
        combine = df

    colonnes_annonce = ["Lien", "Prix", "Surface", "Arrondissement", "Pieces", "DPE"]
    combine = combine.drop_duplicates(subset=colonnes_annonce, keep="first")
    combine.to_csv(config.HISTORY_CSV, index=False)
    logger.info("Historique mis à jour : %d annonces uniques cumulées.", len(combine))


def run_scraping():
    liste_prix = []
    liste_surface = []
    liste_pieces = []
    liste_arrondissement = []
    liste_DPE = []
    liste_lien = []
    liste_description = []

    try:
        reponse = _get_avec_retry(config.BASE_URL)
        soup = BeautifulSoup(reponse.text, "lxml")

        parent_block = soup.select("p.text-sm")
        card_texte = _normaliser_espaces(parent_block[-1].get_text()) if parent_block else ""
        motif_card = r"(?<=(?:sur ))\s*[-+]?\d+(?:[.,]\d+)?"
        page_text = re.findall(motif_card, card_texte)
        if not page_text:
            raise ValueError(
                "Compteur d'annonces introuvable dans la page — le site a probablement "
                "renvoyé un contenu inattendu (structure modifiée, page de blocage, etc.)."
            )
        nombre_pages = int(float(page_text[0]) // config.LISTINGS_PER_PAGE) + 1

        for i in range(1, nombre_pages + 1):
            logger.info("Analyse de la page %d/%d", i, nombre_pages)
            if i > 1:
                reponse = _get_avec_retry(f"{config.BASE_URL}&p={i}")
                soup = BeautifulSoup(reponse.text, "lxml")

            for card in soup.select("div.blocAnnonce"):
                ajout_prix(card, liste_prix)
                ajout_surface(card, liste_surface)
                ajout_arrondissement(card, liste_arrondissement)
                ajout_pieces(card, liste_pieces)
                ajout_DPE(card, liste_DPE)
                ajout_lien(card, liste_lien)
                ajout_description(card, liste_description)

            if i < nombre_pages:
                time.sleep(config.PAGE_DELAY_SECONDS)

        df = pd.DataFrame({
            "Prix": liste_prix,
            "Surface": liste_surface,
            "Arrondissement": liste_arrondissement,
            "Pieces": liste_pieces,
            "DPE": liste_DPE,
            "Lien": liste_lien,
            "Description": liste_description,
        })
        df["DPE"] = df["DPE"].map(config.DPE_MAP)
        df["Date_scraping"] = date.today().isoformat()
        df.to_csv(config.RAW_CSV, index=False)
        _sauvegarder_historique(df)
        return config.RAW_CSV

    except (ErreurReseau, ErreurHTTP) as e:
        logger.error(str(e))
        return None

    except Exception as e:
        logger.error("Exception pendant le scraping : %s", e)
        return None

    finally:
        logger.info("Fin du scraping")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_scraping()
