import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# AGENT VEILLE — SYMBIOSE (génie écologique / biodiversité)
# Fork indépendant de l'agent OPTIMA (conseil financier/juridique/structuration).
# Pipeline dupliqué volontairement : destinataires, filtres, prompt de scoring
# et périmètre métier sont propres à Symbiose, pas des variantes du même agent.
# =============================================================================

# --- Perimetre marches ---
# HYPOTHESE DE TRAVAIL (a confirmer) : contrairement a l'agent OPTIMA (SERVICES
# uniquement), on couvre ici SERVICES + TRAVAUX, car le Catalogue de Prestations
# Symbiose inclut des missions d'execution (coordination de la compensation,
# mission MOE foncier compensatoire, operateur de mesures environnementales)
# qui sont frequemment publiees en famille TRAVAUX sur BOAMP, pas uniquement
# en SERVICES intellectuels. A resserrer si trop de bruit constate en usage reel.
TYPE_MARCHE_SCOPE = ["SERVICES", "TRAVAUX"]

CPV_CODES = [
    # NB : non utilises directement dans boamp_fetcher.py (le fetch se fait par
    # requete texte 'q=', comme dans l'agent OPTIMA d'origine) — conserves ici
    # a titre de documentation / pour un futur filtre CPV explicite si besoin.
    "90700000",   # Services environnementaux
    "90711000",   # Services de conseil en environnement
    "71313000",   # Services de consultants en genie de l'environnement
    "90721800",   # Services de protection contre les risques naturels
    "77310000",   # Services de plantation et d'entretien d'espaces verts
    "90721500",   # Services de protection de la nature
]

MONTANT_MIN   = 5000  # seuil plus bas que l'agent OPTIMA : missions d'etudes/diagnostics souvent < 20k EUR
FAMILLES      = ["MARC", "CONCE", "AMI"]
LOOKBACK_DAYS = 15

# --- Mots-cles CORE (au moins 1 requis) ---
# Signal suffisamment specifique pour declencher seul un passage en scoring Claude.
# Corrections/verifications effectuees (28/08/2026) :
#   - "AFB" retire : l'Agence francaise pour la biodiversite a fusionne dans
#     l'OFB au 1er janvier 2020 (source : OFB / biodiversite.gouv.fr). Terme
#     obsolete pour des AO recents.
#   - "MNHM" corrige en "MNHN" (Museum National d'Histoire Naturelle).
#   - "OFB" = "Office francais de la biodiversite" (francais, pas francaise).
KEYWORDS_CORE_ENVIRO = [
    # Biodiversite institutionnel
    "biodiversite", "biodiversité",
    "atlas de la biodiversite", "atlas de la biodiversité",
    "atlas de la biodiversite communale", "ABC biodiversite",
    "solutions fondees sur la nature", "solutions fondées sur la nature", "SFN",
    "programme LIFE",
    "MNHN",
    "office francais de la biodiversite", "office français de la biodiversité", "OFB",
    "agence regionale de la biodiversite", "agence régionale de la biodiversité", "ARB",
    "CDC biodiversite", "CDC biodiversité",
    "federation de la recherche sur la biodiversite", "FRB",
    "tour du valat",
    "office national des forets", "office national des forêts", "ONF",
    "zone humide", "zones humides", "zone humides",

    # Coeur de metier Symbiose (aligne sur le Catalogue de Prestations v1)
    "sequence eviter reduire compenser", "sequence ERC", "mesures ERC", "mesures ERCA",
    "compensation ecologique", "compensation écologique",
    "mesures compensatoires",
    "foncier compensatoire",
    "obligation reelle environnementale", "obligation réelle environnementale", "ORE",
    "derogation especes protegees", "dérogation espèces protégées",
    "dossier CNPN",
    "defrichement", "défrichement",
    "loi sur l'eau", "dossier loi sur l'eau",
    "etude d'impact environnemental", "étude d'impact environnemental",
    "notice d'incidence environnementale",
    "diagnostic ecologique", "diagnostic écologique",
    "inventaire faune flore",
    "genie ecologique", "génie écologique",
    "restauration ecologique", "restauration écologique",
    "renaturation",
    "trame verte et bleue", "continuites ecologiques", "continuités écologiques",
    "natura 2000",
    "ZNIEFF",
    "GEMAPI",
    "suivi ecologique", "suivi écologique", "suivi environnemental",
]

