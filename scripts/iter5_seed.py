"""Seed a TEST booking for iter5 UI test. Usage: python iter5_seed.py <userId> <vehicleId> <ownerId>"""
import sys, asyncio, uuid
from datetime import date, timedelta, datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import dotenv_values

async def main(uid, vid, oid_):
    env = dotenv_values("/app/backend/.env")
    db = AsyncIOMotorClient(env["MONGO_URL"])[env["DB_NAME"]]
    doc = {
        "userId": uid, "vehicleId": vid, "ownerId": oid_,
        "vehicleTitle": "TEST veh iter5 UI",
        "frm": (date.today() - timedelta(days=10)).isoformat(),
        "to": (date.today() - timedelta(days=5)).isoformat(),
        "status": "confirmé",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "ref": "TEST-" + uuid.uuid4().hex[:6].upper(),
    }
    r = await db.bookings.insert_one(doc)
    print(str(r.inserted_id))

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
