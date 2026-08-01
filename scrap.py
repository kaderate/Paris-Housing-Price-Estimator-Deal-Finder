import logging
import re
import time
from datetime import date

import pandas as pd
from playwright.sync_api import sync_playwright, Error as PlaywrightError

import config

logger = logging.getLogger(__name__)

MARQUEURS_ERREUR_RESEAU = (
    "net::ERR_",
    "NS_ERROR_",
    "ERR_NAME_NOT_RESOLVED",
    "ERR_CONNECTION",
    "ERR_INTERNET_DISCONNECTED",
    "ERR_TUNNEL_CONNECTION_FAILED",
    "ERR_BLOCKED_BY_",
    "ERR_PROXY_CONNECTION_FAILED",
)


class ErreurReseau(RuntimeError):
    """Levée quand le site cible (ou le CDN Playwright) est injoignable pour une raison réseau."""

    def __init__(self, url, cause):
        message = (
            f"\n{'=' * 70}\n"
            f"ERREUR RÉSEAU : impossible de joindre {url}\n"
            f"Le domaine ({config.SITE_URL}) et/ou le CDN Playwright semble bloqué, "
            "mal résolu (DNS) ou inaccessible.\n"
            "Vérifie la configuration réseau (liste blanche de domaines, proxy, pare-feu) "
            "de l'environnement d'exécution avant de relancer le pipeline.\n"
            f"Détail technique : {cause}\n"
            f"{'=' * 70}"
        )
        super().__init__(message)


def _est_erreur_reseau(exception):
    """Détecte si une erreur Playwright ressemble à une coupure réseau plutôt qu'à un simple timeout applicatif."""
    message = str(exception)
    return any(marqueur in message for marqueur in MARQUEURS_ERREUR_RESEAU)


def ajout_DPE(card, liste_DPE):
    try:
        dpe_element = card.locator('span[class*="NoteEnerg_"]').first
        dpe_text = None
        if dpe_element.count() > 0:
            dpe_text = dpe_element.inner_text().strip()
        liste_DPE.append(dpe_text)
    except Exception as e:
        logger.warning("Erreur lors de l'ajout du DPE : %s", e)
        liste_DPE.append(None)


def ajout_pieces(card, liste_pieces):
    try:
        piece = card.locator("li.text-xs.text-grey-600.py-1.px-2.border-1.border-grey-50.rounded-xl.bg-grey-50.font-normal").first.inner_text(timeout=500)
        motif_piece = r"[-+]?\d+(?:[.,]\d+)?(?=\s*(?:pièce|piece|pièces|pieces))"
        piece_text = re.findall(motif_piece, piece)
        if piece_text:
            liste_pieces.append(int(piece_text[0]))
        else:
            liste_pieces.append(None)
    except Exception:
        liste_pieces.append(None)


def ajout_prix(card, liste_prix):
    try:
        prix = card.locator('div.encoded-lnk').inner_text().strip(" ")
        prix = re.sub(r"\s+", "", prix)
        motif_prix = r"[-+]?\d+(?:\.\d+)?"
        prix_texte = re.findall(motif_prix, prix)
        if prix_texte:
            liste_prix.append(float(prix_texte[0]))
        else:
            liste_prix.append(None)
    except Exception as e:
        logger.warning("Erreur lors de l'ajout du prix : %s", e)
        liste_prix.append(None)


def ajout_surface(card, liste_surface):
    try:
        motif_surface = r"[-+]?\d+(?:[.,]\d+)?(?=\s*(?:m2|m²))"
        surface = card.locator('a.hover\\:no-underline').first.inner_text()
        surface_texte = re.findall(motif_surface, surface)
        if surface_texte:
            liste_surface.append(int(surface_texte[0]))
        else:
            liste_surface.append(None)
    except Exception as e:
        logger.warning("Erreur lors de l'ajout de la surface : %s", e)
        liste_surface.append(None)


