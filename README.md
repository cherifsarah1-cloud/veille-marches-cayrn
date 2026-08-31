# Veille Marchés — Symbiose (génie écologique / biodiversité)

Fork indépendant de l'agent `veille-marches` (OPTIMA), même architecture
(BOAMP + TED → pré-filtre → scoring Claude → dashboard statique GitHub Pages
+ digest email SendGrid), périmètre métier et destinataires différents.

## Ce qui diffère de l'agent OPTIMA

| | OPTIMA | Symbiose |
|---|---|---|
| Métier ciblé | Conseil financier/juridique, AMO, PPP/SEM, structuration | Génie écologique, études environnementales, mesures compensatoires |
| Périmètre `type_marche` | SERVICES uniquement | **SERVICES + TRAVAUX** (hypothèse — voir ci-dessous) |
| Seuil montant min | 20 000 € | 5 000 € (missions d'études souvent plus petites) |
| Mots-clés négatifs | excluent "travaux", "espaces verts", "diagnostic technique" | ces termes sont retirés des négatifs (cœur de cible Symbiose) |
| Destinataire email | sarah@cosygroup.fr | à définir (cf `.env`) |
| Dashboard / repo GitHub | veille-marches | veille-marches-symbiose (à créer) |

## Hypothèses prises à valider

1. **Périmètre SERVICES + TRAVAUX** : le Catalogue de Prestations Symbiose
   inclut des missions d'exécution (coordination de la compensation,
   mission MOE foncier compensatoire) qui sont souvent publiées en famille
   TRAVAUX sur BOAMP. À resserrer sur SERVICES seul si trop de bruit en
   usage réel (beaucoup plus de volume côté TRAVAUX).
2. **Destinataire email** : `EMAIL_DESTINATAIRES` dans `.env` est un
   placeholder — à renseigner avec l'adresse de la personne/équipe
   Symbiose concernée.
3. **AFB retiré des mots-clés** : cet établissement a fusionné dans l'OFB
   au 1er janvier 2020, il n'a plus d'existence propre pour des AO récents.
4. **MNHM → MNHN** : coquille corrigée (Muséum National d'Histoire Naturelle).
5. **PLU / aménagement / risque naturel** : trop génériques pour déclencher
   seuls le scoring (fort volume de bruit BOAMP). Ils ne comptent que
   combinés à un terme de contexte environnemental dans le même avis —
   voir `KEYWORDS_SECONDAIRES` / `CONTEXT_TERMS` dans `config.py`.

## Déploiement

1. Créer un nouveau repo GitHub (ex : `veille-marches-symbiose`), y pousser
   ce dossier.
2. Configurer les secrets GitHub Actions : `ANTHROPIC_API_KEY`,
   `SENDGRID_API_KEY` (Settings → Secrets and variables → Actions).
3. Activer GitHub Pages sur la branche `gh-pages` (créée automatiquement
   au premier run par `peaceiris/actions-gh-pages`).
4. Mettre à jour `DASHBOARD_URL` dans les secrets/variables ou `.env`
   local une fois l'URL Pages connue.
5. Renseigner `EMAIL_DESTINATAIRES` avec le(s) bon(s) destinataire(s).

## Test local

```bash
cp .env.example .env   # puis remplir ANTHROPIC_API_KEY au minimum
pip install -r requirements.txt
python run_local.py --days 30 --open
```

`run_local.py` ne touche pas à `data/seen_ids.json` et n'envoie pas
d'email — utile pour calibrer les mots-clés et le seuil de score avant
mise en prod.

## Fichiers modifiés par rapport à l'agent OPTIMA

- `config.py` — mots-clés, seuils, CPV, destinataires (entièrement réécrit)
- `boamp_fetcher.py` — nouveaux groupes de mots-clés, périmètre SERVICES+TRAVAUX
- `ted_fetcher.py` — CPV environnementaux
- `scorer.py` — prompt de scoring, pré-filtre à deux niveaux (core / secondaire+contexte), boosts sectoriels
- `mailer.py` — branding, sujet d'email
- `templates/dashboard.html`, `templates/email.html` — branding, catégories de badges, prompt de l'analyseur DCE
- `main.py`, `.github/workflows/veille.yml` — branding, cron décalé de 30 min

Non modifiés : `renderer.py`, `run_local.py`, `diagnose_boamp.py`,
`test_api.py`, `requirements.txt` (génériques, aucune dépendance au
secteur).
