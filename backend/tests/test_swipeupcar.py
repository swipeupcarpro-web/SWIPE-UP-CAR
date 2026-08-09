"""SWIPEUPCAR backend tests - messaging, verification block, admin migration."""
import os, uuid, pytest, requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://location-vehicles-1.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

CLIENT = ("client@swipeupcar.fr", "client123")
ADMIN = ("swipeupcar.pro@gmail.com", "SwipeAdmin@2026")
OWNER = ("sophie@swipeupcar.fr", "loueur123")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    return r


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- Auth / Admin migration ----------
class TestAuth:
    def test_client_login(self):
        r = _login(*CLIENT)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["verified"] is True

    def test_admin_login_new_password(self):
        r = _login(*ADMIN)
        assert r.status_code == 200, r.text
        assert r.json()["user"]["role"] == "ADMIN"

    def test_admin_old_password_rejected(self):
        r = _login(ADMIN[0], "loueur123")
        assert r.status_code == 401

    def test_owner_login(self):
        r = _login(*OWNER)
        assert r.status_code == 200
        # Should own the 8 demo vehicles now
        token = r.json()["token"]
        vr = requests.get(f"{API}/vehicles/owner/mine", headers=_auth_headers(token), timeout=30)
        assert vr.status_code == 200
        vs = vr.json()
        assert len(vs) >= 1, f"Expected demo vehicles owned by sophie, got {len(vs)}"


# ---------- Messaging ----------
@pytest.fixture(scope="module")
def client_token():
    r = _login(*CLIENT)
    assert r.status_code == 200
    return r.json()["token"], r.json()["user"]["id"]


@pytest.fixture(scope="module")
def owner_info():
    r = _login(*OWNER)
    assert r.status_code == 200
    return r.json()["token"], r.json()["user"]["id"]


