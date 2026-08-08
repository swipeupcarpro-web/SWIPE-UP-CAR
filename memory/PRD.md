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

## Reste (P0)
- Stripe Connect : encaissement réel des locations + reversement auto 95% aux loueurs (nécessite onboarding Stripe de chaque loueur). À faire en passe dédiée.
