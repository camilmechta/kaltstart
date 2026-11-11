# Kaltstart : spec de design

Date : 2026-11-11
Statut : en attente de relecture
Nom du projet : Kaltstart (le dossier local s'appelle encore `hsg-spontan`)

## 1. Résumé

Kaltstart est une web app réservée aux étudiants de l'Université de Saint-Gall
(HSG), sur invitation. Elle
repère les startups et scale-ups tech de Suisse, d'Allemagne et d'Autriche qui
ont levé des fonds dans les 12 derniers mois, trouve à qui écrire, et prépare
une candidature spontanée qui s'ouvre sur la levée. L'étudiant relit et envoie
lui-même depuis sa boîte mail. L'app n'envoie jamais rien.

Le produit ne liste pas d'offres d'emploi. Sa différence est la candidature
spontanée bien ciblée, au moment où l'entreprise vient de recevoir de l'argent
pour recruter.

## 2. Objectifs et critères de succès

Le projet est d'abord un portfolio de product builder. Il devient un vrai
produit seulement si le test final atteint des seuils fixés à l'avance.

| Critère | Seuil | Mesuré en |
|---|---|---|
| Contacts utilisables trouvés par le scraper | 70 % des entreprises | Phase 2 |
| Nom d'un fondateur trouvé | 40 % des entreprises | Phase 2 |
| Taux de réponse humaine | 10 % des mails envoyés | Phase 5 |
| Taux de réponse positive | 3 % des mails envoyés | Phase 5 |

Définitions :

- **Contact utilisable** : au moins une adresse mail publiée sur le site de
  l'entreprise, quel que soit son type.
- **Réponse humaine** : toute réponse écrite par une personne, y compris un
  refus. Les accusés de réception automatiques ne comptent pas.
- **Réponse positive** : proposition d'appel ou d'entretien.
- **Mail envoyé** : mail que l'étudiant a marqué « envoyé ». Les mails
  « présumés envoyés » (voir 7.4) sont exclus du calcul des taux.

Volume visé pour le test : 20 étudiants, environ 10 mails chacun, soit environ
200 mails. Les seuils correspondent à 20 réponses humaines dont 6 positives.

Si un seuil de la phase 2 n'est pas atteint, on s'arrête et on choisit un plan
B avant de continuer : saisie manuelle des contacts manquants pour le test,
lecture des pages en JavaScript avec un vrai navigateur, ou utilisation du
formulaire de contact.

## 3. Hors périmètre

- Envoi automatique de mails.
- Lecture de la boîte mail des étudiants.
- Stockage de CV ou de pièces jointes.
- Scraping de LinkedIn.
- Adresses mail devinées à partir d'un nom.
- Appel à une API d'IA à l'exécution.
- Autres pays européens. Le périmètre géographique est la Suisse, l'Allemagne
  et l'Autriche ; d'autres pays pourront être ajoutés plus tard.
- Demandes autres que stage ou temps partiel (premier emploi, simple appel).
- Offres d'emploi.

## 4. Contraintes

- Tout le produit est en Python, sans IA à l'exécution : règles, extraction de
  texte et templates.
- Source des levées : API Tech.eu Funding Explorer, licence CC BY 4.0, mention
  « Tech.eu Funding Explorer » obligatoire dans l'app et le README.
- Quotas Tech.eu : 120 requêtes par minute, 600 par heure, 2000 par jour.
- Scraping : respect de robots.txt, rythme limité, pages publiques seulement.
- Données personnelles : on stocke le minimum, chaque contact a une source.

## 5. Architecture

Cinq pièces indépendantes. Elles ne communiquent que par la base de données,
sauf le serveur qui appelle le générateur directement.

```
Tech.eu API ──> [1. Ingestion] ──┐
                                 ▼
Sites web ───> [2. Contacts] ──> Supabase <──> [5. Front]
                                 ▲                 │
               [3. Générateur] ─ [4. Serveur] <────┘
```

| Pièce | Rôle | Quand elle tourne | Dépend de |
|---|---|---|---|
| 1. Ingestion | Récupère les nouvelles levées, nettoie, écrit en base | Chaque nuit, GitHub Actions | API Tech.eu, Supabase |
| 2. Contacts | Visite les sites des entreprises sans contact, extrait adresses et noms | Chaque nuit, après l'ingestion | Sites web, Supabase |
| 3. Générateur | Fonction pure : reçoit profil, entreprise, levée, contact ; renvoie objet et texte | Appelée par le serveur | Rien d'extérieur |
| 4. Serveur | Vérifie les règles de réservation, appelle le générateur, enregistre le mail | À chaque clic sur « Générer » | Supabase, pièce 3 |
| 5. Front | Inscription, filtres, liste, fiche entreprise, suivi | Dans le navigateur | Supabase, pièce 4 |

Principes :

1. Le nettoyage est séparé du téléchargement. La réponse brute de Tech.eu est
   conservée ; on peut rejouer le nettoyage sans rappeler l'API.
2. Le générateur ne touche ni à la base ni au réseau. Mêmes entrées, même mail.
3. Les règles métier sont vérifiées par le serveur, jamais par le front seul.

Technologies : Python, Supabase (Postgres), Jinja2 pour les templates, FastAPI
pour le serveur, pytest pour les tests, GitHub Actions pour le travail de nuit
et pour lancer les tests à chaque commit. Le choix de l'outil pour le front
(Lovable ou front écrit à la main) est reporté au début de la phase 4.

Structure du repo :

```
src/ingestion/    src/contacts/    src/mailgen/    src/api/
tests/            docs/            .github/workflows/
PRD.md  DECISIONS.md  CHANGELOG.md  CLAUDE.md  README.md
```

## 6. Données

Sept tables.

### 6.1 Données sur les entreprises (écrites par les scripts de nuit)

| Table | Une ligne représente | Colonnes principales |
|---|---|---|
| `raw_rounds` | Une levée telle que Tech.eu l'a renvoyée | identifiant Tech.eu, réponse brute, date de récupération |
| `companies` | Une entreprise | identifiant Tech.eu, nom, site web, description, pays, ville nettoyée, canton ou région, secteurs |
| `rounds` | Une levée nettoyée | entreprise, montant en euros, stade d'origine, catégorie de taille, date, investisseurs, lien source |
| `contacts` | Une adresse ou un nom trouvé sur le site | entreprise, type (nominatif, carrière, générique), adresse, nom et rôle du fondateur, page source, confiance, date de vérification |

La table `companies` porte aussi l'état du scraping de chaque entreprise :
jamais visité, réussi, ou échec avec sa raison, le nombre d'essais et la date
du prochain essai.

### 6.2 Données sur les étudiants (écrites par le front et le serveur)

| Table | Une ligne représente | Colonnes principales |
|---|---|---|
| `profiles` | Un étudiant | adresse mail, prénom et nom, filière, langues, rôle visé, type de demande, disponibilités (date de début, durée ou taux), secteurs et lieux souhaités |
| `experiences` | Un exemple concret de l'étudiant (deux au maximum) | étudiant, texte en anglais, texte en allemand, ordre |
| `emails` | Un mail généré | étudiant, entreprise, levée, contact, style de template utilisé, objet, texte, langue, statut, date de chaque changement de statut |

### 6.3 Catégorie de taille

Tech.eu classe environ la moitié des levées en stade « Other ». On calcule donc
une catégorie à trois valeurs, stockée à côté du stade d'origine :

| Catégorie | Si le stade est connu | Sinon, selon le montant |
|---|---|---|
| Petite | Pre-seed, Seed | Moins de 3 millions d'euros |
| Moyenne | Series A | De 3 à 15 millions d'euros |
| Grande | Series B et au-delà | Plus de 15 millions d'euros |

Les bornes 3 et 15 millions sont des valeurs de départ. Elles sont recalées en
phase 1 sur les levées dont on connaît à la fois le stade et le montant, et la
valeur retenue est notée dans DECISIONS.md. Une levée sans stade connu ni
montant est classée « petite » par défaut et son mail utilise une ouverture
sans montant.

### 6.4 Statuts d'un mail

```
généré ──> copié ──> envoyé ──> réponse humaine ──> réponse positive
   └──────────┴──> abandonné
   └──────────┴──> présumé envoyé   (automatique après 7 jours)
```

La table `emails` suffit à calculer le plafond par entreprise, la limite de
mails en attente et les taux de réponse. Il n'y a pas de table de réservations.

### 6.5 Accès et protection des données

- Row Level Security de Supabase : un étudiant ne lit et ne modifie que son
  profil, ses exemples et ses mails.
- Pour le plafond, il voit un nombre de places prises par entreprise, jamais
  l'identité des autres étudiants.
- Inscription avec n'importe quelle adresse mail, à condition de saisir un
  code d'invitation. Le code est unique pour tout le test, distribué par le
  porteur du projet aux étudiants HSG, et vérifié par le serveur. Il n'y a pas
  de contrôle du domaine de l'adresse.
- Un étudiant peut supprimer son compte et toutes ses données.
- Les contacts d'entreprise viennent uniquement de pages publiques et gardent
  leur page source.

## 7. Règles métier

### 7.1 Ingestion

- Premier lancement : 12 mois de levées pour la Suisse, l'Allemagne et
  l'Autriche, par pages de 100, puis une requête par entreprise pour sa fiche.
  Environ 830 levées. Le rythme est limité pour rester sous 600 requêtes par
  heure.
- Chaque nuit : on demande les levées depuis la date de la plus récente en
  base, moins 7 jours de marge. Une levée déjà connue est mise à jour, jamais
  dupliquée. La fiche d'une entreprise déjà connue n'est pas redemandée.
- À chaque appel, on compare `appliedFilters` aux filtres envoyés. S'ils
  diffèrent, le script s'arrête avec une erreur et n'écrit rien.
- Nettoyage des villes : suppression des espaces en trop, puis table de
  correspondance écrite à la main (variantes d'orthographe ramenées à un seul
  nom, cantons et régions sortis du champ ville). Toute valeur inconnue est
  listée dans un rapport, pas corrigée en silence.
- Les montants sont convertis en euros si Tech.eu les fournit dans une autre
  devise ; le montant et la devise d'origine sont conservés.

### 7.2 Contacts

- Pages visitées : accueil, `/careers`, `/jobs`, `/about`, `/team`,
  `/impressum`, `/imprint`, `/contact`. Huit pages au plus par entreprise.
- Politesse : lecture de robots.txt avant toute visite, deux secondes au moins
  entre deux requêtes vers le même site, un nom d'outil qui identifie le
  projet. Jamais LinkedIn.
- Adresses : extraites du texte et des liens, y compris les formes déguisées
  courantes (« hello [at] startup.ch »). On ne garde que celles du domaine de
  l'entreprise.
- Noms de fondateurs : repérés par des mots de rôle (Founder, Co-Founder, CEO,
  Gründer, Mitgründer, Geschäftsführer) proches d'un nom, sur les pages équipe
  et Impressum.
- Types d'adresse : nominative (contient le prénom ou le nom d'un fondateur
  trouvé), carrière (careers@, jobs@, talent@, hr@), générique (hello@, info@,
  contact@ et équivalents).

