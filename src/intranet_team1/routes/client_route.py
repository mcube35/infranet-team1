from datetime import datetime, timezone
import io
import logging
import mimetypes
from flask import Blueprint, redirect, render_template, request, url_for, flash, send_file, jsonify
from bson.objectid import ObjectId
from bson.errors import InvalidId
from extension import get_fs
from db import mongo_db
from datetime import datetime, timedelta
import logging

client_bp = Blueprint("client", __name__, url_prefix="/client")
fs = get_fs()

# ========== 🔧 유틸 함수 ==========
def get_clients_collection():
    return mongo_db["clients"]

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except (TypeError, ValueError) as e:
        logging.warning(f"날짜 파싱 실패: {date_str} -> {e}")
        return None

def save_files(files):
    """여러 파일 저장 후 메타정보 반환"""
    saved = []
    for file in files:
        if file and file.filename:
            file_id = fs.put(file, filename=file.filename, content_type=file.content_type)
            saved.append({
                "file_id": file_id,
                "file_name": file.filename,
                "uploaded_at": datetime.now(timezone.utc)
            })
    return saved

# ========== ✅ 고객사 등록 ==========
@client_bp.route("/create", methods=["GET"])
def create_form():
    return render_template("client/create.html")

from flask import request, redirect, url_for, flash, render_template
from datetime import datetime

@client_bp.route("/create", methods=["POST"])
def create():
    form = request.form

    # 계약 시작일과 종료일 필수값 검증
    start_date_raw = form.get("contract_start_date", "").strip()
    end_date_raw = form.get("contract_end_date", "").strip()

    if not start_date_raw or not end_date_raw:
        flash("계약 시작일과 종료일을 모두 입력해야 합니다.", "error")
        return redirect(request.url)

    try:
        start_date = parse_date(start_date_raw)
        end_date = parse_date(end_date_raw)
    except ValueError:
        flash("계약 날짜 형식이 올바르지 않습니다.", "error")
        return redirect(request.url)

    contract_files = save_files(request.files.getlist("contract_files"))

    client_doc = {
        "company_name": form.get("company_name", "").strip(),
        "department": form.get("department", "").strip(),
        "contact_person": form.get("contact_person", "").strip(),
        "phone": form.get("phone", "").strip(),
        "email": form.get("email", "").strip(),
        "tech_stack": [s.strip() for s in form.get("tech_stack", "").split(",") if s.strip()],
        "notes": form.get("notes", "").strip(),
        "contract": {
            "status": form.get("contract_status"),
            "start_date": start_date,
            "end_date": end_date
        },
        "contract_files": contract_files,
        "attachments": save_files(request.files.getlist("attachments"))
    }

    get_clients_collection().insert_one(client_doc)
    flash("고객사 등록이 완료되었습니다.", "success")
    return redirect(url_for("client.show_list"))


