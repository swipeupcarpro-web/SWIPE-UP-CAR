# SWIPEUPCAR — Marketplace automobile (France)

## Livrable
Site HTML complet et fonctionnel (Tailwind CDN + JS vanilla, données persistées en localStorage — démo opérationnelle de bout en bout). Dossier : `/app/frontend/public/swipeupcar/`.
URL : `{REACT_APP_BACKEND_URL}/swipeupcar/index.html`.

## Pages (14)
index, location (recherche+filtres+tri), vehicule (fiche+réservation), reservation (paiement), confirmation, connexion, inscription, devenir-loueur, compte (particulier), loueur (dashboard pro), admin (back-office), messages (messagerie modérée), services (bientôt), infos (comment ça marche/sécurité/FAQ/contact/CGU/confidentialité/mentions).

## Rôles & comptes démo
- Client : client@swipeupcar.fr / client123
- Loueur : loueur@swipeupcar.fr / loueur123
- Admin : admin@swipeupcar.fr / admin123
- Rôles prévus (extension) : GARAGE, PNEUMATIQUE, VENDEUR_PIÈCES, LAVAGE

## Fonctionnel vérifié
- Parcours client : recherche → filtres → fiche → dates → réservation → paiement test → confirmation → espace perso.
- Commission 5% calculée automatiquement (360€ → 18€), configurable en admin.
- Parcours loueur : inscription pro → validation admin → ajout véhicule (brouillon/soumission) → calendrier → revenus (net 95%).
- Admin : validation loueurs/annonces, dashboard CA/commissions, paramètres taux.
- Messagerie : filtrage anti-contournement (téléphone/email/URL/réseaux masqués).
- Anti double-réservation côté logique (overlaps), favoris, avis liés à réservation, notifications, états vides.

## Backlog / production
- P0 : backend réel (Next.js/Supabase ou FastAPI+Mongo), Stripe Connect réel (reversements), stockage images réel, emails transactionnels.
- P1 : carte géographique, SEO (sitemap/robots/OG dynamiques), vérification email, KYC documents.
- P2 : modules Entretien/Pneus/Pièces/Lavage.

## Implémenté
- Location véhicules (backend réel) : auth JWT, véhicules, réservations, commission 5% serveur, paiement (UI test), carte Leaflet, admin.
- Emails transactionnels (Resend managé) : inscription, réservation, validation.
- **Module RDV services (Entretien/Garage, Pneus, Lavage)** — sans commande ni paiement :
  - `providers` (users role PRO + proType), prestations éditables, `appointments` (RDV) en base.
  - Pages : services.html (annuaire par type), service.html (prise de RDV), devenir-partenaire.html, pro.html (dashboard prestataire), compte.html « Mes rendez-vous », admin Prestataires + RDV.
  - Emails RDV client + prestataire. Validation prestataire par admin.
- Comptes pro démo : garage@swipeupcar.fr / pneus@swipeupcar.fr / lavage@swipeupcar.fr (mdp pro123).

## Implémenté (récent)
- Photos réelles : object storage Emergent — POST /api/upload (auth, max 6 Mo), GET /api/files/{path}. Loueur "Ajouter un véhicule" upload multi-photos réel.
- RDV avec créneaux : anti double-réservation serveur (409), GET /providers/{id}/availability?date.
- Confirmation Pro : RDV créé "En attente" → POST /appointments/{id}/{accept|refuse} → "confirmé/refusé" + emails. Dashboard pro (Accepter/Refuser), statuts colorés côté client.

