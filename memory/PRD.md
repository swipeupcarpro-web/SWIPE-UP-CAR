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

## Reste (P0/P1)
- Migrer les **avis (reviews)** de localStorage vers la base (toujours en local). (P1)
- Module **Pièces auto** (e-commerce : catalogue, panier, livraison). (P1)
- Stripe Connect onboarding : gérer l'erreur si le loueur n'a pas finalisé son compte Stripe. (P1) — NB : modèle 5% only, pas de reversement 95%.
- SMS rappels RDV (P2), modération photo auto (plaques/QR/téléphone) (P2).
- Compléter les champs société des mentions légales (SIRET, adresse, hébergeur, directeur de publication). (P2)