def ajout_arrondissement(card, liste_arrondissement):
    try:
        motif_arrondissement = r"(?<=(?:Paris ))\s*[-+]?\d+(?:[.,]\d+)?"
        arrondissement = card.locator('a.hover\\:no-underline').first.inner_text()
        arrondissement_texte = re.findall(motif_arrondissement, arrondissement)
        if arrondissement_texte:
            liste_arrondissement.append(int(arrondissement_texte[0]))
        else:
            liste_arrondissement.append(None)
    except Exception as e:
        logger.warning("Erreur lors de l'ajout de l'arrondissement : %s", e)
        liste_arrondissement.append(None)


def ajout_lien(card, liste_lien):
    try:
        href = card.locator('a.hover\\:no-underline').first.get_attribute("href")
        if href:
            if href.startswith("http"):
                liste_lien.append(href)
            else:
                liste_lien.append(f"{config.SITE_URL}{href}")
        else:
            liste_lien.append(None)
    except Exception as e:
        logger.warning("Erreur lors de l'ajout du lien : %s", e)
        liste_lien.append(None)


def ajout_description(card, liste_description):
    try:
        description = card.locator("p.line-clamp-5").first.inner_text(timeout=500).strip()
        description = re.sub(r"\s+", " ", description)
        mots = description.split(" ")
        liste_description.append(" ".join(mots[:config.DESCRIPTION_NB_MOTS]) + ("…" if len(mots) > config.DESCRIPTION_NB_MOTS else ""))
    except Exception:
        liste_description.append(None)


def _goto_avec_retry(page, url):
    """Navigue vers `url`, avec réessais en cas de timeout applicatif.

    Une erreur réseau (DNS, connexion refusée, domaine bloqué) n'est PAS réessayée :
    elle est quasi certainement persistante, donc on échoue immédiatement avec un
    message explicite plutôt que de perdre du temps sur plusieurs tentatives/pages.
    """
    derniere_erreur = None
    for tentative in range(1, config.MAX_PAGE_RETRIES + 1):
        try:
            page.goto(url, wait_until="networkidle")
            return True
        except PlaywrightError as e:
            if _est_erreur_reseau(e):
                raise ErreurReseau(url, e) from e
            derniere_erreur = e
            logger.warning(
                "Timeout sur %s (tentative %d/%d) : %s",
                url, tentative, config.MAX_PAGE_RETRIES, e,
            )
            time.sleep(config.RETRY_DELAY_SECONDS)
    logger.error("Abandon de la page %s après %d tentatives : %s", url, config.MAX_PAGE_RETRIES, derniere_erreur)
    return False


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
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=config.CHROMIUM_ARGS)
        context = browser.new_context(user_agent=config.USER_AGENT)
        page = context.new_page()

        try:
            liste_prix = []
            liste_surface = []
            liste_pieces = []
            liste_arrondissement = []
            liste_DPE = []
            liste_lien = []
            liste_description = []

            if not _goto_avec_retry(page, config.BASE_URL):
                logger.error("Impossible de charger la page de recherche initiale, scraping annulé.")
                return None

            parent_block = page.locator("p.text-sm").all()
            card = parent_block[-1].first.inner_text()
            motif_card = r"(?<=(?:sur ))\s*[-+]?\d+(?:[.,]\d+)?"
            page_text = re.findall(motif_card, card)
            nombre_pages = int(float(page_text[0]) // config.LISTINGS_PER_PAGE) + 1

            for i in range(1, nombre_pages + 1):
                logger.info("Analyse de la page %d/%d", i, nombre_pages)
                url_page = f"{config.BASE_URL}&p={i}"

                if not _goto_avec_retry(page, url_page):
                    logger.warning("Page %d ignorée après échec des tentatives.", i)
                    continue

                parent_block = page.locator("div.blocAnnonce").all()

                for card in parent_block:
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

        except ErreurReseau as e:
            logger.error(str(e))
            return None

        except Exception as e:
            logger.error("Exception pendant le scraping : %s", e)
            return None

        finally:
            logger.info("Fin du scraping")
            browser.close()
        return config.RAW_CSV


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_scraping()
