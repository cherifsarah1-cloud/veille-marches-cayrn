"""
Recuperation des avis BOAMP via l'API OpenDataSoft.
Resserre sur missions de genie ecologique, biodiversite, mesures
compensatoires et environnement (filiale Symbiose).
"""

import requests
from datetime import datetime, timedelta
from config import MONTANT_MIN, LOOKBACK_DAYS, TYPE_MARCHE_SCOPE

BASE_URL = "https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records"
TIMEOUT  = 30

# Groupes de recherche cibles - genie ecologique / biodiversite / environnement
KEYWORD_GROUPS = [
    "biodiversite atlas solutions fondees nature etude ecologique",
    "compensation ecologique mesures ERC ERCA foncier compensatoire",
    "derogation especes protegees CNPN dossier loi sur l'eau defrichement",
    "zone humide zones humides GEMAPI continuites ecologiques trame verte bleue",
    "diagnostic ecologique inventaire faune flore restauration ecologique renaturation",
    "office francais biodiversite OFB agence regionale biodiversite",
    "genie ecologique bureau etude environnement mission AMO environnement",
    "obligation reelle environnementale ORE suivi ecologique exploitation",
    "programme LIFE biodiversite territoire",
    "office national forets ONF gestion forestiere ecologique",
    "etude d'impact environnemental notice incidence environnementale",
    "natura 2000 ZNIEFF protection especes milieux naturels",
]


def fetch_avis(lookback_days: int = LOOKBACK_DAYS) -> list[dict]:
    date_min = (datetime.today() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    seen_ids: set = set()
    results:  list = []

    type_marche_filter = " OR ".join(f"type_marche='{t}'" for t in TYPE_MARCHE_SCOPE)

    for keyword_group in KEYWORD_GROUPS:
        offset = 0
        while True:
            params = {
                "where":    f"dateparution >= '{date_min}' AND ({type_marche_filter})",
                "q":        keyword_group,
                "limit":    100,
                "offset":   offset,
                "order_by": "dateparution DESC",
            }
            try:
                r = requests.get(BASE_URL, params=params, timeout=TIMEOUT)
                r.raise_for_status()
                data = r.json()
            except requests.exceptions.HTTPError as e:
                print(f"  [BOAMP] HTTP {e.response.status_code} - '{keyword_group[:40]}'")
                break
            except Exception as e:
                print(f"  [BOAMP] Erreur - '{keyword_group[:40]}': {e}")
                break

            records = data.get("results", [])
            if not records:
                break

            for record in records:
                idweb = record.get("idweb") or record.get("id", "")
                if not idweb or idweb in seen_ids:
                    continue
                montant = _extract_montant(record)
                if montant and montant < MONTANT_MIN:
                    continue
                seen_ids.add(idweb)
                results.append(_normalize(record, montant))

            total = data.get("total_count", "?")
            print(f"  [BOAMP] '{keyword_group[:40]}' -> {len(records)} (total: {total})")

            if len(records) < 100:
                break
            offset += 100

    print(f"  [BOAMP] Total : {len(results)} avis uniques (fenetre : {lookback_days}j, perimetre : {TYPE_MARCHE_SCOPE})")
    return results


def _extract_montant(record: dict):
    m = record.get("montant")
    if m:
        try:
            return float(str(m).replace(" ", "").replace(",", "."))
        except (ValueError, TypeError):
            pass
    donnees = record.get("donnees")
    if isinstance(donnees, str):
        import json
        try:
            d = json.loads(donnees)
            m = d.get("MONTANT") or d.get("montant")
            if m:
                return float(str(m).replace(" ", "").replace(",", "."))
        except Exception:
            pass
    return None


def _normalize(record: dict, montant) -> dict:
    idweb = record.get("idweb") or record.get("id", "")
    url = record.get("url_avis") or f"https://www.boamp.fr/pages/avis/?q=idweb:{idweb}"
    dept_raw = record.get("code_departement") or []
    dept = dept_raw[0] if isinstance(dept_raw, list) and dept_raw else str(dept_raw)

    return {
        "idweb":               idweb,
        "objet":               record.get("objet") or "Sans objet",
        "acheteur": {
            "denominationSociale": record.get("nomacheteur") or "N/C",
            "departement":         dept,
        },
        "montant":             montant,
        "procedure":           record.get("procedure_libelle") or record.get("procedure_categorise") or "",
        "famille":             record.get("famille") or record.get("famille_libelle") or "",
        "datePublication":     (record.get("dateparution") or "")[:10],
        "dateLimiteReception": (record.get("datelimitereponse") or "")[:10],
        "urlAvis":             url,
        "cpv":                 record.get("descripteur_code") or [],
        "nature":              record.get("nature_libelle") or "",
        "_source":             "BOAMP",
    }