class TestMessaging:
    def test_create_conversation_and_send(self, client_token, owner_info):
        ct, cid = client_token
        ot, oid_ = owner_info
        # Client creates conv to owner
        r = requests.post(f"{API}/conversations",
                          json={"to": oid_, "vehicleId": None},
                          headers=_auth_headers(ct), timeout=30)
        assert r.status_code == 200, r.text
        conv = r.json()
        assert conv["otherId"] == oid_
        conv_id = conv["id"]
        # Simple message
        r2 = requests.post(f"{API}/conversations/{conv_id}/messages",
                           json={"text": "Bonjour, la voiture est-elle dispo ?"},
                           headers=_auth_headers(ct), timeout=30)
        assert r2.status_code == 200, r2.text
        assert r2.json()["warn"] is False

        # Contact masking - phone + email
        r3 = requests.post(f"{API}/conversations/{conv_id}/messages",
                           json={"text": "Appelle-moi 0612345678 ou test@example.com"},
                           headers=_auth_headers(ct), timeout=30)
        assert r3.status_code == 200
        body = r3.json()
        assert body["warn"] is True
        assert "0612345678" not in body["message"]["text"]
        assert "test@example.com" not in body["message"]["text"]
        assert "•••••" in body["message"]["text"]

        # Persistence: fetch
        r4 = requests.get(f"{API}/conversations/{conv_id}",
                          headers=_auth_headers(ct), timeout=30)
        assert r4.status_code == 200
        msgs = r4.json()["messages"]
        assert len(msgs) >= 2

        # Owner can access too (membership)
        r5 = requests.get(f"{API}/conversations/{conv_id}",
                          headers=_auth_headers(ot), timeout=30)
        assert r5.status_code == 200
        assert len(r5.json()["messages"]) >= 2

    def test_non_member_forbidden(self, client_token, owner_info):
        ct, cid = client_token
        ot, oid_ = owner_info
        # Create a fresh conv
        r = requests.post(f"{API}/conversations",
                          json={"to": oid_},
                          headers=_auth_headers(ct), timeout=30)
        conv_id = r.json()["id"]
        # Create a third user
        email = f"TEST_intruder_{uuid.uuid4().hex[:8]}@test.fr"
        rr = requests.post(f"{API}/auth/register",
                           json={"firstName": "In", "lastName": "Truder", "email": email,
                                 "password": "test1234", "role": "PARTICULIER"}, timeout=30)
        assert rr.status_code == 200, rr.text
        tok = rr.json()["token"]
        r2 = requests.get(f"{API}/conversations/{conv_id}",
                          headers=_auth_headers(tok), timeout=30)
        assert r2.status_code == 404

    def test_list_conversations_auth(self, client_token):
        ct, _ = client_token
        r = requests.get(f"{API}/conversations", headers=_auth_headers(ct), timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_conversations_unauth(self):
        r = requests.get(f"{API}/conversations", timeout=30)
        assert r.status_code == 401


# ---------- Verification block ----------
@pytest.fixture(scope="module")
def unverified_user():
    email = f"TEST_unv_{uuid.uuid4().hex[:8]}@test.fr"
    r = requests.post(f"{API}/auth/register",
                      json={"firstName": "Un", "lastName": "Verified", "email": email,
                            "password": "test1234", "role": "PARTICULIER"}, timeout=30)
    assert r.status_code == 200
    return r.json()["token"], r.json()["user"]["id"]


@pytest.fixture(scope="module")
def approved_vehicle_id(owner_info):
    ot, _ = owner_info
    r = requests.get(f"{API}/vehicles", timeout=30)
    assert r.status_code == 200
    vs = r.json()
    assert len(vs) > 0, "No approved vehicles seeded"
    return vs[0]["id"]


class TestVerificationBlock:
    def test_unverified_cannot_book(self, unverified_user, approved_vehicle_id):
        tok, _ = unverified_user
        r = requests.post(f"{API}/bookings",
                          json={"vehicleId": approved_vehicle_id,
                                "frm": "2026-06-01", "to": "2026-06-03"},
                          headers=_auth_headers(tok), timeout=30)
        assert r.status_code == 403
        assert "confirmer" in r.json().get("detail", "").lower()

    def test_unverified_cannot_checkout(self, unverified_user, approved_vehicle_id):
        tok, _ = unverified_user
        r = requests.post(f"{API}/payments/checkout/booking",
                          json={"vehicleId": approved_vehicle_id, "frm": "2026-06-01",
                                "to": "2026-06-03", "origin_url": BASE_URL},
                          headers=_auth_headers(tok), timeout=30)
        assert r.status_code == 403

    def test_verified_client_can_initiate_checkout(self, client_token, approved_vehicle_id):
        tok, _ = client_token
        r = requests.post(f"{API}/payments/checkout/booking",
                          json={"vehicleId": approved_vehicle_id, "frm": "2027-01-01",
                                "to": "2027-01-03", "origin_url": BASE_URL},
                          headers=_auth_headers(tok), timeout=45)
        # 200 with checkout_url expected (Stripe test)
        assert r.status_code == 200, r.text
        assert "checkout_url" in r.json()

    def test_resend_verification(self, unverified_user):
        tok, _ = unverified_user
        r = requests.post(f"{API}/auth/resend-verification",
                          headers=_auth_headers(tok), timeout=30)
        assert r.status_code == 200
        assert r.json().get("ok") is True


# ---------- Iteration 2 : Stripe supprimé, PIECES, validation pro ----------
class TestStripeConnectRemoved:
    def test_onboard_removed(self):
        # Try with sophie loueur token (was intended to onboard) - should be 404
        r = _login(*OWNER)
        tok = r.json()["token"]
        rr = requests.post(f"{API}/stripe/connect/onboard", headers=_auth_headers(tok), timeout=30)
        assert rr.status_code == 404, f"Endpoint should be removed, got {rr.status_code}"

    def test_status_removed(self):
        r = _login(*OWNER)
        tok = r.json()["token"]
        rr = requests.get(f"{API}/stripe/connect/status", headers=_auth_headers(tok), timeout=30)
        assert rr.status_code == 404

    def test_loueur_html_no_connectStripe(self):
        r = requests.get(f"{BASE_URL}/swipeupcar/loueur.html", timeout=30)
        assert r.status_code == 200
        html = r.text
        assert "connectStripe" not in html, "loueur.html still contains connectStripe function"
        assert "stripe/connect/onboard" not in html


class TestPiecesProvidersDirectory:
    def test_pieces_provider_listed(self):
        r = requests.get(f"{API}/providers?type=PIECES", timeout=30)
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list) and len(arr) >= 1
        p = next((x for x in arr if x.get("company") == "AutoPièces Express"), None)
        assert p is not None, f"AutoPièces Express not found in {arr}"
        assert p.get("phone")
        assert p.get("address")
        assert p.get("website")
        assert p.get("proType") == "PIECES"

    def test_get_pieces_provider_detail(self):
        arr = requests.get(f"{API}/providers?type=PIECES", timeout=30).json()
        pid = arr[0]["id"]
        r = requests.get(f"{API}/providers/{pid}", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["proType"] == "PIECES"
        assert "phone" in d and "address" in d and "website" in d


@pytest.fixture(scope="module")
def new_pro_pieces():
    """Register a fresh PIECES pro (unvalidated)"""
    email = f"TEST_pro_pieces_{uuid.uuid4().hex[:8]}@test.fr"
    r = requests.post(f"{API}/auth/register", json={
        "firstName": "Test", "lastName": "Pieces", "email": email,
        "password": "test1234", "role": "PRO", "proType": "PIECES",
        "company": "TEST PIECES Co", "city": "Paris"
    }, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"], r.json()["user"]["id"], email


@pytest.fixture(scope="module")
def new_pro_garage():
    email = f"TEST_pro_garage_{uuid.uuid4().hex[:8]}@test.fr"
    r = requests.post(f"{API}/auth/register", json={
        "firstName": "Test", "lastName": "Garage", "email": email,
        "password": "test1234", "role": "PRO", "proType": "GARAGE",
        "company": "TEST Garage Co", "city": "Paris"
    }, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"], r.json()["user"]["id"], email


class TestProValidationGate:
    def test_unvalidated_pro_status(self, new_pro_pieces):
        tok, uid, email = new_pro_pieces
        r = requests.get(f"{API}/auth/me", headers=_auth_headers(tok), timeout=30)
        assert r.status_code == 200
        assert r.json().get("proStatus") == "En vérification"
        assert r.json().get("proType") == "PIECES"

    def test_unvalidated_pro_cannot_add_service(self, new_pro_garage):
        tok, uid, _ = new_pro_garage
        r = requests.post(f"{API}/providers/service",
                          json={"name": "Vidange", "price": 89, "duration": "1h"},
                          headers=_auth_headers(tok), timeout=30)
        assert r.status_code == 403
        detail = r.json().get("detail", "").lower()
        assert "validé" in detail or "administration" in detail, f"Unexpected detail: {detail}"

    def test_pieces_pro_update_profile(self, new_pro_pieces):
        tok, uid, _ = new_pro_pieces
        r = requests.post(f"{API}/providers/profile", json={
            "city": "Marseille", "description": "Test annonce pièces",
            "phone": "0491000000", "address": "1 rue Test 13000 Marseille",
            "website": "https://test-pieces.fr"
        }, headers=_auth_headers(tok), timeout=30)
        assert r.status_code == 200
        # Verify persistence via /auth/me
        me = requests.get(f"{API}/auth/me", headers=_auth_headers(tok), timeout=30).json()
        assert me.get("phone") == "0491000000"
        assert me.get("address") == "1 rue Test 13000 Marseille"
        assert me.get("website") == "https://test-pieces.fr"

    def test_admin_validate_and_then_service_add(self, new_pro_garage):
        tok, uid, _ = new_pro_garage
        # Admin login
        ar = _login(*ADMIN)
        assert ar.status_code == 200
        atok = ar.json()["token"]
        # Validate
        vr = requests.post(f"{API}/admin/owners/{uid}/validate",
                           headers=_auth_headers(atok), timeout=30)
        assert vr.status_code == 200, vr.text
        # Now add service should work
        r = requests.post(f"{API}/providers/service",
                          json={"name": "TEST Vidange", "price": 89, "duration": "1h"},
                          headers=_auth_headers(tok), timeout=30)
        assert r.status_code == 200, r.text
        # Verify present in providers list
        pr = requests.get(f"{API}/providers?type=GARAGE", timeout=30).json()
        found = next((x for x in pr if x["id"] == uid), None)
        assert found is not None, "Validated GARAGE pro should appear in directory"
        assert any(s["name"] == "TEST Vidange" for s in found.get("services", []))

    def test_unvalidated_pieces_not_in_directory(self, new_pro_pieces):
        tok, uid, _ = new_pro_pieces
        arr = requests.get(f"{API}/providers?type=PIECES", timeout=30).json()
        found = [x for x in arr if x["id"] == uid]
        assert not found, "Unvalidated PIECES pro should NOT appear in public directory"


# ---------- Legal pages served ----------
class TestLegalPages:
    @pytest.mark.parametrize("path", [
        "/swipeupcar/cgu.html",
        "/swipeupcar/cgv.html",
        "/swipeupcar/confidentialite.html",
        "/swipeupcar/mentions-legales.html",
    ])
    def test_page_loads(self, path):
        r = requests.get(f"{BASE_URL}{path}", timeout=30)
        assert r.status_code == 200, path
        assert len(r.text) > 500, f"{path} too small"
