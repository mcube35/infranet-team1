from flask import Blueprint, render_template
from db import mongo

# http://127.0.0.1:5000/client
client_bp = Blueprint("client", __name__)

# {
#   "_id": ObjectId,
#   "company_name": "ACME Corp",
#   "contact_person": "김철수",
#   "email": "contact@acme.com",
#   "phone": "02-123-4567",
#   "address": "서울특별시 강남구 ...",
#   "contract_start": ISODate,
#   "contract_end": ISODate,
#   "notes": "특이사항 기록",
#   "created_at": ISODate,
#   "updated_at": ISODate
# }

@client_bp.route("/")
def home():
    return render_template("client/index.html")