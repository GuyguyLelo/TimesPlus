# Gestion des heures supplémentaires

Application web de gestion des heures supplémentaires pour un service d'administration publique en République démocratique du Congo. Le rendu est côté serveur (Django Templates, Bootstrap 5, JavaScript vanilla). Les durées, les types d'heures, les coefficients et les montants estimés viennent de règles saisies dans l'application. Aucun barème juridique n'est codé en dur.

Les coefficients, le taux horaire de démonstration (5 000 CDF) et les jours fériés chargés par `seed_demo` sont des **exemples**. Ils se modifient dans l'interface ou dans l'administration Django.

## 1. Présentation

Un agent déclare une période. Le serveur calcule la durée en minutes, classe chaque minute selon les règles actives (jour, nuit, week-end, férié), applique le coefficient de la règle retenue et estime un montant :

```text
durée travaillée → classification → règle applicable → coefficient → montant estimé
```

Le montant d'un segment est `heures × taux horaire de l'agent × coefficient de la règle`. La ventilation et la règle utilisée sont conservées sur la déclaration.

Circuit par défaut (modifiable) :

```text
BROUILLON → EN_VALIDATION (chef de service) → VALIDATION RH → APPROUVE
```

Un rejet exige un motif. Un agent ne peut pas approuver sa propre déclaration. Un chef ne traite que son service et ses services descendants, sauf permission `validate_all_overtime`.

## 2. Architecture

```text
config/                 réglages, URLs, WSGI
apps/accounts/          connexion, profils, groupes, permissions
apps/agents/            agents
apps/services/          services (hiérarchie)
apps/overtime/          horaires, fériés, types, règles, déclarations, calcul
apps/workflow/          circuit et décisions
apps/reports/           PDF (ReportLab) et Excel (openpyxl)
apps/settings_app/      paramètres du site
apps/audit/             journal non supprimable depuis l'interface
apps/dashboard/         tableau de bord
templates/ static/      interface
docker/                 Nginx et script d'entrée
```

Le calcul est dans `apps/overtime/services/calculation.py`. Le workflow est dans `apps/workflow/services.py`. Les PDF utilisent ReportLab (polices Arial sous Windows, DejaVu dans l'image Docker) plutôt que WeasyPrint, plus simple à installer sur Windows et dans l'image Python.

## 3. Prérequis

- Python 3.12 ou plus récent
- PostgreSQL 16, ou Docker avec Docker Compose
- Pour les PDF dans Docker : les polices DejaVu sont installées par le `Dockerfile`

## 4. Installation locale

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Renseigner au minimum `SECRET_KEY`, `DEBUG=True` pour le développement, et les accès PostgreSQL. Le fichier `.env` ne doit pas être versionné.

En local, l'application utilise PostgreSQL sur `127.0.0.1:5432`, base `HEURE_SUP`, utilisateur `postgres`. Créer cette base si elle n'existe pas, puis lancer les migrations.

Docker Compose reste disponible pour un PostgreSQL isolé. Dans ce cas, le conteneur web doit utiliser `POSTGRES_HOST=db`. Le port publié sur l'hôte est **15432**.

## 5. Variables d'environnement

Voir `.env.example`.

| Variable | Rôle |
| --- | --- |
| `SECRET_KEY` | Clé Django. Obligatoire si `DEBUG=False`. Les valeurs `change-me` sont refusées en production. |
| `DEBUG` | `True` seulement en développement. |
| `ALLOWED_HOSTS` | Hôtes autorisés, séparés par des virgules. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | Base de données. Les alias `DB_*` sont acceptés. |
| `CSRF_TRUSTED_ORIGINS` | Origines du formulaire (inclure le port public, par exemple `http://localhost:8080`). |
| `USE_HTTPS` | Laisser `False` tant que le certificat TLS n'est pas en place. |
| `SEED_DEMO_PASSWORD` | Si renseigné, remplace les mots de passe individuels de `seed_demo`. |

