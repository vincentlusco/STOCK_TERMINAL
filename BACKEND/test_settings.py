from app.settings import settings

def test_settings():
    print("Testing settings...")
    print(f"HOST: {settings.HOST}")
    print(f"PORT: {settings.PORT}")
    print(f"MONGO_URI: {settings.MONGO_URI}")
    print(f"DB_NAME: {settings.DB_NAME}")

if __name__ == "__main__":
    test_settings() 