Choix du contact proposé à l'étudiant :

| Catégorie de taille | 1er choix | 2e choix | 3e choix |
|---|---|---|---|
| Petite | Adresse nominative publiée d'un fondateur | Générique ou carrière, mail adressé au fondateur par son prénom | Générique ou carrière seule |
| Moyenne, grande | Adresse carrière | Générique | Aucun |

Niveau de confiance :

| Niveau | Cas |
|---|---|
| Élevé | Adresse nominative publiée |
| Moyen | Adresse carrière, ou générique avec un nom de fondateur trouvé |
| Faible | Générique seule |

Une entreprise sans aucune adresse est masquée de la liste étudiante.

### 7.3 Génération du mail

- Langue : allemand si l'étudiant le parle et que l'entreprise est en
  Allemagne, en Autriche ou dans un canton germanophone ; anglais sinon.
  L'étudiant peut basculer. La première version ne propose que l'anglais et
  l'allemand.
- Structure : un mélange de blocs fixes et de parties qui varient selon le
  style de template. Les blocs de départ sont : ouverture sur la levée, phrase
  sur le secteur, exemple concret de l'étudiant, paragraphe sur le rôle,
  demande, signature. La répartition exacte entre ce qui est commun à tous les
  styles et ce qui change d'un style à l'autre n'est pas encore décidée : elle
  le sera en phase 3, avec les modèles fournis.