## Implémenté (session fork — juin 2026)
- **Messagerie serveur** : conversations/messages persistés en MongoDB (collection `conversations`), historique multi-appareils, filtre anti-contournement côté serveur (téléphone/email/URL masqués). Endpoints : GET/POST `/api/conversations`, GET `/api/conversations/{id}`, POST `/api/conversations/{id}/messages`. Polling 6s côté client. (localStorage abandonné pour la messagerie.)
- **Vérification email obligatoire avant réservation** : `/api/bookings` et `/api/payments/checkout/booking` → 403 si email non confirmé. Page réservation affiche un blocage + bouton « Renvoyer l'email ».
- **Pages légales complètes** : `cgu.html`, `cgv.html`, `confidentialite.html` (RGPD), `mentions-legales.html` (liées depuis footer + infos.html). Aucune mention « à faire valider ». Mentions légales : quelques champs société `[à compléter]` (SIRET/adresse/hébergeur).
- **Compte officiel/admin** : `swipeupcar.pro@gmail.com` migré de LOUEUR → ADMIN (mdp `SwipeAdmin@2026`). Reçoit les notifications admin. Véhicules de démo réattribués à `sophie@swipeupcar.fr`.
- **Fix bug** : section Sécurité de infos.html (template literal JS écrit en HTML statique) → cartes rendues correctement.
- Tests : pytest backend 16/16 + Playwright frontend 100% (iteration_1.json).

