"""SWIPEUPCAR iteration 4 tests: owner reply on reviews + providers map data."""
import os, uuid, pytest, requests, asyncio
from datetime import datetime, timezone, date, timedelta
from dotenv import dotenv_values
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or 'https://location-vehicles-1.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

CLIENT = ("client@swipeupcar.fr", "client123")
OWNER = ("sophie@swipeupcar.fr", "loueur123")
ADMIN = ("swipeupcar.pro@gmail.com", "SwipeAdmin@2026")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"], r.json()["user"]


def _h(t): return {"Authorization": f"Bearer {t}"}


def _db():
    env = dotenv_values("/app/backend/.env")
    return AsyncIOMotorClient(env["MONGO_URL"])[env["DB_NAME"]]


@pytest.fixture(scope="module")
def owner_ctx():
    return _login(*OWNER)


@pytest.fixture(scope="module")
def client_ctx():
    return _login(*CLIENT)


# ---------- Auth guards ----------
class TestReplyAuth:
    def test_reply_requires_auth(self):
        r = requests.post(f"{API}/reviews/000000000000000000000000/reply", json={"text": "x"}, timeout=30)
        assert r.status_code in (401, 403)

    def test_owner_mine_requires_auth(self):
        r = requests.get(f"{API}/reviews/owner/mine", timeout=30)
        assert r.status_code in (401, 403)


# ---------- Owner reviews (empty state is OK) ----------
class TestOwnerReviewsList:
    def test_owner_mine_returns_list(self, owner_ctx):
        tok, _ = owner_ctx
        r = requests.get(f"{API}/reviews/owner/mine", headers=_h(tok), timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------- Full E2E: seed booking + review, reply as owner ----------
class TestOwnerReplyE2E:
    def test_reply_flow_end_to_end(self, owner_ctx, client_ctx):
        otok, ou = owner_ctx
        ctok, cu = client_ctx
        db = _db()

        # Find a vehicle owned by sophie
        vs = requests.get(f"{API}/vehicles", timeout=30).json()
        owner_vehs = [v for v in vs if v.get("owner") == ou["id"]]
        assert len(owner_vehs) >= 1, "Sophie should own vehicles"
        veh = owner_vehs[0]
        vid = veh["id"]

        # Also find a vehicle NOT owned by sophie
        other_vehs = [v for v in vs if v.get("owner") != ou["id"]]

        loop = asyncio.new_event_loop()
        bid = rid = other_bid = other_rid = None
        try:
            async def seed(vehicle_id, owner_id):
                doc = {
                    "userId": cu["id"], "vehicleId": vehicle_id, "ownerId": owner_id,
                    "vehicleTitle": "TEST veh",
                    "frm": (date.today() - timedelta(days=10)).isoformat(),
                    "to": (date.today() - timedelta(days=5)).isoformat(),
                    "status": "confirmé",
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                    "ref": "TEST-" + uuid.uuid4().hex[:6].upper(),
                }
                res = await db.bookings.insert_one(doc)
                return str(res.inserted_id)

            bid = loop.run_until_complete(seed(vid, ou["id"]))

            # Client posts a review
            r = requests.post(f"{API}/reviews",
                              json={"bookingId": bid, "rating": 5, "text": "TEST_iter4 super location"},
                              headers=_h(ctok), timeout=30)
            assert r.status_code == 200, r.text
            rid = r.json()["id"]

            # Owner sees it in /reviews/owner/mine with vehicleTitle
            mine = requests.get(f"{API}/reviews/owner/mine", headers=_h(otok), timeout=30).json()
            found = next((x for x in mine if x["id"] == rid), None)
            assert found is not None, "Review should appear in owner/mine"
            assert found.get("vehicleTitle"), "vehicleTitle must be populated"
            assert "ownerReply" not in found or not found.get("ownerReply")

            # Reply as owner
            reply_text = "TEST_iter4 merci pour votre retour !"
            rr = requests.post(f"{API}/reviews/{rid}/reply",
                               json={"text": reply_text}, headers=_h(otok), timeout=30)
            assert rr.status_code == 200, rr.text
            data = rr.json()
            assert data.get("ok") is True
            assert data.get("ownerReply") == reply_text

            # Public GET on vehicle reviews returns ownerReply
            pub = requests.get(f"{API}/reviews/vehicle/{vid}", timeout=30).json()
            entry = next((x for x in pub if x["id"] == rid), None)
            assert entry is not None
            assert entry.get("ownerReply") == reply_text
            assert entry.get("ownerReplyDate")

            # Update reply (idempotent)
            rr2 = requests.post(f"{API}/reviews/{rid}/reply",
                                json={"text": "TEST_iter4 réponse modifiée"}, headers=_h(otok), timeout=30)
            assert rr2.status_code == 200
            assert rr2.json()["ownerReply"] == "TEST_iter4 réponse modifiée"

            # Client (not owner) cannot reply
            rr3 = requests.post(f"{API}/reviews/{rid}/reply",
                                json={"text": "hack"}, headers=_h(ctok), timeout=30)
            assert rr3.status_code == 403

            # If there's a vehicle owned by someone else, sophie cannot reply on its review
            if other_vehs:
                other_v = other_vehs[0]
                other_bid = loop.run_until_complete(seed(other_v["id"], other_v.get("owner")))
                r_o = requests.post(f"{API}/reviews",
                                    json={"bookingId": other_bid, "rating": 3, "text": "TEST_iter4 other"},
                                    headers=_h(ctok), timeout=30)
                assert r_o.status_code == 200
                other_rid = r_o.json()["id"]
                rrX = requests.post(f"{API}/reviews/{other_rid}/reply",
                                    json={"text": "should be 403"}, headers=_h(otok), timeout=30)
                assert rrX.status_code == 403

            # Unknown review id -> 404
            r404 = requests.post(f"{API}/reviews/{ObjectId()}/reply",
                                 json={"text": "x"}, headers=_h(otok), timeout=30)
            assert r404.status_code == 404
        finally:
            async def cleanup():
                for _id in filter(None, [rid, other_rid]):
                    await db.reviews.delete_one({"_id": ObjectId(_id)})
                for _id in filter(None, [bid, other_bid]):
                    await db.bookings.delete_one({"_id": ObjectId(_id)})
                # Also cleanup any TEST_iter4 leftovers
                await db.reviews.delete_many({"text": {"$regex": "^TEST_iter4"}})
                await db.bookings.delete_many({"ref": {"$regex": "^TEST-"}})
            try:
                loop.run_until_complete(cleanup())
            except Exception as e:
                print("cleanup error", e)
            loop.close()


# ---------- Providers map data ----------
class TestProvidersMapData:
    @pytest.mark.parametrize("ptype", ["GARAGE", "PNEUMATIQUE", "LAVAGE", "PIECES"])
    def test_providers_have_lat_lng(self, ptype):
        arr = requests.get(f"{API}/providers", params={"type": ptype}, timeout=30).json()
        assert isinstance(arr, list) and len(arr) >= 1, f"No providers for {ptype}"
        with_coords = [p for p in arr if p.get("lat") is not None and p.get("lng") is not None]
        assert len(with_coords) >= 1, f"No provider with coords for {ptype}: {arr}"

    def test_lavage_bordeaux_bullepro_present(self):
        arr = requests.get(f"{API}/providers", params={"type": "LAVAGE"}, timeout=30).json()
        b = [p for p in arr if p.get("city", "").lower() == "bordeaux" and p.get("lat") is not None]
        assert len(b) >= 1