Enregistrer `.env` en fins de ligne LF. Un fichier CRLF peut ajouter un caractère invisible au mot de passe lu par le conteneur PostgreSQL.

## 6. Migration

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

À chaque migration, les groupes et leurs permissions sont réappliqués depuis `apps/accounts/roles.py` dès que toutes les permissions existent. Ce fichier est la source de vérité des rôles.

## 7. Création du superuser

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Le compte `admin` créé par `seed_demo` est déjà superutilisateur. Il est réservé à la démonstration.

## 8. Données de démonstration

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo
```

La commande refuse de s'exécuter si `DEBUG=False`, sauf avec `--force`. Elle ne remplace pas le mot de passe d'un compte déjà existant.

Comptes créés la première fois (à changer avant toute mise en production) :

| Identifiant | Mot de passe | Rôle |
| --- | --- | --- |
| `admin` | `Admin@123` | Super administrateur |
| `rh` | `Gestion-Heures-Rh-2026!` | Administration RH |
| `chef` | `Gestion-Heures-Chef-2026!` | Chef de service (DSI) |
| `agent` | `Gestion-Heures-Agent-2026!` | Agent (DSI) |

Groupes : `SUPER_ADMIN`, `ADMIN_RH`, `CHEF_SERVICE`, `VALIDATEUR`, `AGENT`, `AUDITEUR`, `CONSULTATION`.

## 9. Lancement

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

- Connexion : http://127.0.0.1:8000/login/
- Après connexion : http://127.0.0.1:8000/dashboard/
- Administration Django : http://127.0.0.1:8000/admin/

## 10. Docker

```powershell
docker compose build
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_demo
```

- Application : http://localhost:8080/
- PostgreSQL publié sur l'hôte : port **15432**
- Volume persistant : `postgres_data`
- Nginx sert `/static/` et proxyfie l'application. Les pièces jointes ne sont pas publiées : le téléchargement passe par Django.

## 11. Tests

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

Les tests couvrent la durée (180 et 210 minutes), les plages invalides, le chevauchement, le workflow, l'interdiction d'approuver sa propre demande ou une demande d'un autre service, les exports PDF et Excel, et le parcours déclaration → chef → RH → PDF → Excel.

## 12. Génération PDF

Menu **Rapports**. Les modèles sont : individuel, service, mensuel, administratif. L'en-tête contient le nom de l'administration, le service, la période, la date de génération, l'utilisateur et un numéro `HS-année-séquence`.

## 13. Export Excel

Le classeur comporte trois feuilles : **Synthèse**, **Détails**, **Par service**. Filtres automatiques, en-têtes figés, totaux, durées au format `[h]:mm`.

## 14. Sauvegarde

```bash
./backup_db.sh
```

Le script exécute `pg_dump` dans le conteneur `db` et écrit `backups/gestion_heures_AAAAMMJJ_HHMMSS.sql`.

## 15. Restauration

```bash
./restore_db.sh backups/gestion_heures_AAAAMMJJ_HHMMSS.sql
```

La restauration écrase les données du conteneur `db`. Arrêter les écritures applicatives avant de la lancer.

## 16. Déploiement production

1. `DEBUG=False` et une `SECRET_KEY` longue et aléatoire.
2. `ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS` limités au nom réel du site.
3. Mots de passe des comptes de démonstration changés, ou `seed_demo` non exécuté.
4. PostgreSQL non exposé sur Internet. Retirer la publication `15432:5432` si la base ne doit être jointe que par le réseau Docker.
5. HTTPS terminé (certificat et proxy) **avant** `USE_HTTPS=True`. Ce drapeau active les cookies sécurisés, la redirection SSL et HSTS. Le laisser à `False` tant que TLS n'est pas en place.
6. `python manage.py collectstatic` (déjà lancé par l'entrée Docker).
7. Sauvegardes planifiées avec `backup_db.sh`.
8. Journal d'audit consultable par les profils autorisés. Il n'est pas supprimable depuis l'interface ni depuis l'administration Django.

Commandes de contrôle :

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
```