## Implémenté (session fork — juin 2026, suite)
- **Stripe Connect loueur SUPPRIMÉ** : endpoints `/api/stripe/connect/*` retirés (404) + fonctions frontend mortes retirées. Cohérent avec le modèle 5% only (les loueurs n'ont pas besoin de Stripe). Testé 26/26 backend + 32/32 frontend (iteration_2.json).
- **Module Pièces auto (simple, sans e-commerce)** : nouveau type de pro `PIECES`. Le vendeur publie une annonce avec coordonnées directes (téléphone, adresse, site web) affichées aux clients ; boutons « Appeler » / « Itinéraire ». Pas de panier/paiement/RDV. Annuaire sur `services.html?s=pieces` + fiche `service.html`.
- **Validation admin obligatoire avant publication** pour TOUS les pros (garage/pneus/lavage/pièces) : `POST /api/providers/service` → 403 tant que `proStatus != "Validé"`. UI pro.html verrouillée + bandeau tant que non validé.
- **Filtre par zone/ville sur les services** : champ « Votre ville ou secteur » sur `services.html` (filtrage en direct par ville/adresse, comme les locations). Compteur de résultats + conservation du secteur entre onglets.
- Seed : vendeur de pièces démo `pieces@swipeupcar.fr` (AutoPièces Express, Lille).

## Implémenté (session fork — juin 2026, suite 2)
- **Avis en base** : avis clients migrés de localStorage vers MongoDB (collection `reviews`), liés à une location terminée (note 1-5 + commentaire). `POST /api/reviews` (auth, anti-doublon, réservation terminée requise), `GET /api/reviews/vehicle/{id}` (public), `GET /api/reviews/mine`. La note moyenne + nombre d'avis du véhicule ET la note/satisfaction du loueur sont recalculées automatiquement. Affichés sur la fiche véhicule et dans compte.html.
- **Photos pour tous les pros** (garage/pneus/lavage/pièces) : upload dans pro.html (« Ma vitrine »/« Mon annonce »), stockées via object storage + `/providers/profile`. Affichées en vignette sur les cartes `services.html` et en galerie sur `service.html`. 4 pros de démo pré-remplis avec photos.
- **Filtre par distance/rayon** sur les services : géocodage de la ville (dictionnaire villes FR + fallback Nominatim), rayon 10/25/50/100 km, tri par distance + badge « à X km ». `GET /api/geocode`. Villes des pros géocodées à l'inscription et à la sauvegarde du profil.
- Tests : 45/45 pytest backend + frontend 100% (iteration_3.json).

## Implémenté (session fork — juin 2026, suite 3)
- **Carte des prestataires** : carte Leaflet sur `services.html` (bouton « Afficher la carte »), marqueurs par lat/lng pour garages/pneus/lavage/pièces, popup nom/ville/distance + lien fiche. Se met à jour avec le filtre par rayon.
- **Réponse du loueur aux avis** : `GET /api/reviews/owner/mine`, `POST /api/reviews/{rid}/reply` (contrôle propriété véhicule, réponse non vide). Le loueur répond depuis loueur.html onglet « Avis » ; la réponse s'affiche publiquement sur la fiche véhicule.
- Nettoyage des données de test résiduelles. Tests : 54/54 pytest backend + frontend 100% (iteration_4.json).

## Implémenté (session fork — juin 2026, suite 4)
- **Signalement d'avis + modération admin** : bouton « Signaler » sur chaque avis (fiche véhicule), `POST /api/reviews/{rid}/report` (auth, anti-doublon par utilisateur). Nouvel onglet admin « Modération avis » (`GET /api/admin/reviews/reported`) avec actions Supprimer (`/delete`, recalcule la note) et Ignorer (`/dismiss`).
- **Encart accueil « Trouvez un pro près de chez vous »** : sur index.html, champ ville + catégorie (entretien/pneus/lavage/pièces) redirigeant vers `services.html?s=<cat>&zone=<ville>`.
- Tests : 66/66 pytest backend + frontend 100% (iteration_5.json).

## Implémenté (session fork — juin 2026, suite 5)
- **Expérience mobile (design conservé)** : correction responsive complète. Cause racine trouvée : attributs `class=` en double sur les conteneurs dashboard/location → les media queries étaient inertes ; contenu tassé et débordements. Corrigé + règles globales dans `style.css` (repli 1 colonne du héro, des formulaires de recherche, des tableaux de bord, des grilles de specs via `.stack-sm`, `minmax(0,1fr)`, `img{max-width:100%}`). Résultat : 10/10 pages sans débordement horizontal à 390px, desktop 1280px inchangé (iteration_7.json, 100%).

## Implémenté (session fork — juin 2026, suite 6)
- **Menu mobile ☰** : bouton hamburger (mobile uniquement) dans la barre du haut ouvrant un panneau d'accès rapide (Louer, Entretien, Pneus, Pièces auto, Lavage + Mon espace/Messages/Quitter ou Se connecter). Caché sur desktop (menu classique conservé).
- **Onglets de compte visibles sur mobile** : correction du bug où les sidebars (client/pro/loueur/admin) avaient `hide-mobile` → onglets invisibles. Désormais barre d'onglets horizontale scrollable (chips) en haut du tableau de bord sur mobile, sidebar verticale sticky conservée sur desktop.
- Tests : frontend 100% sur les 4 rôles à 390px + non-régression desktop (iteration_8.json).

## Reste (P0/P1)
- Migrer les **avis (reviews)** de localStorage vers la base (toujours en local). (P1) — ✅ FAIT (suite 2)
- Module **Pièces auto** (e-commerce : catalogue, panier, livraison). (P1)
- Stripe Connect onboarding : gérer l'erreur si le loueur n'a pas finalisé son compte Stripe. (P1) — NB : modèle 5% only, pas de reversement 95%.
- SMS rappels RDV (P2), modération photo auto (plaques/QR/téléphone) (P2).
- Compléter les champs société des mentions légales (SIRET, adresse, hébergeur, directeur de publication). (P2)

## DEMO_MODE (preview vs production GitHub) — 2026-06-09
- Variable env `DEMO_MODE` (backend/.env). Preview = "true", production GitHub = absente/false.
- `GET /api/config` → `{demo_mode: bool}` (server.py).
- Seed données démo (server.py startup) exécuté UNIQUEMENT si DEMO_MODE=true.
- `connexion.html` récupère /api/config et masque le bloc identifiants de démo si demo_mode=false.
- Résultat : preview reste une démo (données + identifiants visibles) ; code poussé sur GitHub = base propre sans fausses données ni identifiants.
- Vérifié : curl /api/config → {"demo_mode":true} en preview ; screenshot connexion → bloc démo visible.
