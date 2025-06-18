from flask import Blueprint, render_template
from db import mongo

hr_bp = Blueprint("hr", __name__)

# {
#   "_id": ObjectId,
#   "name": "홍길동",
#   "email": "hong@example.com",
#   "password": "bcrypt 해시된 비밀번호",
#   "position": "개발자",
#   "department": "IT팀",
#   "phone": "010-1234-5678",
#   "hire_date": ISODate,
#   "status": "재직중" | "퇴사",
#   "role": "user" | "admin",
#   "created_at": ISODate,
#   "updated_at": ISODate
# }

@hr_bp.route("/")
def home():
    return render_template("hr/index.html")