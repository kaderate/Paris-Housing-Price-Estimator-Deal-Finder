"""Configuration centralisée du pipeline (URLs, chemins, seuils)."""

# --- Scraping ---
SITE_URL = "https://www.paruvendu.fr"
DESCRIPTION_NB_MOTS = 12  # nombre de mots conservés pour la description courte d'une annonce
BASE_URL = (
    "https://www.paruvendu.fr/immobilier/recherche/location/appartement/paris-75/"
    "?rechpv=1&tt=5&tbApp=1&tbDup=1&tbChb=1&tbLof=1&tbAtl=1&tbPla=1&tbMai=1&tbVil=1"
    "&tbCha=1&tbPro=1&tbHot=1&tbMou=1&lo=75&ddlFiltres=nofilter&prestige=0"
)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, Gecko) Chrome/144.0.0.0 Safari/537.36"
)
DPE_MAP = {"A": 7, "B": 6, "C": 5, "D": 4, "E": 3, "F": 2, "G": 1}
LISTINGS_PER_PAGE = 30
MAX_PAGE_RETRIES = 3
RETRY_DELAY_SECONDS = 2
PAGE_DELAY_SECONDS = 1.0  # pause entre deux pages pour limiter le risque de blocage

# --- Fichiers ---
RAW_CSV = "Data_Loyer.csv"
HISTORY_CSV = "Data_Loyer_historique.csv"
DEALS_CSV = "Appartement_interessant.csv"
DEALS_REPORT_MD = "rapport_bonnes_affaires.md"

# --- Nettoyage des données ---
PRIX_MAX = 3000
PRIX_M2_MIN = 15
PRIX_M2_MAX = 80

# --- Détection de bonnes affaires ---
DECOTE_SEUIL = -15  # une annonce est une "bonne affaire" si sa décote est <= à ce seuil (%)
