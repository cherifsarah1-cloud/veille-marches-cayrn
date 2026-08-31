import json, os, re
import anthropic
from config import (
    KEYWORDS_CORE_ENVIRO, KEYWORDS_SECONDAIRES, CONTEXT_TERMS, KEYWORDS_NEGATIFS,
    CLAUDE_MODEL, CLAUDE_MAX_TOKENS,
    SCORE_SEUIL, SEEN_IDS_FILE,
    KEYWORDS_SECTEUR_BOOST, SECTEUR_BONUS,
)

client = anthropic.Anthropic()

SYSTEM_PROMPT = """Tu es un assistant qui analyse des marches publics francais.
Tu reponds TOUJOURS et UNIQUEMENT avec un objet JSON valide sur une seule ligne.
Tu ne dis rien d'autre. Pas de texte avant, pas de texte apres, pas de markdown."""

def _build_prompt(avis: dict) -> str:
    acheteur = avis.get("acheteur") or {}
    return f"""Analyse ce marche public et reponds avec ce JSON exact (une seule ligne) :
{{"score":7,"type_mission":"Etude-Environnementale","resume":"Resume en 2 phrases.","points_attention":"Point de vigilance ou vide.","urgence":"moyenne"}}

Scoring (1-10) pour Symbiose, bureau d'etudes en genie ecologique specialise en :
- Accompagnement en phase de developpement : pre-diagnostics ecologiques, dossiers PC (volet environnemental), autorisations complementaires (loi sur l'eau, defrichement, derogation especes protegees)
- Accompagnement en phase de construction : preparation des engagements environnementaux (mesures ERC/ERCA), coordination de la compensation ecologique
- Accompagnement en phase exploitation : mission MOE fonciers compensatoires, suivi ecologique de centrale, suivi ORE
- Plus largement : diagnostics biodiversite, etudes d'impact environnemental, inventaires faune/flore, restauration ecologique/renaturation, missions liees a l'OFB/ARB/CDC biodiversite/MNHN

8-10 : mission d'etude/diagnostic/AMO environnemental ou de mise en oeuvre de mesures compensatoires clairement dans nos domaines
6-7  : mission connexe avec composante ecologique/environnementale significative (ex : mission mixte incluant un volet biodiversite)
4-5  : mention environnementale generique ou secondaire (ex : amenagement/PLU/risque naturel sans volet ecologique clair), a verifier
1-3  : hors cible (conseil financier pur, IT, RH, travaux de batiment sans lien ecologique, diagnostics techniques batiment...)

type_mission : Etude-Environnementale / AMO-Enviro / Mesures-Compensatoires / Diagnostic-Ecologique / Travaux-Restauration / Suivi-Exploitation / Autorisations-Reglementaires / Autre
urgence : haute (<3 sem) / moyenne (3-6 sem) / faible (>6 sem)

Marche :
Objet: {avis.get("objet", "N/A")}
Acheteur: {(acheteur.get("denominationSociale", "N/A"))}
Montant: {avis.get("montant", "N/C")} EUR
Procedure: {avis.get("procedure", "N/A")}
Famille: {avis.get("famille", "N/A")}
Date limite: {avis.get("dateLimiteReception", "N/A")}

JSON uniquement :"""


def _pre_filtre(avis: dict) -> bool:
    """
    Pre-filtre a deux niveaux, adapte au bruit specifique du secteur
    genie ecologique (PLU, amenagement, risque naturel sont trop generiques
    pour declencher seuls) :
    1. Au moins 1 mot-cle CORE, OU un mot-cle SECONDAIRE combine a un
       terme de contexte environnemental dans le meme avis.
    2. Ne doit pas contenir de mot-cle negatif.
    """
    texte = " ".join([
        (avis.get("objet") or ""),
        str(avis.get("cpv") or ""),
    ]).lower()

    has_core = any(kw.lower() in texte for kw in KEYWORDS_CORE_ENVIRO)
    has_secondaire = any(kw.lower() in texte for kw in KEYWORDS_SECONDAIRES)
    has_context = any(ctx.lower() in texte for ctx in CONTEXT_TERMS)
    has_negative = any(kw.lower() in texte for kw in KEYWORDS_NEGATIFS)

    has_signal = has_core or (has_secondaire and has_context)

    return has_signal and not has_negative


def _secteur_boost(avis: dict) -> tuple[int, list]:
    objet = (avis.get("objet") or "").lower()
    bonus_total = 0
    secteurs = []
    for secteur, keywords in KEYWORDS_SECTEUR_BOOST.items():
        if any(kw.lower() in objet for kw in keywords):
            secteurs.append(secteur)
            bonus_total += SECTEUR_BONUS.get(secteur, 1)
    return bonus_total, secteurs


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return None


def _scorer_avis(avis: dict) -> dict | None:
    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_prompt(avis)}],
        )
        raw = message.content[0].text.strip() if message.content else ""
        if not raw:
            return None
        analyse = _extract_json(raw)
        if not analyse:
            print(f"    [scorer] JSON invalide pour {avis.get('idweb')}: {raw[:80]}")
            return None
        return {**avis, **analyse}
    except Exception as e:
        print(f"    [scorer] Erreur Claude pour {avis.get('idweb')}: {e}")
        return None


def _load_seen_ids() -> set:
    if os.path.exists(SEEN_IDS_FILE):
        with open(SEEN_IDS_FILE) as f:
            return set(json.load(f))
    return set()


def _save_seen_ids(ids: set):
    os.makedirs(os.path.dirname(SEEN_IDS_FILE), exist_ok=True)
    with open(SEEN_IDS_FILE, "w") as f:
        json.dump(list(ids), f, indent=2)


def run_scoring(avis_list: list[dict], skip_seen: bool = True) -> list[dict]:
    seen_ids = _load_seen_ids() if skip_seen else set()
    scored   = []
    nb_total = len(avis_list)
    nb_new = nb_filtre = nb_claude = 0

    for avis in avis_list:
        idweb = avis.get("idweb")
        if skip_seen and idweb in seen_ids:
            continue
        nb_new += 1

        if not _pre_filtre(avis):
            seen_ids.add(idweb)
            continue
        nb_filtre += 1

        print(f"    [Claude] {idweb} - {avis.get('objet','')[:55]}...")
        result = _scorer_avis(avis)
        nb_claude += 1

        if result:
            score = result.get("score", 0)
            bonus, secteurs = _secteur_boost(avis)
            if bonus > 0:
                score = min(score + bonus, 10)
                result["score"]    = score
                result["secteurs"] = secteurs
            else:
                result["secteurs"] = []
            result["compensation_boost"] = "mesures_compensatoires" in result["secteurs"]

            boost_label = f" [+{bonus}: {','.join(secteurs)}]" if bonus > 0 else ""
            print(f"             -> {score}/10{boost_label} | {result.get('type_mission')} | {result.get('urgence')}")

            if score >= SCORE_SEUIL:
                scored.append(result)

        seen_ids.add(idweb)

    if skip_seen:
        _save_seen_ids(seen_ids)

    print(f"\n  [scorer] {nb_total} recus | {nb_new} nouveaux | {nb_filtre} pre-filtre | {nb_claude} Claude | {len(scored)} retenus")

    def sort_key(x):
        s = x.get("secteurs", [])
        priority = (
            3 * ("mesures_compensatoires" in s) +
            2 * ("biodiversite_institutionnel" in s) +
            2 * ("eau_zones_humides" in s) +
            1 * ("autorisations_reglementaires" in s) +
            1 * ("foret" in s)
        )
        return (x.get("score", 0), priority)

    return sorted(scored, key=sort_key, reverse=True)
