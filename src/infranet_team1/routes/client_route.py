from datetime import datetime
from flask import Blueprint, redirect, render_template, request, url_for
from bson.objectid import ObjectId
from db import mongo

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


from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, Field, field_validator

def objectid_str(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

class Attachment(BaseModel):
    file_id: ObjectId = Field(...)
    file_name: str
    uploaded_at: Optional[datetime]

    @field_validator("file_id", mode="before")
    @classmethod
    def validate_file_id(cls, v):
        if isinstance(v, ObjectId):
            return v
        return ObjectId(str(v))

    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {
            ObjectId: objectid_str,
            datetime: lambda v: v.isoformat() if v else None,
        },
    }

class Contract(BaseModel):
    status: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]

    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {
            ObjectId: objectid_str,
            datetime: lambda v: v.isoformat() if v else None,
        },
    }

class Client(BaseModel):
    id: ObjectId = Field(default_factory=ObjectId, alias="_id")
    company_name: str
    department: str
    contact_person: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    tech_stack: List[str] = []
    notes: Optional[str] = ""
    contract: Contract
    contract_file_id: Optional[ObjectId] = None
    attachments: List[Attachment] = []

    @field_validator("id", "contract_file_id", mode="before")
    @classmethod
    def validate_objectid(cls, v):
        if v is None:
            return None
        if isinstance(v, ObjectId):
            return v
        return ObjectId(str(v))

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            ObjectId: objectid_str,
            datetime: lambda v: v.isoformat() if v else None,
        },
    }


@client_bp.route("/list", methods=['GET'])
def show_list():
    search = request.args.get("search", "").strip()
    query = {"$or": [
        {"company_name": {"$regex": search, "$options": "i"}},
        {"department": {"$regex": search, "$options": "i"}}
    ]} if search else {}

    docs = mongo.db.clients.find(query)
    clients = [Client(**doc) for doc in docs]
    return render_template("client/list.html", clients=clients, search=search)


@client_bp.route("/<id>", methods=['GET'])
def detail(id):
    try:
        obj_id = ObjectId(id)
    except Exception:
        return "잘못된 ID 형식입니다.", 400

    doc = mongo.db.clients.find_one({"_id": obj_id})
    if not doc:
        return "해당 고객을 찾을 수 없습니다.", 404

    client = Client(**doc)
    return render_template("client/detail.html", client=client)