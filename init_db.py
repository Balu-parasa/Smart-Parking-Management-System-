from pymongo import MongoClient
from werkzeug.security import generate_password_hash

# ------------------- Connect to MongoDB -------------------
client = MongoClient("mongodb://localhost:27017/")

# Create or access the database
db = client["parking_db"]

# Create collections explicitly (optional, MongoDB creates them automatically on first insert)
if "users" not in db.list_collection_names():
    db.create_collection("users")
    print("✅ Created collection: users")

if "bookings" not in db.list_collection_names():
    db.create_collection("bookings")
    print("✅ Created collection: bookings")

# ------------------- Insert Admin User -------------------
admin_email = "vaishnaviparasa@gmail.com"
existing_admin = db.users.find_one({"email": admin_email})

if not existing_admin:
    db.users.insert_one({
        "username": "Vaishnavi",
        "email": admin_email,
        "password": generate_password_hash("vyshu123"),
        "is_admin": True,
        "profile_pic": None
    })
    print("✅ Admin user created successfully!")
else:
    print("ℹ️ Admin user already exists in database.")

print("✅ Database initialization complete.")