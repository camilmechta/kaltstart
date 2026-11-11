# Phase 1 : ingestion Tech.eu — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Récupérer les levées de fonds Tech.eu pour la Suisse, l'Allemagne et l'Autriche, les nettoyer, les stocker dans Supabase et les tenir à jour chaque nuit sans doublon.

**Architecture:** Un client HTTP parle à l'API Tech.eu, des fonctions pures nettoient les données, un « store » écrit dans Supabase, et un pipeline les enchaîne. Les données brutes sont conservées à côté des données nettoyées, pour rejouer le nettoyage sans rappeler l'API. Le store a une version en mémoire pour les tests : aucun test ne touche au réseau.

**Tech Stack:** Python 3.12+, httpx, supabase-py, pytest, GitHub Actions. Paquet Python `kaltstart` dans `src/kaltstart/`.

**Spec:** `docs/superpowers/specs/2026-11-11-candidatures-spontanees-hsg-design.md`

## Global Constraints

- Aucun appel à une API d'IA à l'exécution.
- Aucun test ne fait d'appel réseau réel ; les réponses Tech.eu sont rejouées depuis `tests/fixtures/techeu/`.
- Quotas Tech.eu : 120 requêtes par minute, 600 par heure, 2000 par jour. Le client attend 7 secondes entre deux requêtes (environ 514 par heure) et s'arrête à 1500 requêtes par exécution.
- Pays couverts, orthographe exacte de l'API : `Switzerland`, `Germany`, `Austria`.
- Mention de la source dans le README : « Tech.eu Funding Explorer », licence CC BY 4.0.
- Fichiers publics du repo, code, commentaires et messages de commit en anglais. Spec et plans en français.
- Aucun secret dans le repo : les clés Supabase passent par des variables d'environnement (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`).
- Développement piloté par les tests : le test est écrit et vu en échec avant le code.
- Un commit par tâche au minimum, message au format `type: description` (`feat`, `test`, `docs`, `chore`, `fix`).

## Ce que l'API renvoie réellement (vérifié le 2026-11-11)

`GET /api/v1/rounds?country=&from=&to=&limit=&after=` renvoie
`{data: [...], nextCursor, count, appliedFilters, ...}`. `nextCursor` vaut
`null` sur la dernière page. Un pays inconnu renvoie HTTP 400 avec
`{error, hint}`. Une levée :

```json
{"id": "F9B3...", "pageUrl": "https://funding.tech.eu/deals/F9B3...",
 "date": "2026-11-10", "stage": "Seed", "rawRoundType": "seed",
 "amountEur": 4547887, "amountNative": 5100000, "currency": "USD",
 "company": {"id": "0DF1...", "name": "Light Frame", "country": "Switzerland",
             "pageUrl": "https://funding.tech.eu/companies/light-frame-0df151be",
             "city": "Lausanne", "founded": null, "sectors": ["Fintech"]},
 "investors": ["Rogue Venture Partners", "Tenity "],
 "source": {"domain": "tech.eu", "tier": "own"}, "confidence": "high"}
```

Faits observés sur 100 levées suisses :

- `amountEur` est déjà en euros ; il vaut `null` pour 27 levées sur 100, avec `currency` égal à `""`.
- Valeurs de `stage` : `Pre-Seed`, `Seed`, `Series A`, `Series B`, `Series C`, `Series D+`, `Growth/Late`, `Grant`, `Debt`, `Other` (53 sur 100).
- `city` peut être `null`, `""`, finir par un espace (`"Zurich "`), ou contenir un canton (`"Vaud"`, `"Obwalden"`). `"Bern"` et `"Berne"` coexistent.
- Les noms d'investisseurs peuvent finir par un espace (`"Tenity "`).

`GET /api/v1/companies/{id}` renvoie `description`, `website`, `founded`,
`founders` (vide), `sectors`, `rounds`.

`GET /api/v1/changes?since=<date ou horodatage ISO>&limit=` renvoie les levées
ajoutées depuis `since`, tous pays confondus, avec un champ `createdAt`, plus
`removed` (levées supprimées) et `nextCursor`. Cette réponse n'a pas de
`appliedFilters` : le filtrage par pays se fait donc de notre côté. Les
modifications d'une levée déjà existante n'y figurent pas.

En-têtes de réponse : `ratelimit-limit`, `ratelimit-remaining`, `ratelimit-reset`.

## Review Focus

