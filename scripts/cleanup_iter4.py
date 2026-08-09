"""Cleanup TEST_iter4 data + TEST bookings."""
import asyncio
from dotenv import dotenv_values
from motor.motor_asyncio import AsyncIOMotorClient

env = dotenv_values("/app/backend/.env")

async def main():
    db = AsyncIOMotorClient(env["MONGO_URL"])[env["DB_NAME"]]
    # Delete reviews
    r1 = await db.reviews.delete_many({"text": {"$regex": "^TEST_iter4"}})
    # Delete our TEST- bookings
    r2 = await db.bookings.delete_many({"ref": {"$regex": "^TEST-"}})
    # Recompute vehicle ratings for the affected vehicle
    from bson import ObjectId
    # Just recount for the BMW Série 5 owned by Sophie
    vs = await db.vehicles.find({}).to_list(500)
    for v in vs:
        revs = await db.reviews.find({"vehicleId": str(v["_id"])}).to_list(500)
        avg = round(sum(r.get("rating",0) for r in revs)/len(revs), 1) if revs else 0
        await db.vehicles.update_one({"_id": v["_id"]}, {"$set": {"reviews": len(revs), "rating": avg}})
    # Also cleanup any TEST_ user residue
    r3 = await db.users.delete_many({"email": {"$regex": "^TEST_"}})
    print("reviews deleted:", r1.deleted_count, "bookings:", r2.deleted_count, "users:", r3.deleted_count)

asyncio.run(main())
