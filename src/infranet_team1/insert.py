from pymongo import MongoClient
from datetime import datetime
import bcrypt

client = MongoClient("mongodb://localhost:27017/")
db = client["infranet"]

password_plain = "123"
hashed_password = bcrypt.hashpw(password_plain.encode("utf-8"), bcrypt.gensalt())

hr_data = {
    "name": "mcube",
    "email": "mcube3575@gmail.com",
    "password": hashed_password,
    "position": "개발자",
    "department": "IT팀",
    "phone": "010-1234-5678",
    "hire_date": datetime(2023, 1, 1),
    "status": "재직중",
    "role": "admin",
    "created_at": datetime.now(),
    "updated_at": datetime.now()
}

result = db.hr.insert_one(hr_data)
print("Inserted ID:", result.inserted_id)