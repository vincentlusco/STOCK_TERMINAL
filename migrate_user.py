import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
from datetime import datetime
from app.settings import settings

# Load environment variables
load_dotenv()

# User data from MongoDB
user_data = {
    "username": "Vincent",
    "email": "vlusco447@gmail.com",
    "hashed_password": "$2b$12$m3PtEwk/TpUmBIubitZ10usGLBNS5lxZ4JK6gUEBrNAWHkzO2UufG",
    "created_at": datetime.utcnow(),
    "watchlists": []
}

async def migrate_user():
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(settings.MONGO_URI)
        db = client[settings.DB_NAME]
        
        # Check if user already exists
        existing_user = await db[settings.USERS_COLLECTION].find_one(
            {"username": user_data['username']}
        )
        
        if existing_user is None:
            # Insert user
            result = await db[settings.USERS_COLLECTION].insert_one(user_data)
            print(f"User migrated successfully! ID: {result.inserted_id}")
        else:
            print("User already exists in MongoDB")

        print("Migration complete!")
        
    except Exception as e:
        print(f"Error during migration: {str(e)}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(migrate_user()) 