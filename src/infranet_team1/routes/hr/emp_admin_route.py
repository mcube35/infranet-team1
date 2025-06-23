from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, abort, flash
from flask_login import current_user
from db import mongo_db
from datetime import datetime
import bcrypt

# 파일 처리를 위한 모듈 추가
from gridfs import GridFS
from werkzeug.utils import secure_filename

emp_admin_bp = Blueprint("emp_admin", __name__, url_prefix="/hr/emp")

def get_hr_collection():
    return mongo_db["hr"]

# 직원 목록 페이지 (관리자 전용)
@emp_admin_bp.route("/list", methods=["GET"])
def employee_list():
    search_category = request.args.get('search_category', 'name')
    search_keyword = request.args.get('search_keyword', '')
    search_status = request.args.get('status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = {}

    if search_keyword:
        query[search_category] = {"$regex": search_keyword, "$options": "i"}

    if search_status:
        query["status"] = search_status

    date_query = {}
    if start_date:
        date_query["$gte"] = datetime.strptime(start_date, "%Y-%m-%d")
    if end_date:
        date_query["$lte"] = datetime.strptime(end_date, "%Y-%m-%d")
    
    if date_query:
        query["hire_date"] = date_query

    employees = list(mongo_db.hr.find(query).sort("created_at", -1))
    
    return render_template(
        "hr/emp_admin_list.html", 
        employees=employees,
        search_category=search_category,
        search_keyword=search_keyword,
        search_status=search_status,
        start_date=start_date,
        end_date=end_date
    )

# 직원 수정 폼 (GET)
@emp_admin_bp.route("/detail/<employee_id>", methods=["GET"])
def employee_edit_form(employee_id):
    if current_user.role not in ["admin", "system"]:
        abort(403)
    employee = mongo_db.hr.find_one({"_id": ObjectId(employee_id)})
    if not employee:
        abort(404)
    return render_template("hr/emp_admin_detail.html", employee=employee)

# 직원 수정 처리 (POST)
@emp_admin_bp.route("/detail/<employee_id>", methods=["POST"])
def employee_edit_submit(employee_id):
    if current_user.role not in ["admin", "system"]:
        abort(403)

    employee = mongo_db.hr.find_one({"_id": ObjectId(employee_id)})
    if not employee:
        abort(404)

    update_data = {
        "name": request.form["name"],
        "email": request.form["email"],
        "position": request.form["position"],
        "department": request.form["department"],
        "phone": request.form["phone"],
        "hire_date": datetime.strptime(request.form["hire_date"], "%Y-%m-%d") if request.form.get("hire_date") else None,
        "status": request.form["status"],
        "role": request.form["role"],
        "updated_at": datetime.now()
    }

    fs = GridFS(mongo_db)

    if 'profile_image' in request.files:
        file = request.files['profile_image']
        if file and file.filename != '':
            if employee.get('profile_image_id'):
                try:
                    fs.delete(ObjectId(employee['profile_image_id']))
                except Exception as e:
                    print(f"기존 파일 삭제 실패: {e}")

            filename = secure_filename(file.filename)
            file_id = fs.put(file, filename=filename, content_type=file.content_type)
            update_data['profile_image_id'] = file_id

    if request.form.get("password"):
        password_plain = request.form["password"].encode("utf-8")
        hashed_password = bcrypt.hashpw(password_plain, bcrypt.gensalt())
        update_data["password"] = hashed_password

    mongo_db.hr.update_one({"_id": ObjectId(employee_id)}, {"$set": update_data})
    # flash("직원 정보가 성공적으로 수정되었습니다.", "success")
    return redirect(url_for("emp_admin.employee_list"))

# 신규 등록 폼 (GET)
@emp_admin_bp.route("/new", methods=["GET"])
def employee_create_form():
    return render_template("hr/emp_admin_detail.html", employee=None)

# 신규 등록 처리 (POST)
@emp_admin_bp.route("/new", methods=["POST"])
def employee_create():
    if current_user.role not in ["admin", "system"]:
        abort(403)

    password_plain = request.form["password"].encode("utf-8")
    password = bcrypt.hashpw(password_plain, bcrypt.gensalt())
    
    employee_data = {
        "name": request.form["name"],
        "email": request.form["email"],
        "password": password,
        "position": request.form.get("position"),
        "department": request.form.get("department"),
        "phone": request.form.get("phone"),
        "hire_date": datetime.strptime(request.form["hire_date"], "%Y-%m-%d") if request.form.get("hire_date") else None,
        "status": request.form["status"],
        "role": request.form["role"],
        "annual_leave_days": 15,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "profile_image_id": None
    }

    if 'profile_image' in request.files:
        file = request.files['profile_image']
        if file and file.filename != '':
            fs = GridFS(mongo_db)
            filename = secure_filename(file.filename)
            file_id = fs.put(file, filename=filename, content_type=file.content_type)
            employee_data['profile_image_id'] = file_id

    mongo_db.hr.insert_one(employee_data)
    # flash("새로운 직원이 등록되었습니다.", "success")
    return redirect(url_for("emp_admin.employee_list"))

# ✅ 직원 비활성화(퇴사 처리) 라우트 추가
@emp_admin_bp.route("/deactivate/<employee_id>", methods=["POST"])
def employee_deactivate(employee_id):
    if current_user.role not in ["admin", "system"]:
        abort(403)
    
    try:
        result = mongo_db.hr.update_one(
            {"_id": ObjectId(employee_id)},
            {"$set": {
                "status": "퇴사",
                "updated_at": datetime.now()
            }}
        )
        if result.matched_count == 0:
            abort(404)
        
        # flash("직원 정보가 비활성화(퇴사) 처리되었습니다.", "success")
    except Exception as e:
        # flash(f"처리 중 오류가 발생했습니다: {e}", "error")
        pass

    return redirect(url_for("emp_admin.employee_list"))