1. Levée sans ville, sans montant ou sans devise (`null` ou `""`) : elle est stockée sans erreur, avec `city` et `amount_eur` à `null`. Test en tâche 3.
2. Même entreprise dans plusieurs levées avec des orthographes de ville différentes : une seule ligne `companies`, la levée la plus récente l'emporte. Test en tâche 6.
3. L'API renvoie 429 ou ne répond pas au milieu d'une pagination : trois essais, puis arrêt ; l'exécution est enregistrée en échec et rien n'est marqué comme réussi. Tests en tâches 4 et 6.
4. Le budget de 1500 requêtes est atteint pendant la récupération des fiches d'entreprise : arrêt propre, l'exécution suivante reprend là où on s'est arrêté. Test en tâche 6.
5. Site web absent ou mal formé dans la fiche (`null`, sans `https://`, espaces) : normalisé ou mis à `null`, jamais stocké tel quel. Test en tâche 3.

---

## Structure des fichiers

| Fichier | Responsabilité |
|---|---|
| `pyproject.toml` | Paquet `kaltstart`, dépendances, configuration pytest |
| `src/kaltstart/ingestion/cleaning.py` | Fonctions pures : villes, investisseurs, catégorie de taille, site web |
| `src/kaltstart/ingestion/city_aliases.csv` | Table de correspondance des villes, écrite à la main |
| `src/kaltstart/ingestion/transform.py` | Passe d'une levée brute aux lignes `companies` et `rounds` |
| `src/kaltstart/ingestion/techeu_client.py` | Appels HTTP : pagination, vérification des filtres, rythme, essais, budget |
| `src/kaltstart/ingestion/store.py` | Interface `Store` et `InMemoryStore` pour les tests |
| `src/kaltstart/ingestion/supabase_store.py` | `SupabaseStore`, même interface, écrit dans Supabase |
| `src/kaltstart/ingestion/pipeline.py` | Enchaînements : `backfill`, `sync_changes`, `fetch_company_details`, `reclean` |
| `src/kaltstart/ingestion/__main__.py` | Ligne de commande `python -m kaltstart.ingestion <commande>` |
| `supabase/migrations/0001_ingestion.sql` | Création des tables |
| `.github/workflows/tests.yml` | Lance pytest à chaque push |
| `.github/workflows/nightly.yml` | Lance la synchronisation chaque nuit |
| `tests/ingestion/` | Un fichier de test par module |
| `tests/fixtures/techeu/` | Réponses réelles de l'API enregistrées |

Forme des lignes échangées entre modules (dictionnaires Python) :

```python
CompanyRow = {"id": str, "name": str, "country": str, "city_raw": str | None,
              "city": str | None, "region": str | None, "sectors": list[str],
              "techeu_url": str}
RoundRow = {"id": str, "company_id": str, "date": str, "stage": str | None,
            "raw_round_type": str | None, "amount_eur": int | None,
            "amount_native": float | None, "currency": str | None,
            "size_category": str, "investors": list[str], "source_url": str,
            "source_domain": str | None, "confidence": str | None}
CompanyDetails = {"website": str | None, "description": str | None,
                  "founded": int | None}
```

---

### Task 1 : squelette du projet et documents publics

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `src/kaltstart/__init__.py`, `src/kaltstart/ingestion/__init__.py`, `tests/__init__.py`, `tests/ingestion/__init__.py`, `tests/test_smoke.py`
- Create: `README.md`, `PRD.md`, `DECISIONS.md`, `CHANGELOG.md`, `CLAUDE.md`
- Create: `.github/workflows/tests.yml`
- Create: `tests/fixtures/techeu/rounds_page1.json`, `rounds_page2.json`, `company.json`, `changes.json`

**Interfaces:**
- Produces: paquet importable `kaltstart` ; commande `pytest` ; fixtures. `rounds_page1.json` contient 3 levées et un `nextCursor` non nul, `rounds_page2.json` contient 2 levées et `nextCursor: null`, toutes deux avec `appliedFilters` égal à `{"country": "Switzerland", "from": "2026-09-01", "to": "2026-11-10"}`. `changes.json` contient au moins une levée suisse, une britannique, et `removed: []`.

- [ ] **Step 1 :** écrire `tests/test_smoke.py`

```python
def test_package_imports():
    import kaltstart.ingestion  # noqa: F401
```