# --- Mots-cles secondaires (SIGNAL AMBIGU) ---
# Trop generiques/frequents dans BOAMP pour declencher seuls le scoring Claude
# (fort volume de bruit constate). Ne comptent que combines a un terme CORE ou
# a un terme de CONTEXT_TERMS ci-dessous, dans le meme avis.
KEYWORDS_SECONDAIRES = [
    "PLU", "plan local d'urbanisme",       # tres frequent, hors perimetre la plupart du temps
    "amenagement", "aménagement",           # generique voirie/urbanisme/ZAC
    "amenagement du territoire", "aménagement du territoire",
    "risque naturel",                       # recoupe sismique/technologique, pas assez specifique
    "secheresse", "sécheresse",
    "inondation",
    "PAPI",                                 # programme d'action de prevention des inondations
]

CONTEXT_TERMS = [
    "environnement", "environnemental", "environnementale",
    "ecologique", "écologique", "ecologie", "écologie",
    "faune", "flore", "milieu naturel", "especes protegees", "espèces protégées",
    "biodiversite", "biodiversité", "zones humides", "hydraulique",
]

# Pour compatibilite avec scorer.py (pre-filtre)
KEYWORDS_POSITIFS = KEYWORDS_CORE_ENVIRO + KEYWORDS_SECONDAIRES

# --- Mots-cles NEGATIFS ---
# ATTENTION : volontairement different de la liste OPTIMA. "travaux",
# "espaces verts" et "diagnostic technique" ont ete RETIRES des negatifs
# (ils font partie du coeur de cible Symbiose selon le Catalogue de
# Prestations — cf mission MOE foncier compensatoire, suivi exploitation).
# Les negatifs ci-dessous ciblent le bruit reellement hors perimetre.
KEYWORDS_NEGATIFS = [
    "restauration collective", "restauration scolaire", "cantine",
    "nettoyage de locaux", "gardiennage", "securite incendie",
    "fourniture de bureau", "fournitures administratives",
    "telephonie", "informatique", "logiciel", "infogerance", "infogérance",
    "vehicules", "véhicules", "transport de personnes", "transport scolaire",
    "interim", "intérim", "recrutement",
    "assurance", "mutuelle",
    "audit comptable", "commissaire aux comptes", "expertise comptable",
    "medecine du travail", "médecine du travail",
    "diagnostic amiante", "diagnostic plomb", "DPE", "diagnostic technique batiment",
    "coordination SPS", "bureau de controle", "controle technique construction",
    "maintenance ascenseur", "maintenance chauffage",
]

# --- Boost secteurs prioritaires ---
KEYWORDS_SECTEUR_BOOST = {
    "biodiversite_institutionnel": [
        "OFB", "office francais de la biodiversite", "office français de la biodiversité",
        "ARB", "agence regionale de la biodiversite", "agence régionale de la biodiversité",
        "CDC biodiversite", "CDC biodiversité", "FRB", "MNHN", "tour du valat",
    ],
    "mesures_compensatoires": [
        "compensation ecologique", "compensation écologique", "mesures compensatoires",
        "foncier compensatoire", "mesures ERC", "mesures ERCA", "sequence ERC",
        "obligation reelle environnementale", "obligation réelle environnementale", "ORE",
    ],
    "eau_zones_humides": [
        "zone humide", "zones humides", "GEMAPI", "loi sur l'eau", "dossier loi sur l'eau",
    ],
    "autorisations_reglementaires": [
        "derogation especes protegees", "dérogation espèces protégées",
        "dossier CNPN", "defrichement", "défrichement",
    ],
    "foret": [
        "office national des forets", "office national des forêts", "ONF",
    ],
}

SECTEUR_BONUS = {
    "biodiversite_institutionnel": 1,
    "mesures_compensatoires":      2,  # coeur de cible Symbiose selon Catalogue de Prestations
    "eau_zones_humides":           1,
    "autorisations_reglementaires":1,
    "foret":                       1,
}

# --- Claude ---
CLAUDE_MODEL      = "claude-haiku-4-5"
CLAUDE_MAX_TOKENS = 800
SCORE_SEUIL       = 6

# --- Email ---
# IMPORTANT : a renseigner dans .env — placeholder volontaire, l'agent OPTIMA
# pointe vers sarah@cosygroup.fr, celui-ci doit pointer vers l'equipe/la
# personne Symbiose concernee (ex : Cedric, ou une adresse generique
# symbiose@cosygroup.fr) puisque l'usage n'est pas le meme.
DESTINATAIRES = os.getenv("EMAIL_DESTINATAIRES", "").split(",")
EXPEDITEUR    = os.getenv("EMAIL_EXPEDITEUR", "veille-symbiose@cosygroup.fr")

# --- Paths ---
SEEN_IDS_FILE  = "data/seen_ids.json"
DASHBOARD_FILE = "output/index.html"
# A renseigner apres creation du repo GitHub dedie (distinct de veille-marches OPTIMA)
DASHBOARD_URL  = os.getenv("DASHBOARD_URL", "https://TON_ORG.github.io/veille-marches-symbiose/")