# ========== ✅ 고객사 목록 ==========
@client_bp.route("/list", methods=["GET"])
def show_list():
    search = request.args.get("search", "").strip()
    query = {
        "$or": [
            {"company_name": {"$regex": search, "$options": "i"}},
            {"department": {"$regex": search, "$options": "i"}},
            {"contact_person": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]
    } if search else {}

    pipeline = [
        {"$match": query},
        {"$addFields": {
            "status_order": {
                "$cond": [{"$eq": ["$contract.status", "Active"]}, 0, 1]
            }
        }},
        {"$sort": {"status_order": 1, "_id": -1}}
    ]

    docs = list(get_clients_collection().aggregate(pipeline))

    now = datetime.now()
    for doc in docs:
        contract = doc.get("contract", {})
        end_date_raw = contract.get("end_date")

        if isinstance(end_date_raw, str):
            end_date = parse_date(end_date_raw)
        elif isinstance(end_date_raw, datetime):
            end_date = end_date_raw
        else:
            end_date = None

        if end_date:
            if end_date < now:
                contract["highlight"] = "expired"
            elif end_date - now <= timedelta(days=7):
                contract["highlight"] = "soon"
            else:
                contract["highlight"] = "normal"
        else:
            contract["highlight"] = "unknown"

    return render_template("client/list.html", clients=docs, search=search)

# ========== ✅ 고객사 상세 ==========
@client_bp.route("/<id>", methods=["GET"])
def detail(id):
    try:
        doc = get_clients_collection().find_one({"_id": ObjectId(id)})
    except InvalidId:
        return "유효하지 않은 ID입니다.", 400
    if not doc:
        return "해당 고객을 찾을 수 없습니다.", 404
    return render_template("client/detail.html", client_doc=doc)

# ========== ✅ 고객사 수정 ==========
@client_bp.route("/<id>/edit", methods=["GET"])
def edit_form(id):
    collection = get_clients_collection()
    try:
        client_doc = collection.find_one({"_id": ObjectId(id)})
    except InvalidId:
        return "유효하지 않은 ID입니다.", 400
    if not client_doc:
        return "해당 고객을 찾을 수 없습니다.", 404
    return render_template("client/edit.html", client_doc=client_doc)

@client_bp.route("/<id>/edit", methods=["POST"])
def edit(id):
    collection = get_clients_collection()
    try:
        client_doc = collection.find_one({"_id": ObjectId(id)})
    except InvalidId:
        return "유효하지 않은 ID입니다.", 400
    if not client_doc:
        return "해당 고객을 찾을 수 없습니다.", 404

    form = request.form
    updated_doc = {
        "company_name": form.get("company_name", "").strip(),
        "department": form.get("department", "").strip(),
        "contact_person": form.get("contact_person", "").strip(),
        "phone": form.get("phone", "").strip(),
        "email": form.get("email", "").strip(),
        "tech_stack": [s.strip() for s in form.get("tech_stack", "").split(",") if s.strip()],
        "notes": form.get("notes", "").strip(),
        "contract": {
            "status": form.get("contract_status"),
            "start_date": parse_date(form.get("contract_start_date")),
            "end_date": parse_date(form.get("contract_end_date"))
        }
    }

    delete_contract_ids = request.form.getlist("delete_contract_file_ids")
    contract_files = client_doc.get("contract_files", [])
    contract_files = [f for f in contract_files if str(f["file_id"]) not in delete_contract_ids]
    contract_files += save_files(request.files.getlist("contract_files"))
    updated_doc["contract_files"] = contract_files

    delete_ids = request.form.getlist("delete_file_ids")
    attachments = client_doc.get("attachments", [])
    attachments = [f for f in attachments if str(f["file_id"]) not in delete_ids]
    attachments += save_files(request.files.getlist("attachments"))
    updated_doc["attachments"] = attachments

    collection.update_one({"_id": ObjectId(id)}, {"$set": updated_doc})
    flash("고객사 정보가 수정되었습니다.", "success")
    return redirect(url_for("client.detail", id=id))

# ========== ✅ 고객사 삭제 ==========
@client_bp.route("/<id>/delete", methods=["POST"])
def delete(id):
    collection = get_clients_collection()
    try:
        client_doc = collection.find_one({"_id": ObjectId(id)})
    except InvalidId:
        return "유효하지 않은 ID입니다.", 400
    if not client_doc:
        return "해당 고객을 찾을 수 없습니다.", 404

    for f in client_doc.get("contract_files", []):
        try:
            fs.delete(ObjectId(f["file_id"]))
        except Exception as e:
            logging.warning(f"계약서 파일 삭제 실패: {f['file_id']} -> {e}")

    for f in client_doc.get("attachments", []):
        try:
            fs.delete(ObjectId(f["file_id"]))
        except Exception as e:
            logging.warning(f"첨부파일 삭제 실패: {f['file_id']} -> {e}")

    collection.delete_one({"_id": ObjectId(id)})
    flash("고객사가 삭제되었습니다.", "info")
    return redirect(url_for("client.show_list"))

# ========== ✅ 계약서 미리보기 ==========
@client_bp.route("/files/preview/<file_id>", methods=["GET"])
def file_preview(file_id):
    try:
        file_obj = fs.get(ObjectId(file_id))
        mimetype = file_obj.content_type or mimetypes.guess_type(file_obj.filename)[0] or "application/octet-stream"
        return send_file(
            io.BytesIO(file_obj.read()),
            mimetype=mimetype,
            download_name=file_obj.filename or "preview",
            as_attachment=False
        )
    except Exception as e:
        logging.warning(f"파일 미리보기 실패: {file_id} -> {e}")
        return jsonify({"error": "파일을 찾을 수 없습니다."}), 404