- [ ] **Step 2 :** lancer `pytest -q`. Attendu : échec, `ModuleNotFoundError: kaltstart`.
- [ ] **Step 3 :** créer `pyproject.toml` (nom `kaltstart`, `requires-python = ">=3.12"`, dépendances `httpx`, `supabase` ; extra `dev` avec `pytest` ; paquets sous `src/` ; `[tool.pytest.ini_options] testpaths = ["tests"]`), les fichiers `__init__.py`, puis `pip install -e ".[dev]"`.
- [ ] **Step 4 :** lancer `pytest -q`. Attendu : `1 passed`.
- [ ] **Step 5 :** créer `.gitignore` (`.env`, `__pycache__/`, `.venv/`, `*.egg-info/`, `.pytest_cache/`) et `.env.example` (`SUPABASE_URL=`, `SUPABASE_SERVICE_KEY=`, sans valeur).
- [ ] **Step 6 :** enregistrer les fixtures à partir de vraies réponses de l'API (4 requêtes au plus), en les réduisant à la taille indiquée dans « Produces ».
- [ ] **Step 7 :** écrire les documents publics, en anglais :
  - `PRD.md` : problème, utilisateurs, parcours, périmètre et hors périmètre, métriques et seuils, phases. Contenu repris des sections 1 à 4 et 10 de la spec.
  - `DECISIONS.md` : D1 à D13 de la spec, plus D14 (paquet `src/kaltstart/` au lieu de `src/ingestion/` directement : un nom de paquet unique évite les conflits d'import) et D15 (synchronisation nocturne par `/changes` : c'est le mécanisme prévu par l'API, il signale aussi les suppressions).
  - `CHANGELOG.md` : format « Keep a Changelog », une entrée `Phase 0`.
  - `CLAUDE.md` : commandes (`pip install -e ".[dev]"`, `pytest -q`), les contraintes globales ci-dessus, la structure des dossiers, la règle « mettre à jour DECISIONS.md et CHANGELOG.md à chaque changement notable ».
  - `README.md` : description en trois phrases, statut du projet par phase, installation, mention « Data: Tech.eu Funding Explorer, CC BY 4.0 ».
- [ ] **Step 8 :** créer `.github/workflows/tests.yml` : sur `push` et `pull_request`, Python 3.12, `pip install -e ".[dev]"`, `pytest -q`.
- [ ] **Step 9 :** commit `chore: scaffold project, public docs and CI`.

### Task 2 : fonctions de nettoyage

**Files:**
- Create: `src/kaltstart/ingestion/cleaning.py`, `src/kaltstart/ingestion/city_aliases.csv`
- Test: `tests/ingestion/test_cleaning.py`

**Interfaces:**
- Produces:
  - `clean_city(raw: str | None) -> tuple[str | None, str | None]` renvoie `(city, region)`.
  - `clean_investors(raw: list[str] | None) -> list[str]`
  - `size_category(stage: str | None, amount_eur: int | None) -> str` renvoie `"small"`, `"medium"` ou `"large"`.
  - `clean_website(raw: str | None) -> str | None`
  - Constantes `SMALL_MAX_EUR = 3_000_000` et `MEDIUM_MAX_EUR = 15_000_000`.

- [ ] **Step 1 :** écrire les tests

```python
import pytest
from kaltstart.ingestion.cleaning import (
    clean_city, clean_investors, clean_website, size_category)

@pytest.mark.parametrize("raw,expected", [
    ("Zurich ", ("Zurich", None)),
    ("  Zürich", ("Zurich", None)),
    ("Berne", ("Bern", None)),
    ("Vaud", (None, "Vaud")),
    ("Obwalden", (None, "Obwalden")),
    ("St.  Gallen", ("St. Gallen", None)),
    ("Eggersriet", ("Eggersriet", None)),   # inconnue : conservée telle quelle
    ("", (None, None)),
    (None, (None, None)),
])
def test_clean_city(raw, expected):
    assert clean_city(raw) == expected

def test_clean_investors_strips_and_dedupes_keeping_order():
    assert clean_investors(["Tenity ", "Altair Capital", "Tenity", ""]) == [
        "Tenity", "Altair Capital"]
    assert clean_investors(None) == []

@pytest.mark.parametrize("stage,amount,expected", [
    ("Pre-Seed", 50_000_000, "small"),      # le stade connu l'emporte
    ("Seed", None, "small"),
    ("Series A", None, "medium"),
    ("Series B", 1_000_000, "large"),
    ("Series C", None, "large"),
    ("Series D+", None, "large"),
    ("Growth/Late", None, "large"),
    ("Other", 2_999_999, "small"),
    ("Other", 3_000_000, "medium"),
    ("Other", 15_000_000, "medium"),
    ("Other", 15_000_001, "large"),
    ("Grant", 150_000, "small"),            # Grant et Debt : selon le montant
    ("Debt", 20_000_000, "large"),
    ("Other", None, "small"),               # ni stade ni montant
    (None, None, "small"),
    ("Brand New Stage", 5_000_000, "medium"),
])
def test_size_category(stage, amount, expected):
    assert size_category(stage, amount) == expected

@pytest.mark.parametrize("raw,expected", [
    ("https://www.lightframe.tech/", "https://www.lightframe.tech"),
    (" www.example.ch ", "https://www.example.ch"),
    ("http://example.de/path", "http://example.de/path"),
    ("", None), (None, None), ("not a url", None),
])
def test_clean_website(raw, expected):
    assert clean_website(raw) == expected
```

- [ ] **Step 2 :** lancer `pytest tests/ingestion/test_cleaning.py -q`. Attendu : échec à l'import.
- [ ] **Step 3 :** créer `city_aliases.csv` avec les colonnes `raw,city,region`. La colonne `raw` est comparée sans tenir compte de la casse. Lignes de départ — variantes : Zürich→Zurich, Berne→Bern, Genève→Geneva, Genf→Geneva, Luzern→Lucerne, Basle→Basel, München→Munich, Köln→Cologne, Nürnberg→Nuremberg, Wien→Vienna. Régions (colonne `city` vide) : Vaud, Obwalden, Bavaria, Bayern, Baden-Württemberg, North Rhine-Westphalia, Hesse, Tyrol, Styria.
- [ ] **Step 4 :** implémenter les quatre fonctions. `clean_city` : remplace les suites d'espaces par un seul, retire ceux des bords, puis cherche dans la table ; une valeur absente de la table est renvoyée comme ville. `clean_website` : retire les espaces et le `/` final, ajoute `https://` s'il n'y a pas de schéma, renvoie `None` si le résultat contient un espace ou n'a pas de point dans le nom d'hôte.
- [ ] **Step 5 :** lancer `pytest tests/ingestion/test_cleaning.py -q`. Attendu : tous passent.
- [ ] **Step 6 :** commit `feat: add cleaning rules for cities, investors, size and websites`.

### Task 3 : transformation d'une levée brute

**Files:**
- Create: `src/kaltstart/ingestion/transform.py`
- Test: `tests/ingestion/test_transform.py`

**Interfaces:**
- Consumes: les fonctions de `cleaning.py`.
- Produces:
  - `transform_round(raw: dict) -> tuple[CompanyRow, RoundRow]`
  - `transform_company_details(raw: dict) -> CompanyDetails`

- [ ] **Step 1 :** écrire les tests

```python
import json, pathlib
from kaltstart.ingestion.transform import transform_round, transform_company_details

FIX = pathlib.Path(__file__).parents[1] / "fixtures" / "techeu"

def _round(**overrides):
    raw = json.loads((FIX / "rounds_page1.json").read_text())["data"][0]
    raw.update(overrides)
    return raw

def test_transform_round_maps_all_fields():
    raw = _round()
    company, rnd = transform_round(raw)
    assert company == {
        "id": raw["company"]["id"], "name": raw["company"]["name"],
        "country": "Switzerland", "city_raw": raw["company"]["city"],
        "city": "Lausanne", "region": None,
        "sectors": raw["company"]["sectors"],
        "techeu_url": raw["company"]["pageUrl"]}
    assert rnd["id"] == raw["id"]
    assert rnd["company_id"] == raw["company"]["id"]
    assert rnd["date"] == raw["date"]
    assert rnd["amount_eur"] == raw["amountEur"]
    assert rnd["size_category"] == "small"
    assert rnd["source_url"] == raw["pageUrl"]
    assert rnd["source_domain"] == raw["source"]["domain"]
    assert all(name == name.strip() for name in rnd["investors"])

def test_missing_amount_city_and_currency_become_none():
    raw = _round(amountEur=None, amountNative=None, currency="", fx=None)
    raw["company"] = {**raw["company"], "city": None, "sectors": None}
    company, rnd = transform_round(raw)
    assert (company["city"], company["region"], company["sectors"]) == (None, None, [])
    assert (rnd["amount_eur"], rnd["currency"]) == (None, None)

def test_missing_source_and_investors():
    company, rnd = transform_round(_round(source=None, investors=None))
    assert rnd["source_domain"] is None and rnd["investors"] == []

def test_company_details():
    raw = json.loads((FIX / "company.json").read_text())
    assert transform_company_details(raw) == {
        "website": "https://www.lightframe.tech",
        "description": raw["description"], "founded": raw["founded"]}

def test_company_details_with_bad_website_and_blank_description():
    assert transform_company_details(
        {"website": "n/a", "description": "  ", "founded": None}
    ) == {"website": None, "description": None, "founded": None}
```

- [ ] **Step 2 :** lancer `pytest tests/ingestion/test_transform.py -q`. Attendu : échec à l'import.
- [ ] **Step 3 :** implémenter les deux fonctions dans `transform.py`. Toute chaîne vide devient `None`.
- [ ] **Step 4 :** relancer. Attendu : tous passent.
- [ ] **Step 5 :** commit `feat: transform raw Tech.eu rounds into company and round rows`.

### Task 4 : client Tech.eu

**Files:**
- Create: `src/kaltstart/ingestion/techeu_client.py`
- Test: `tests/ingestion/test_techeu_client.py`

**Interfaces:**
- Produces:
  - `class TechEuClient(http: httpx.Client, min_interval_s: float = 7.0, max_requests: int = 1500, sleep: Callable[[float], None] = time.sleep)` avec l'attribut `requests_made: int`.
  - `iter_rounds(country: str, date_from: str, date_to: str) -> Iterator[dict]`
  - `fetch_changes(since: str) -> tuple[list[dict], list[str]]` renvoie `(levées ajoutées, identifiants supprimés)`.
  - `get_company(company_id: str) -> dict`
  - Exceptions : `TechEuError`, et ses sous-classes `FilterMismatchError` et `BudgetExhaustedError`.
  - `BASE_URL = "https://funding.tech.eu/api/v1"`, `PAGE_SIZE = 100`.

Les tests construisent le client avec `httpx.Client(transport=httpx.MockTransport(handler), base_url=BASE_URL)` et `sleep` remplacé par une fonction qui enregistre les durées.

- [ ] **Step 1 :** écrire les tests, un par comportement :
  - `test_iter_rounds_follows_cursor` : le handler sert `rounds_page1.json` puis `rounds_page2.json` ; on obtient 5 levées ; la deuxième requête porte `after=<nextCursor de la page 1>` ; chaque requête porte `country=Switzerland`, `from`, `to`, `limit=100`.
  - `test_filter_mismatch_raises` : la réponse a `appliedFilters` sans `country` ; `list(client.iter_rounds(...))` lève `FilterMismatchError` avant de produire la moindre levée.
  - `test_waits_between_requests` : après deux requêtes, `sleep` a été appelé avec une durée comprise entre 0 et 7.0 ; aucune attente avant la première.
  - `test_retries_then_succeeds` : le handler renvoie 429, puis 503, puis 200 ; l'appel réussit ; `requests_made == 3`.
  - `test_gives_up_after_three_attempts` : le handler renvoie toujours 503 ; `TechEuError` est levée ; exactement 3 requêtes ; même attente pour `httpx.ConnectTimeout`.
  - `test_client_error_is_not_retried` : HTTP 400 avec `{"error": "unknown country: Suisse"}` lève `TechEuError` dont le message contient ce texte, après 1 seule requête.
  - `test_budget_exhausted` : avec `max_requests=2`, la troisième requête lève `BudgetExhaustedError` sans appeler le handler.
  - `test_fetch_changes_returns_added_and_removed` : sert `changes.json` modifié avec `removed: ["X1", {"id": "X2"}]` ; renvoie toutes les levées de `data` et `["X1", "X2"]`.
  - `test_fetch_changes_stops_on_repeated_cursor` : le handler renvoie toujours le même `nextCursor` non nul ; l'appel se termine après 2 requêtes.
- [ ] **Step 2 :** lancer `pytest tests/ingestion/test_techeu_client.py -q`. Attendu : échec à l'import.
- [ ] **Step 3 :** implémenter `TechEuClient`. Une méthode privée `_get(path, params)` porte le budget, l'attente et les essais ; les trois méthodes publiques l'utilisent. Attente entre essais : 5, puis 15 secondes, passées à `sleep`. On réessaie sur 429, 5xx et `httpx.TransportError` ; jamais sur les autres 4xx. La vérification des filtres compare `country`, `from` et `to` de `appliedFilters` aux valeurs envoyées.
- [ ] **Step 4 :** relancer. Attendu : tous passent.
- [ ] **Step 5 :** commit `feat: add Tech.eu client with pagination, throttling and retries`.

### Task 5 : stockage

**Files:**
- Create: `src/kaltstart/ingestion/store.py`, `src/kaltstart/ingestion/supabase_store.py`, `supabase/migrations/0001_ingestion.sql`
- Test: `tests/ingestion/test_store.py`

**Interfaces:**
- Produces: `class Store(Protocol)` avec :
  - `upsert_raw_rounds(raws: list[dict]) -> None` (clé : `raw["id"]`)
  - `upsert_companies(rows: list[CompanyRow]) -> None`
  - `upsert_rounds(rows: list[RoundRow]) -> None`
  - `delete_rounds(ids: list[str]) -> int` (supprime aussi dans `raw_rounds`)
  - `all_raw_rounds() -> list[dict]`
  - `company_ids_missing_details(limit: int) -> list[str]`
  - `set_company_details(company_id: str, details: CompanyDetails) -> None`
  - `last_successful_run_started_at() -> str | None` (horodatage ISO)
  - `record_run(run: dict) -> None`
  - `counts() -> dict[str, int]` avec les clés `raw_rounds`, `companies`, `rounds`
  - `all_rounds_with_company() -> list[dict]` : chaque élément est une `RoundRow` avec une clé `company` contenant sa `CompanyRow`
- `InMemoryStore` et `SupabaseStore(client: supabase.Client)` implémentent `Store`.
- `SupabaseStore.from_env() -> SupabaseStore` lit `SUPABASE_URL` et `SUPABASE_SERVICE_KEY`, et lève `RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")` si l'une manque.

- [ ] **Step 1 :** écrire les tests de `InMemoryStore` :
  - insérer deux fois la même levée ne crée qu'une ligne, la seconde version remplace la première ;
  - `upsert_companies` sur une entreprise dont la fiche est déjà remplie conserve `website`, `description`, `founded` et `details_fetched_at` ;
  - `company_ids_missing_details(limit=2)` renvoie au plus 2 identifiants, uniquement ceux sans `details_fetched_at` ; après `set_company_details`, l'entreprise n'y figure plus, même si `website` vaut `None` ;
  - `delete_rounds(["a", "inconnu"])` renvoie 1 et retire `a` de `rounds` et de `raw_rounds` ;
  - `all_rounds_with_company()` renvoie une entrée par levée, avec la ligne de son entreprise sous la clé `company` ;
  - `last_successful_run_started_at()` renvoie `None` sans exécution, ignore les exécutions `failed`, et renvoie le `started_at` le plus récent parmi les `success` ;
  - `SupabaseStore.from_env()` lève `RuntimeError` quand les variables sont absentes (avec `monkeypatch.delenv`).
- [ ] **Step 2 :** lancer `pytest tests/ingestion/test_store.py -q`. Attendu : échec à l'import.
- [ ] **Step 3 :** implémenter `Store` et `InMemoryStore` dans `store.py`.
- [ ] **Step 4 :** relancer. Attendu : tous passent sauf le test `from_env`.
- [ ] **Step 5 :** écrire `supabase/migrations/0001_ingestion.sql` :

```sql
create table raw_rounds (
  id text primary key,
  payload jsonb not null,
  fetched_at timestamptz not null default now()
);
create table companies (
  id text primary key,
  name text not null,
  country text not null,
  city_raw text,
  city text,
  region text,
  sectors text[] not null default '{}',
  techeu_url text not null,
  website text,
  description text,
  founded int,
  details_fetched_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table rounds (
  id text primary key,
  company_id text not null references companies(id),
  date date not null,
  stage text,
  raw_round_type text,
  amount_eur bigint,
  amount_native numeric,
  currency text,
  size_category text not null check (size_category in ('small','medium','large')),
  investors text[] not null default '{}',
  source_url text not null,
  source_domain text,
  confidence text,
  updated_at timestamptz not null default now()
);
create index rounds_date_idx on rounds (date desc);
create index rounds_company_idx on rounds (company_id);
create index companies_country_city_idx on companies (country, city);
create table sync_runs (
  id bigint generated always as identity primary key,
  command text not null,
  started_at timestamptz not null,
  finished_at timestamptz not null,
  status text not null check (status in ('success','failed')),
  rounds_upserted int not null default 0,
  rounds_removed int not null default 0,
  companies_upserted int not null default 0,
  details_fetched int not null default 0,
  requests_made int not null default 0,
  error text
);
alter table raw_rounds enable row level security;
alter table companies enable row level security;
alter table rounds enable row level security;
alter table sync_runs enable row level security;
```

  Aucune règle d'accès n'est créée : seule la clé de service, utilisée par les scripts, peut lire et écrire. Les règles de lecture pour les étudiants viendront en phase 4.
- [ ] **Step 6 :** implémenter `SupabaseStore` avec `client.table(...).upsert(...)`, par lots de 500 lignes. `upsert_companies` n'envoie que les colonnes de `CompanyRow` plus `updated_at`, pour ne pas écraser la fiche.
- [ ] **Step 7 :** relancer `pytest tests/ingestion/test_store.py -q`. Attendu : tous passent.
- [ ] **Step 8 :** commit `feat: add store interface, in-memory store, Supabase store and schema`.

`SupabaseStore` n'a pas de test automatique au-delà de `from_env` : il est vérifié contre la vraie base en tâche 8.

### Task 6 : pipeline

**Files:**
- Create: `src/kaltstart/ingestion/pipeline.py`
- Test: `tests/ingestion/test_pipeline.py`

**Interfaces:**
- Consumes: `TechEuClient`, `Store`, `transform_round`, `transform_company_details`.
- Produces:
  - `COUNTRIES = ("Switzerland", "Germany", "Austria")`
  - `backfill(client, store, date_from: str, date_to: str) -> dict`
  - `sync_changes(client, store) -> dict`
  - `fetch_company_details(client, store, limit: int = 1000) -> dict`
  - `reclean(store) -> dict`
  - Chaque fonction renvoie le dictionnaire d'exécution, de même forme que les colonnes de `sync_runs` (sans `id`), et l'enregistre avec `store.record_run`, y compris en cas d'échec ; dans ce cas `status` vaut `"failed"`, `error` contient le message, et l'exception est relancée.

Les tests utilisent `InMemoryStore` et un faux client (classe de test avec les trois mêmes méthodes et `requests_made`).

- [ ] **Step 1 :** écrire les tests :
  - `test_backfill_stores_raw_companies_and_rounds` : 3 levées pour 2 entreprises donnent `counts() == {"raw_rounds": 3, "companies": 2, "rounds": 3}` ; `iter_rounds` a été appelée une fois par pays de `COUNTRIES` ; l'exécution est `success` avec `rounds_upserted == 3`.
  - `test_backfill_twice_adds_nothing` : deux appels identiques laissent les mêmes `counts()`.
  - `test_company_city_comes_from_latest_round` : deux levées de la même entreprise, ville `"Zurich "` le 2026-01-10 et `"Vaud"` le 2026-06-01, dans les deux ordres d'arrivée : la ligne `companies` a `city is None` et `region == "Vaud"`.
  - `test_sync_changes_keeps_only_our_countries` : `fetch_changes` renvoie une levée suisse, une britannique, et `["old-id"]` à supprimer ; seule la suisse est stockée, `rounds_removed` vaut le nombre réellement supprimé.
  - `test_sync_changes_since_is_last_success_minus_one_day` : avec une dernière exécution réussie à `2026-11-10T03:00:00+00:00`, `fetch_changes` reçoit `"2026-11-09T03:00:00+00:00"`.
  - `test_sync_changes_without_previous_run_fails_clearly` : lève `RuntimeError("no successful run found: run backfill first")`.
  - `test_failure_is_recorded_and_reraised` : `iter_rounds` lève `TechEuError` au deuxième pays ; l'exception remonte ; une exécution `failed` est enregistrée ; `last_successful_run_started_at()` reste `None`.
  - `test_fetch_company_details_fills_and_resumes` : 3 entreprises sans fiche ; le faux client lève `BudgetExhaustedError` au deuxième appel ; l'exécution est `success` avec `details_fetched == 1` ; un second appel traite les 2 restantes.
  - `test_reclean_reapplies_rules_without_client` : on stocke une levée brute, on modifie à la main sa ligne `rounds` (`size_category="large"`), `reclean(store)` la remet à `"small"`.
- [ ] **Step 2 :** lancer `pytest tests/ingestion/test_pipeline.py -q`. Attendu : échec à l'import.
- [ ] **Step 3 :** implémenter les quatre fonctions. Une fonction privée `_store_rounds(store, raws) -> tuple[int, int]` est partagée par `backfill`, `sync_changes` et `reclean` : elle écrit les levées brutes, puis les entreprises (une ligne par entreprise, tirée de sa levée la plus récente du lot), puis les levées. Dans `fetch_company_details`, `BudgetExhaustedError` arrête la boucle sans faire échouer l'exécution ; toute autre `TechEuError` sur une entreprise est comptée et on passe à la suivante.
- [ ] **Step 4 :** relancer. Attendu : tous passent.
- [ ] **Step 5 :** commit `feat: add backfill, incremental sync, details fetch and reclean pipelines`.

### Task 7 : ligne de commande et exécution de nuit

**Files:**
- Create: `src/kaltstart/ingestion/__main__.py`, `.github/workflows/nightly.yml`
- Test: `tests/ingestion/test_cli.py`

**Interfaces:**
- Consumes: tout ce qui précède.
- Produces: `main(argv: list[str], *, client=None, store=None) -> int`, et les commandes :
  - `backfill [--months 12]` : `backfill` sur la période, puis `fetch_company_details`.
  - `sync` : `sync_changes`, puis `fetch_company_details`.
  - `reclean` : `reclean`.
  - `report` : affiche, sans appeler l'API, les `counts()`, le nombre de levées par pays, le tableau stade × catégorie de taille, et pour les levées dont le stade est connu la médiane de `amount_eur` par stade.
  - `cities` : affiche chaque valeur distincte de `city` avec son pays et son nombre d'entreprises, triée par pays puis par nombre décroissant, puis la liste des `city_raw` différentes de `city`.

- [ ] **Step 1 :** écrire les tests avec `InMemoryStore` et un faux client injectés dans `main` :
  - `main(["backfill", "--months", "12"])` renvoie 0, le store contient les levées, la sortie (`capsys`) contient `rounds_upserted` ;
  - `main(["sync"])` sans exécution précédente renvoie 1 et affiche `run backfill first` sur la sortie d'erreur ;
  - `main(["report"])` affiche les trois compteurs et une ligne par catégorie de taille ;
  - `main(["cities"])` affiche `Zurich` avec son nombre ;
  - `main([])` renvoie 2.
- [ ] **Step 2 :** lancer `pytest tests/ingestion/test_cli.py -q`. Attendu : échec à l'import.
- [ ] **Step 3 :** implémenter `main` avec `argparse`. Sans `client` ni `store` fournis, il construit `TechEuClient(httpx.Client(base_url=BASE_URL, timeout=30))` et `SupabaseStore.from_env()`. `report` et `cities` lisent les données avec `store.all_rounds_with_company()`.
- [ ] **Step 4 :** relancer toute la suite : `pytest -q`. Attendu : tout passe.
- [ ] **Step 5 :** créer `.github/workflows/nightly.yml` : déclencheurs `schedule` (`cron: "17 2 * * *"`) et `workflow_dispatch` avec une entrée `command` (choix `sync`, `backfill`, `reclean` ; défaut `sync`) ; Python 3.12 ; `pip install -e .` ; `python -m kaltstart.ingestion <command>`, soit `sync` pour le déclenchement planifié, avec `SUPABASE_URL` et `SUPABASE_SERVICE_KEY` tirés des secrets du repo ; `timeout-minutes: 180`.
- [ ] **Step 6 :** commit `feat: add ingestion CLI and nightly workflow`.

### Task 8 : mise en service et vérification sur les vraies données

Cette tâche demande des actions du porteur du projet : elles sont marquées **[Camil]**.

- [ ] **Step 1 [Camil] :** créer un repo GitHub public nommé `kaltstart`, puis y pousser le code (`git remote add origin ...`, `git push -u origin main`). Vérifier que le workflow `tests` est vert.
- [ ] **Step 2 [Camil] :** créer un projet Supabase gratuit, région Europe. Dans l'éditeur SQL, exécuter le contenu de `supabase/migrations/0001_ingestion.sql`.
- [ ] **Step 3 [Camil] :** copier l'URL du projet et la clé `service_role` dans les secrets du repo GitHub, sous les noms `SUPABASE_URL` et `SUPABASE_SERVICE_KEY`. Ne jamais les coller dans le chat ni dans un fichier du repo.
- [ ] **Step 4 :** lancer le premier chargement depuis l'onglet Actions (workflow `nightly`, lancé à la main avec `command=backfill`). Durée attendue : environ 1 h 30, à cause de l'attente de 7 secondes entre les fiches d'entreprise.
- [ ] **Step 5 :** vérifier avec `report` : `rounds` vaut environ 830 (260 pour la Suisse, 503 pour l'Allemagne, 63 pour l'Autriche, à quelques unités près selon la date) ; aucune ligne `rounds` sans `size_category`.
- [ ] **Step 6 :** relancer `sync` deux fois de suite. Attendu : la seconde exécution a `rounds_upserted` égal au nombre de levées ajoutées par Tech.eu dans les dernières 24 heures (quelques unités au plus) et `counts()` ne change pas entre les deux, hors nouveautés réelles.
- [ ] **Step 7 :** calibrer les bornes de taille. Lire dans `report` la médiane de `amount_eur` pour `Seed`, `Series A` et `Series B`. Si la médiane `Series A` sort de l'intervalle 3 à 15 millions d'euros, ou si la médiane `Seed` dépasse 3 millions, proposer de nouvelles bornes au porteur du projet, modifier `SMALL_MAX_EUR` et `MEDIUM_MAX_EUR` et les tests correspondants, puis lancer `reclean`. Noter le résultat dans `DECISIONS.md`, que les bornes changent ou non.
- [ ] **Step 8 :** nettoyer les villes. Lancer `cities`, soumettre au porteur du projet les valeurs suspectes (régions, variantes d'orthographe), compléter `city_aliases.csv`, lancer `reclean`, relancer `cities` pour confirmer.
- [ ] **Step 9 :** mettre à jour `CHANGELOG.md` (entrée `Phase 1` avec les chiffres réels), `README.md` (statut de la phase 1, nombre de levées et d'entreprises, part des entreprises avec un site web) et `CLAUDE.md` (commandes de la ligne de commande). Commit `docs: record phase 1 results`.
- [ ] **Step 10 :** demander une revue de code de la phase avec le skill `superpowers:requesting-code-review`, puis traiter les remarques.