- Ouverture : dépend de la catégorie de taille, avec montant, date et
  investisseur principal. Trois formulations par catégorie. Le choix est
  déterminé par la paire étudiant-entreprise : régénérer donne le même texte,
  deux étudiants reçoivent des tournures différentes.
- Données manquantes : chaque ouverture a une version sans montant et une
  version sans investisseur. Aucune phrase ne peut contenir un trou. Si le
  secteur de l'entreprise n'a pas de phrase dédiée, la phrase de secteur est
  omise.
- Exemple concret : le premier par défaut, l'étudiant peut choisir le second.
  Chaque exemple fait 200 caractères au plus.
- Paragraphe de rôle : un par rôle (product, growth, data, ops, BD).
- Demande : stage (date de début, durée) ou temps partiel (date de début,
  taux d'occupation).
- Signature : prénom, nom, filière HSG, disponibilités.
- Longueur : 150 mots au plus pour le corps, 60 caractères au plus pour l'objet.
- Styles de template : l'étudiant pourra choisir entre plusieurs styles de
  mail (trois au plus), chacun en anglais et en allemand. Les styles seront
  définis en phase 3 à partir des modèles fournis par le porteur du projet,
  dont on reprend la structure et non le texte. Le style utilisé est
  enregistré avec chaque mail, pour comparer les taux de réponse par style
  dans le rapport de la phase 5. Les règles ci-dessus (données manquantes,
  longueurs, variantes) s'appliquent à tous les styles.
- Si une donnée obligatoire manque (prénom, filière, date de début, adresse du
  contact), le générateur refuse avec un message qui nomme la donnée.

### 7.4 Réservation et suivi

Générer un mail réserve une place. La génération est refusée si :

- l'entreprise a déjà 3 mails non abandonnés créés dans les 30 derniers jours,
  tous étudiants confondus ;
- l'étudiant a déjà 5 mails au statut généré ou copié ;
- l'étudiant a déjà un mail non abandonné pour cette entreprise.

Le refus indique la raison et, pour le plafond d'entreprise, la date à laquelle
une place se libère.

Suivi :

- Le front propose trois boutons « Copier » : adresse, objet, texte. Copier le
  texte fait passer le mail au statut copié.
- L'étudiant marque lui-même envoyé, réponse humaine, réponse positive ou
  abandonné.
- 72 heures après la génération sans statut envoyé ou abandonné, l'app affiche
  un rappel.
- 7 jours après la génération, un mail encore au statut généré ou copié passe à
  présumé envoyé. Il compte pour le plafond de l'entreprise, ne compte plus
  dans la limite de 5, et il est exclu du calcul des taux de réponse.

## 8. Gestion des erreurs

| Situation | Réaction |
|---|---|
| Tech.eu ne répond pas ou quota atteint | Trois essais espacés, puis arrêt propre. La marge de 7 jours rattrape le retard la nuit suivante. |
| `appliedFilters` ne correspond pas | Arrêt immédiat, rien n'est écrit. |
| Site lent, en erreur ou interdit par robots.txt | Raison notée, on passe au suivant. Nouvel essai 7 jours plus tard, trois fois au plus. |
| Entreprise sans contact | Masquée de la liste étudiante. |
| Donnée obligatoire manquante pour un mail | Refus avec un message clair. |
| Échec du script de nuit | Notification par mail de GitHub Actions. |

Chaque exécution de nuit écrit un bilan : levées ajoutées et mises à jour,
sites visités, contacts trouvés, erreurs par type.

## 9. Tests

Développement piloté par les tests : le test est écrit avant le code. Aucun
test ne fait d'appel réseau réel.

| Pièce | Ce qui est testé | Moyen |
|---|---|---|
| Ingestion | Pagination, absence de doublon, arrêt si un filtre est ignoré, nettoyage des villes, catégorie de taille | Réponses Tech.eu enregistrées dans des fichiers |
| Contacts | Extraction des adresses et des noms, respect de robots.txt, choix du contact, confiance | Pages HTML sauvegardées |
| Générateur | Aucune variable vide, aucun montant manquant affiché, longueurs, anglais et allemand | Toutes les combinaisons taille × rôle × langue × demande × données manquantes (240 cas par style de template) |
| Serveur | Les trois refus de 7.4, le passage à présumé envoyé | Base de test avec données fictives |

Mesure de la phase 2 : 20 entreprises suisses tirées au hasard parmi les levées
en base. Résultat sous forme de tableau par site (adresse générique, nom de
fondateur, adresse nominative, cause de l'échec). Chaque ligne est vérifiée à
la main pour compter aussi les erreurs du scraper.

## 10. Phases

| Phase | Contenu | Terminée quand |
|---|---|---|
| 0. Cadrage | Spec, PRD.md, repo, CLAUDE.md, structure | La spec est validée |
| 1. Ingestion | Tech.eu vers Supabase pour les trois pays, nettoyage, mise à jour incrémentale | Les levées sont en base, propres ; un second lancement n'ajoute que les nouveautés |
| 2. Contacts | Scraper testé sur 20 sites suisses | Les taux sont mesurés et comparés aux seuils de 70 % et 40 % |
| 3. Mails | Générateur et templates en anglais et en allemand | Tous les cas de test passent, pour chaque style |
| 4. Front | Serveur FastAPI, inscription sur code d'invitation, filtres, liste, fiche, suivi | Un étudiant va de l'inscription au mail copié sans aide |
| 5. Test | 20 étudiants HSG, environ 200 mails | Rapport comparant les taux aux seuils de 10 % et 3 % |

Chaque phase a son propre plan d'implémentation et se termine par une revue de
code. La phase 1 est planifiée en premier.

## 11. Journal des décisions

| # | Décision | Raison | Options écartées |
|---|---|---|---|
| D1 | Portfolio d'abord, suite conditionnée aux seuils | Un seuil fixé avant le test montre une démarche produit | Portfolio seul ; vrai produit dès le départ |
| D2 | Seuils de 10 % de réponses humaines et 3 % de positives | Au-dessus d'un mail générique, volume suffisant pour conclure | 5 % ; 15 % |
| D3 | Demande limitée à stage ou temps partiel | Demande précise, test comparable | Stage seul ; tout type de demande |
| D4 | Un ou deux exemples concrets saisis par l'étudiant | Seule partie qui distingue un étudiant d'un autre, sans IA | Champs structurés seuls ; un exemple par rôle |
| D5 | 3 mails par entreprise sur 30 jours, comptés à la génération | Protège le fondateur ; l'app voit forcément la génération | Aucune limite ; compteur sans blocage ; comptage à l'envoi déclaré |
| D6 | Boutons « Copier », limite de 5 mails en attente | Correspond à l'usage réel ; pousse à tenir le suivi à jour | Bouton `mailto:` ; adresse en copie cachée |
| D7 | Adresse nominative seulement si publiée | Chaque adresse a une source vérifiable ; pas de rebond | Générique toujours ; adresse devinée |
| D8 | Seuils du scraper à 70 % et 40 % | Point de contrôle avant d'investir dans les phases 3 à 5 | 50 % ; 85 % |
| D9 | FastAPI pour la génération, GitHub Actions pour la nuit | Le Python doit tourner au clic ; le travail de nuit n'a pas besoin d'un serveur | File d'attente en base ; templates réécrits en JavaScript |
| D10 | Mails présumés envoyés exclus des taux | On ne sait pas s'ils sont partis ; ils fausseraient la métrique | Les compter comme envoyés |
| D11 | Inscription sur code d'invitation, sans contrôle du domaine | Plus simple, pas de dépendance aux boîtes mail universitaires, contrôle de qui entre | Adresse HSG obligatoire ; inscription libre |
| D12 | Plusieurs styles de template, style enregistré par mail | L'étudiant choisit le ton qui lui convient ; le test compare les styles | Un seul template |
| D13 | Documents publics du repo en anglais (README, PRD, DECISIONS, CHANGELOG, CLAUDE.md, code et commits) | Lisible par les recruteurs tech européens | Français |

## 12. Questions ouvertes

Elles ne bloquent pas la phase 1.

- Contenu exact des styles de template (à définir en phase 3, à partir des
  modèles fournis).
- Répartition entre structure fixe et styles de template (phase 3).
- Outil du front : Lovable ou front écrit à la main (à trancher en phase 4).
- Hébergeur du serveur FastAPI (à trancher en phase 4).
