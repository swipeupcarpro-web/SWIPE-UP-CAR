"""SWIPEUPCAR iteration 3 tests: reviews (DB), pro photos, distance/geocode filter."""
import os, uuid, pytest, requests
from datetime import datetime, timezone, date, timedelta

BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or 'https://location-vehicles-1.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

CLIENT = ("client@swipeupcar.fr", "client123")
ADMIN = ("swipeupcar.pro@gmail.com", "SwipeAdmin@2026")
OWNER = ("sophie@swipeupcar.fr", "loueur123")
PROS = {
    "GARAGE": ("garage@swipeupcar.fr", "pro123"),
    "PNEUMATIQUE": ("pneus@swipeupcar.fr", "pro123"),
    "LAVAGE": ("lavage@swipeupcar.fr", "pro123"),
    "PIECES": ("pieces@swipeupcar.fr", "pro123"),
}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"], r.json()["user"]


def _h(t): return {"Authorization": f"Bearer {t}"}


# ---------- Geocode ----------
class TestGeocode:
    def test_geocode_bordeaux(self):
        r = requests.get(f"{API}/geocode", params={"q": "Bordeaux"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d.get("found") is True
        assert abs(d["lat"] - 44.8378) < 0.01
        assert abs(d["lng"] - (-0.5792)) < 0.01

    def test_geocode_paris(self):
        r = requests.get(f"{API}/geocode", params={"q": "Paris"}, timeout=30)
        assert r.status_code == 200
        assert r.json().get("found") is True

    def test_geocode_nantes(self):
        r = requests.get(f"{API}/geocode", params={"q": "Nantes"}, timeout=30)
        d = r.json()
        assert d.get("found") is True
        assert abs(d["lat"] - 47.2184) < 0.01

    def test_geocode_unknown(self):
        r = requests.get(f"{API}/geocode", params={"q": "ZZZunknowncity999"}, timeout=30)
        # Nominatim fallback may still find something, but usually returns found=False
        assert r.status_code == 200


# ---------- Provider photos ----------
class TestProviderPhotos:
    @pytest.mark.parametrize("ptype", ["GARAGE", "PNEUMATIQUE", "LAVAGE", "PIECES"])
    def test_providers_list_has_photos_field(self, ptype):
        r = requests.get(f"{API}/providers", params={"type": ptype}, timeout=30)
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list) and len(arr) >= 1, f"No providers of type {ptype}"
        for p in arr:
            assert "photos" in p, f"'photos' key missing on {ptype} provider {p.get('company')}"
            assert isinstance(p["photos"], list)

    def test_demo_pros_have_seeded_photos(self):
        # Each of the 4 demo pros should have at least 2 photos seeded
        for ptype, (email, _) in PROS.items():
            arr = requests.get(f"{API}/providers", params={"type": ptype}, timeout=30).json()
            match = next((x for x in arr if x.get("company")), None)
            assert match is not None, f"No provider found for {ptype}"
            # Locate demo pro by email is not exposed; verify at least one provider of that type has >=2 photos
            has_photos = any(len(x.get("photos", [])) >= 2 for x in arr)
            assert has_photos, f"No {ptype} provider has >=2 seeded photos"

    def test_pro_photo_upload_persists(self):
        # Login as garage@ pro, POST profile with new photos, verify persistence
        tok, u = _login(*PROS["GARAGE"])
        new_photos = [
            "https://images.unsplash.com/photo-1676018366904-c083ed678e60?w=600&q=80",
            "https://images.unsplash.com/photo-1618312980096-873bd19759a0?w=600&q=80",
            "https://example.com/test_photo.jpg",
        ]
        r = requests.post(f"{API}/providers/profile",
                         json={"city": u.get("city", "Paris"), "description": u.get("description", ""),
                               "company": u.get("company", ""), "photos": new_photos},
                         headers=_h(tok), timeout=30)
        assert r.status_code == 200, r.text
        # Verify via /auth/me
        me = requests.get(f"{API}/auth/me", headers=_h(tok), timeout=30).json()
        assert me.get("photos") == new_photos or set(new_photos).issubset(set(me.get("photos", [])))
        # Also visible in public providers list
        pr = requests.get(f"{API}/providers", params={"type": "GARAGE"}, timeout=30).json()
        me_pub = next((x for x in pr if x["id"] == str(u["id"])), None)
        assert me_pub is not None
        assert "https://example.com/test_photo.jpg" in me_pub.get("photos", [])

        # Restore original 2 photos for cleanliness
        requests.post(f"{API}/providers/profile",
                    json={"city": u.get("city", "Paris"), "description": u.get("description", ""),
                          "company": u.get("company", ""), "photos": new_photos[:2]},
                    headers=_h(tok), timeout=30)


# ---------- Reviews ----------
class TestReviewsAuth:
    def test_post_review_requires_auth(self):
        r = requests.post(f"{API}/reviews",
                          json={"bookingId": "000000000000000000000000", "rating": 5, "text": "nope"},
                          timeout=30)
        assert r.status_code in (401, 403)

    def test_reviews_vehicle_public(self):
        vs = requests.get(f"{API}/vehicles", timeout=30).json()
        assert len(vs) > 0
        vid = vs[0]["id"]
        r = requests.get(f"{API}/reviews/vehicle/{vid}", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_reviews_mine_requires_auth(self):
        r = requests.get(f"{API}/reviews/mine", timeout=30)
        assert r.status_code in (401, 403)


@pytest.fixture(scope="module")
def client_ctx():
    tok, u = _login(*CLIENT)
    return tok, u


@pytest.fixture(scope="module")
def owner_ctx():
    tok, u = _login(*OWNER)
    return tok, u


class TestReviewsFlow:
    def test_post_review_ownership_check(self, client_ctx):
        tok, _ = client_ctx
        # Random/nonexistent bookingId -> 404
        r = requests.post(f"{API}/reviews",
                          json={"bookingId": "507f1f77bcf86cd799439011", "rating": 5, "text": "x"},
                          headers=_h(tok), timeout=30)
        assert r.status_code == 404

    def test_review_flow_end_to_end(self, client_ctx, owner_ctx):
        """Create a booking as client, backdate it via admin/DB not possible via API.
        So: create a future booking, try review -> should get 400 (not terminated yet)."""
        ctok, cu = client_ctx
        vs = requests.get(f"{API}/vehicles", timeout=30).json()
        vid = vs[0]["id"]
        today = date.today()
        # Book in far future with random offset to avoid collision with prior test runs
        offset = 90 + (uuid.uuid4().int % 500)
        # Book in future
        r = requests.post(f"{API}/bookings",
                          json={"vehicleId": vid,
                                "frm": (today + timedelta(days=offset)).isoformat(),
                                "to": (today + timedelta(days=offset+2)).isoformat()},
                          headers=_h(ctok), timeout=30)
        assert r.status_code == 200, r.text
        bid = r.json().get("id") or r.json().get("bookingId")
        assert bid, r.json()
        # Try to leave a review -> should be 400 (location not finished)
        rr = requests.post(f"{API}/reviews",
                           json={"bookingId": bid, "rating": 5, "text": "TEST review"},
                           headers=_h(ctok), timeout=30)
        assert rr.status_code == 400
        assert "après la fin" in rr.json().get("detail", "").lower() or "fin" in rr.json().get("detail", "").lower()

    def test_review_on_terminated_booking_via_mongo(self, client_ctx):
        """Directly insert a terminated booking in Mongo for this client, then POST review, then duplicate."""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        if not mongo_url or not db_name:
            # Load from backend/.env
            from dotenv import dotenv_values
            v = dotenv_values("/app/backend/.env")
            mongo_url = mongo_url or v.get("MONGO_URL")
            db_name = db_name or v.get("DB_NAME")
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]

        ctok, cu = client_ctx
        vs = requests.get(f"{API}/vehicles", timeout=30).json()
        veh = vs[0]
        vid = veh["id"]

        async def _seed_booking():
            from bson import ObjectId
            doc = {
                "userId": cu["id"],
                "vehicleId": vid,
                "ownerId": None,
                "vehicleTitle": f"{veh.get('brand','')} {veh.get('model','')}",
                "frm": (date.today() - timedelta(days=10)).isoformat(),
                "to": (date.today() - timedelta(days=5)).isoformat(),
                "status": "confirmé",
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "ref": "TEST-" + uuid.uuid4().hex[:6].upper(),
            }
            res = await db.bookings.insert_one(doc)
            return str(res.inserted_id)

        async def _cleanup(bid):
            from bson import ObjectId
            await db.bookings.delete_one({"_id": ObjectId(bid)})
            await db.reviews.delete_many({"bookingId": bid})

        loop = asyncio.new_event_loop()
        try:
            bid = loop.run_until_complete(_seed_booking())
            # POST review -> 200
            r = requests.post(f"{API}/reviews",
                              json={"bookingId": bid, "rating": 4, "text": "TEST_review avis client"},
                              headers=_h(ctok), timeout=30)
            assert r.status_code == 200, r.text
            rev = r.json()
            assert rev["rating"] == 4
            assert rev["vehicleId"] == vid

            # Duplicate -> 400
            r2 = requests.post(f"{API}/reviews",
                               json={"bookingId": bid, "rating": 5, "text": "again"},
                               headers=_h(ctok), timeout=30)
            assert r2.status_code == 400
            assert "déjà" in r2.json().get("detail", "").lower()

            # Public GET returns the review
            gr = requests.get(f"{API}/reviews/vehicle/{vid}", timeout=30).json()
            assert any(x.get("text", "").startswith("TEST_review") for x in gr)

            # Vehicle rating recomputed
            v = next((x for x in requests.get(f"{API}/vehicles", timeout=30).json() if x["id"] == vid), None)
            assert v is not None
            assert v["reviews"] >= 1

            # /reviews/mine includes it
            mine = requests.get(f"{API}/reviews/mine", headers=_h(ctok), timeout=30).json()
            assert any(x["bookingId"] == bid for x in mine)
        finally:
            try:
                loop.run_until_complete(_cleanup(bid))
            except Exception:
                pass
            loop.close()


# ---------- Distance filter (services) — via geocode + provider lat/lng ----------
class TestDistanceFilter:
    def test_lavage_pros_have_coords(self):
        arr = requests.get(f"{API}/providers", params={"type": "LAVAGE"}, timeout=30).json()
        assert len(arr) >= 1
        for p in arr:
            assert "lat" in p and "lng" in p, f"lat/lng missing for {p.get('company')}"

    def test_bordeaux_lavage_present(self):
        # BullePro Detailing seed
        arr = requests.get(f"{API}/providers", params={"type": "LAVAGE"}, timeout=30).json()
        bordeaux = [p for p in arr if p.get("city", "").lower() == "bordeaux"]
        assert len(bordeaux) >= 1, f"Expected Bordeaux lavage pro, got cities={[p.get('city') for p in arr]}"


# ---------- Pièces auto — pro geocoded on registration ----------
class TestPiecesRegisterGeocoded:
    def test_new_pieces_pro_gets_lat_lng(self):
        email = f"TEST_iter3_pieces_{uuid.uuid4().hex[:8]}@test.fr"
        r = requests.post(f"{API}/auth/register", json={
            "firstName": "Test", "lastName": "Nantes", "email": email,
            "password": "test1234", "role": "PRO", "proType": "PIECES",
            "company": "TEST Nantes Pieces", "city": "Nantes"
        }, timeout=30)
        assert r.status_code == 200, r.text
        tok = r.json()["token"]
        me = requests.get(f"{API}/auth/me", headers=_h(tok), timeout=30).json()
        # Nantes ~ 47.2184, -1.5536
        assert abs(me["lat"] - 47.2184) < 0.05
        assert abs(me["lng"] - (-1.5536)) < 0.05
        assert me.get("proStatus") == "En vérification"
