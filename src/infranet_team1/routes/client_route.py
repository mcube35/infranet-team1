from datetime import datetime
import io
from flask import Blueprint, redirect, render_template, request, url_for, flash, send_file, jsonify
from bson.objectid import ObjectId
from extension import get_fs
from db import mongo_db


client_bp = Blueprint("client", __name__)
fs = get_fs()

# ========== 🔧 유틸 함수 ==========
def get_clients_collection():
    return mongo_db["clients"]

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None

def save_contract_files(files):
    """여러 계약서 파일 저장 후 메타정보 반환"""
    contract_files = []
    for file in files:
        if file and file.filename:
            file_id = fs.put(file, filename=file.filename, content_type=file.content_type)
            contract_files.append({
                "file_id": file_id,
                "file_name": file.filename,
                "uploaded_at": datetime.utcnow()
            })
    return contract_files

def save_attachments(files):
    """여러 첨부파일 저장 후 메타정보 반환"""
    attachments = []
    for file in files:
        if file and file.filename:
            file_id = fs.put(file, filename=file.filename, content_type=file.content_type)
            attachments.append({
                "file_id": file_id,
                "file_name": file.filename,
                "uploaded_at": datetime.utcnow()
            })
    return attachments

# ========== ✅ 고객사 등록 ==========
@client_bp.route("/create", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        form = request.form
        contract_files = save_contract_files(request.files.getlist("contract_files"))

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
                "start_date": parse_date(form.get("contract_start_date")),
                "end_date": parse_date(form.get("contract_end_date"))
            },
            "contract_files": contract_files,
            "attachments": save_attachments(request.files.getlist("attachments"))
        }

        get_clients_collection().insert_one(client_doc)
        flash("고객사 등록이 완료되었습니다.", "success")
        return redirect(url_for("client.show_list"))

    return render_template("client/create.html")

# ========== ✅ 고객사 목록 ==========
@client_bp.route("/list", methods=["GET"])
def show_list():
    search = request.args.get("search", "").strip()
    query = {
        "$or": [
            {"company_name": {"$regex": search, "$options": "i"}},
            {"department": {"$regex": search, "$options": "i"}}
        ]
    } if search else {}

    # pipeline을 이용한 정렬 (Active 먼저)
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
    return render_template("client/list.html", clients=docs, search=search)

# ========== ✅ 고객사 상세 ==========
@client_bp.route("/<id>", methods=["GET"])
def detail(id):
    doc = get_clients_collection().find_one({"_id": ObjectId(id)})
    if not doc:
        return "해당 고객을 찾을 수 없습니다.", 404
    return render_template("client/detail.html", client_doc=doc)

# ========== ✅ 고객사 수정 ==========
@client_bp.route("/<id>/edit", methods=["GET", "POST"])
def edit(id):
    collection = get_clients_collection()
    client_doc = collection.find_one({"_id": ObjectId(id)})
    if not client_doc:
        return "해당 고객을 찾을 수 없습니다.", 404

    if request.method == "POST":
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

        # 계약서 삭제
        delete_contract_ids = request.form.getlist("delete_contract_file_ids")
        contract_files = client_doc.get("contract_files", [])
        contract_files = [f for f in contract_files if str(f["file_id"]) not in delete_contract_ids]

        # 새 계약서 추가
        new_contract_files = save_contract_files(request.files.getlist("contract_files"))
        contract_files += new_contract_files
        updated_doc["contract_files"] = contract_files

        # 첨부파일 삭제
        delete_ids = request.form.getlist("delete_file_ids")
        attachments = client_doc.get("attachments", [])
        attachments = [f for f in attachments if str(f["file_id"]) not in delete_ids]

        # 첨부파일 추가
        new_files = request.files.getlist("attachments")
        attachments += save_attachments(new_files)
        updated_doc["attachments"] = attachments

        collection.update_one({"_id": ObjectId(id)}, {"$set": updated_doc})
        flash("고객사 정보가 수정되었습니다.", "success")
        return redirect(url_for("client.detail", id=id))

    return render_template("client/edit.html", client_doc=client_doc)


# ========== ✅ 고객사 삭제 ==========
@client_bp.route("/<id>/delete", methods=["POST"])
def delete(id):
    collection = get_clients_collection()
    client_doc = collection.find_one({"_id": ObjectId(id)})
    if not client_doc:
        return "해당 고객을 찾을 수 없습니다.", 404

    # 계약서 파일 제거
    for f in client_doc.get("contract_files", []):
        try:
            fs.delete(ObjectId(f["file_id"]))
        except:
            pass

    # 첨부파일 제거
    for f in client_doc.get("attachments", []):
        try:
            fs.delete(ObjectId(f["file_id"]))
        except:
            pass

    collection.delete_one({"_id": ObjectId(id)})
    flash("고객사가 삭제되었습니다.", "info")
    return redirect(url_for("client.show_list"))

# ========== ✅ 계약서 미리보기 ==========
@client_bp.route("/files/preview/<file_id>", methods=["GET"])
def file_preview(file_id):
    try:
        file_obj = fs.get(ObjectId(file_id))
        return send_file(
            io.BytesIO(file_obj.read()),
            mimetype=file_obj.content_type or "application/pdf",
            download_name=file_obj.filename or "preview",
            as_attachment=False
        )
    except Exception:
        return jsonify({"error": "파일을 찾을 수 없습니다."}), 404
