from datetime import datetime
from flask import Blueprint, redirect, render_template, request, url_for
from bson.objectid import ObjectId
from db import mongo_db

client_bp = Blueprint("client", __name__)

# client document 예시
# {
#   "_id": ObjectId("..."),
#   "company_name": "ABC Corp",
#   "department": "Sales",
#   "contact_person": "홍길동",
#   "phone": "010-1234-5678",
#   "email": "gildong@example.com",
#   "tech_stack": ["Python", "Flask", "MongoDB"],
#   "notes": "보안 이슈 주의 필요",
#   "contract": {
#     "status": "Active",
#     "start_date": ISODate("2024-01-01T00:00:00Z"),
#     "end_date": ISODate("2025-01-01T00:00:00Z")
#   },
#   "contract_file_id": ObjectId("60f5a3..."),
#   "attachments": [
#     {
#       "file_id": ObjectId("60f5a4..."),
#       "file_name": "report.pdf",
#       "uploaded_at": ISODate("2024-05-01T12:00:00Z")
#     },
#     {
#       "file_id": ObjectId("60f5a5..."),
#       "file_name": "presentation.pptx",
#       "uploaded_at": ISODate("2024-05-02T15:30:00Z")
#     }
#   ]
# }

def get_clients_collection():
    return mongo_db["clients"]

# 고객사 목록 리스트화면
@client_bp.route("/list", methods=['GET'])
def show_list():
    search = request.args.get("search", "").strip()
    query = {"$or": [
        {"company_name": {"$regex": search, "$options": "i"}},
        {"department": {"$regex": search, "$options": "i"}}
    ]} if search else {}

    docs = list(get_clients_collection().find(query))
    return render_template("client/list.html", clients=docs, search=search)

# 고객사 목록 상세보기
@client_bp.route("/<id>", methods=['GET'])
def detail(id):
    doc = get_clients_collection().find_one({"_id": ObjectId(id)})
    if not doc:
        return "해당 고객을 찾을 수 없습니다.", 404

    return render_template("client/detail.html", client_doc=doc)
