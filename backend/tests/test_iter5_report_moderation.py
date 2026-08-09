"""SWIPEUPCAR iteration 5 tests: report review + admin moderation."""
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
def owner_ctx(): return _login(*OWNER)
@pytest.fixture(scope="module")
def client_ctx(): return _login(*CLIENT)
@pytest.fixture(scope="module")
def admin_ctx(): return _login(*ADMIN)


# ---------- Auth guards ----------
class TestReportAuth:
    def test_report_requires_auth(self):
        r = requests.post(f"{API}/reviews/000000000000000000000000/report",
                          json={"reason": "test"}, timeout=30)
        assert r.status_code in (401, 403)

    def test_admin_reported_requires_auth(self):
        r = requests.get(f"{API}/admin/reviews/reported", timeout=30)
        assert r.status_code in (401, 403)

    def test_admin_reported_forbids_non_admin(self, client_ctx):
        tok, _ = client_ctx
        r = requests.get(f"{API}/admin/reviews/reported", headers=_h(tok), timeout=30)
        assert r.status_code == 403

    def test_admin_reported_ok_for_admin(self, admin_ctx):
        tok, _ = admin_ctx
        r = requests.get(f"{API}/admin/reviews/reported", headers=_h(tok), timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_admin_dismiss_forbids_non_admin(self, client_ctx):
        tok, _ = client_ctx
        r = requests.post(f"{API}/admin/reviews/{ObjectId()}/dismiss", headers=_h(tok), timeout=30)
        assert r.status_code == 403

    def test_admin_delete_forbids_non_admin(self, client_ctx):
        tok, _ = client_ctx
        r = requests.post(f"{API}/admin/reviews/{ObjectId()}/delete", headers=_h(tok), timeout=30)
        assert r.status_code == 403


# ---------- E2E full flow (report -> admin sees -> dismiss / delete) ----------
class TestReportModerationE2E:
    def test_report_then_dismiss(self, owner_ctx, client_ctx, admin_ctx):
        otok, ou = owner_ctx
        ctok, cu = client_ctx
        atok, _ = admin_ctx
        db = _db()

        vs = requests.get(f"{API}/vehicles", timeout=30).json()
        owner_vehs = [v for v in vs if v.get("owner") == ou["id"]]
        assert owner_vehs
        vid = owner_vehs[0]["id"]

        loop = asyncio.new_event_loop()
        bid = rid = None
        try:
            async def seed():
                doc = {
                    "userId": cu["id"], "vehicleId": vid, "ownerId": ou["id"],
                    "vehicleTitle": "TEST veh",
                    "frm": (date.today() - timedelta(days=10)).isoformat(),
                    "to": (date.today() - timedelta(days=5)).isoformat(),
                    "status": "confirmé",
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                    "ref": "TEST-" + uuid.uuid4().hex[:6].upper(),
                }
                res = await db.bookings.insert_one(doc)
                return str(res.inserted_id)

            bid = loop.run_until_complete(seed())
            r = requests.post(f"{API}/reviews",
                              json={"bookingId": bid, "rating": 5, "text": "TEST_iter5 avis à signaler"},
                              headers=_h(ctok), timeout=30)
            assert r.status_code == 200, r.text
            rid = r.json()["id"]

            # Client reports the review
            rp = requests.post(f"{API}/reviews/{rid}/report",
                               json={"reason": "TEST_iter5 contenu inapproprié"},
                               headers=_h(ctok), timeout=30)
            assert rp.status_code == 200
            assert rp.json().get("ok") is True

            # Verify DB flag
            async def check():
                doc = await db.reviews.find_one({"_id": ObjectId(rid)})
                return doc
            doc = loop.run_until_complete(check())
            assert doc.get("reported") is True
            assert isinstance(doc.get("reports"), list) and len(doc["reports"]) >= 1
            assert doc["reports"][-1]["reason"].startswith("TEST_iter5")
            assert doc["reports"][-1]["by"] == cu["id"]

            # Admin GET /admin/reviews/reported returns the review with vehicleTitle
            listed = requests.get(f"{API}/admin/reviews/reported", headers=_h(atok), timeout=30).json()
            entry = next((x for x in listed if x["id"] == rid), None)
            assert entry is not None, "Reported review not in admin list"
            assert entry.get("vehicleTitle"), "vehicleTitle must be populated"
            assert isinstance(entry.get("reports"), list) and len(entry["reports"]) >= 1

            # Admin dismiss
            dm = requests.post(f"{API}/admin/reviews/{rid}/dismiss", headers=_h(atok), timeout=30)
            assert dm.status_code == 200

            doc2 = loop.run_until_complete(check())
            assert doc2.get("reported") is False
            assert doc2.get("reports") == []

            # No longer in reported list
            listed2 = requests.get(f"{API}/admin/reviews/reported", headers=_h(atok), timeout=30).json()
            assert not any(x["id"] == rid for x in listed2)

            # Still visible on public vehicle reviews (dismiss preserves review)
            pub = requests.get(f"{API}/reviews/vehicle/{vid}", timeout=30).json()
            assert any(x["id"] == rid for x in pub), "Review must still exist after dismiss"
        finally:
            async def cleanup():
                if rid:
                    await db.reviews.delete_one({"_id": ObjectId(rid)})
                if bid:
                    await db.bookings.delete_one({"_id": ObjectId(bid)})
                await db.reviews.delete_many({"text": {"$regex": "^TEST_iter5"}})
                await db.bookings.delete_many({"ref": {"$regex": "^TEST-"}})
            try: loop.run_until_complete(cleanup())
            finally: loop.close()

    def test_report_then_delete_recomputes_rating(self, owner_ctx, client_ctx, admin_ctx):
        otok, ou = owner_ctx
        ctok, cu = client_ctx
        atok, _ = admin_ctx
        db = _db()

        vs = requests.get(f"{API}/vehicles", timeout=30).json()
        owner_vehs = [v for v in vs if v.get("owner") == ou["id"]]
        # Use a different vehicle than the dismiss test (index 1 if possible) to avoid xdist race
        veh_before = owner_vehs[1] if len(owner_vehs) > 1 else owner_vehs[0]
        vid = veh_before["id"]
        reviews_before = int(veh_before.get("reviews", 0) or 0)

        loop = asyncio.new_event_loop()
        bid = rid = None
        try:
            async def seed():
                doc = {
                    "userId": cu["id"], "vehicleId": vid, "ownerId": ou["id"],
                    "vehicleTitle": "TEST veh",
                    "frm": (date.today() - timedelta(days=10)).isoformat(),
                    "to": (date.today() - timedelta(days=5)).isoformat(),
                    "status": "confirmé",
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                    "ref": "TEST-" + uuid.uuid4().hex[:6].upper(),
                }
                res = await db.bookings.insert_one(doc)
                return str(res.inserted_id)
            bid = loop.run_until_complete(seed())

            r = requests.post(f"{API}/reviews",
                              json={"bookingId": bid, "rating": 4, "text": "TEST_iter5 avis à supprimer"},
                              headers=_h(ctok), timeout=30)
            assert r.status_code == 200
            rid = r.json()["id"]

            # Report first
            requests.post(f"{API}/reviews/{rid}/report",
                          json={"reason": "TEST_iter5 spam"}, headers=_h(ctok), timeout=30)

            # reviews count went up
            vs_mid = requests.get(f"{API}/vehicles", timeout=30).json()
            veh_mid = next(v for v in vs_mid if v["id"] == vid)
            assert int(veh_mid.get("reviews", 0)) == reviews_before + 1

            # Admin delete
            dl = requests.post(f"{API}/admin/reviews/{rid}/delete", headers=_h(atok), timeout=30)
            assert dl.status_code == 200

            # review no longer exists
            async def gone():
                return await db.reviews.find_one({"_id": ObjectId(rid)})
            assert loop.run_until_complete(gone()) is None

            # Vehicle reviews count back to before
            vs_after = requests.get(f"{API}/vehicles", timeout=30).json()
            veh_after = next(v for v in vs_after if v["id"] == vid)
            assert int(veh_after.get("reviews", 0)) == reviews_before, \
                f"reviews count should be {reviews_before}, got {veh_after.get('reviews')}"

            rid = None  # already deleted
        finally:
            async def cleanup():
                if rid:
                    await db.reviews.delete_one({"_id": ObjectId(rid)})
                if bid:
                    await db.bookings.delete_one({"_id": ObjectId(bid)})
                await db.reviews.delete_many({"text": {"$regex": "^TEST_iter5"}})
                await db.bookings.delete_many({"ref": {"$regex": "^TEST-"}})
            try: loop.run_until_complete(cleanup())
            finally: loop.close()

    def test_report_404_on_unknown_review(self, client_ctx):
        tok, _ = client_ctx
        r = requests.post(f"{API}/reviews/{ObjectId()}/report",
                          json={"reason": "x"}, headers=_h(tok), timeout=30)
        assert r.status_code == 404


# ---------- Regression: providers map + lavage/bordeaux still fine ----------
class TestRegression:
    def test_providers_lavage_bordeaux(self):
        arr = requests.get(f"{API}/providers", params={"type": "LAVAGE"}, timeout=30).json()
        assert any(p.get("city", "").lower() == "bordeaux" for p in arr)

    def test_vehicles_endpoint(self):
        r = requests.get(f"{API}/vehicles", timeout=30)
        assert r.status_code == 200 and isinstance(r.json(), list)

    def test_owner_mine_reviews(self, owner_ctx):
        tok, _ = owner_ctx
        r = requests.get(f"{API}/reviews/owner/mine", headers=_h(tok), timeout=30)
        assert r.status_code == 200
