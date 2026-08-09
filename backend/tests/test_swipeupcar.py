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
