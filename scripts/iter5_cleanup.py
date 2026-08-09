"""Cleanup iter5 TEST_ leftovers."""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import dotenv_values

async def main():
    env = dotenv_values("/app/backend/.env")
    db = AsyncIOMotorClient(env["MONGO_URL"])[env["DB_NAME"]]
    r1 = await db.reviews.delete_many({"text": {"$regex": "^TEST_iter5"}})
    r2 = await db.bookings.delete_many({"ref": {"$regex": "^TEST-"}})
    print(f"reviews deleted: {r1.deleted_count} ; bookings deleted: {r2.deleted_count}")

if __name__ == "__main__":
    asyncio.run(main())
