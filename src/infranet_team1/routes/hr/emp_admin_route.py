from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, abort, flash
from flask_login import current_user
from db import mongo_db
from datetime import datetime
import bcrypt
import math

from extension import get_fs
from werkzeug.utils import secure_filename

emp_admin_bp = Blueprint("emp_admin", __name__, url_prefix="/hr/emp")

def get_hr_collection():
    return mongo_db["hr"]

@emp_admin_bp.route("/list", methods=["GET"])
def employee_list():
    page_size = 15
    page = request.args.get('page', 1, type=int)
    skip_count = (page - 1) * page_size
    search_category = request.args.get('search_category', 'name')
    search_keyword = request.args.get('search_keyword', '')
    search_status = request.args.get('status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    query = {}
    if search_keyword: query[search_category] = {"$regex": search_keyword, "$options": "i"}
    if search_status: query["status"] = search_status
    date_query = {}
    if start_date: date_query["$gte"] = datetime.strptime(start_date, "%Y-%m-%d")
    if end_date: date_query["$lte"] = datetime.strptime(end_date, "%Y-%m-%d")
    if date_query: query["hire_date"] = date_query
    total_records = get_hr_collection().count_documents(query)
    total_pages = math.ceil(total_records / page_size)
    employees = list(get_hr_collection().find(query).sort("hire_date", -1).skip(skip_count).limit(page_size))
    return render_template("hr/emp_admin_list.html", employees=employees, search_category=search_category, search_keyword=search_keyword,
                        search_status=search_status, start_date=start_date, end_date=end_date, total_pages=total_pages,
                        current_page=page, total_records=total_records, page_size=page_size)

# 직원 수정 폼 (GET) - 부서/직위 목록 전달
@emp_admin_bp.route("/detail/<employee_id>", methods=["GET"])
def employee_edit_form(employee_id):
    if current_user.role not in ["admin", "system"]: abort(403)
    employee = get_hr_collection().find_one({"_id": ObjectId(employee_id)})
    if not employee: abort(404)

    #  DB에서 고유한 부서/직위 목록 가져오기 
    all_departments = get_hr_collection().distinct("department")
    all_positions = get_hr_collection().distinct("position")
    
    # 빈 값 제거 및 정렬
    departments = sorted([d for d in all_departments if d])
    positions = sorted([p for p in all_positions if p])

    return render_template(
        "hr/emp_admin_detail.html", 
        employee=employee,
        departments=departments, # 부서 목록 전달
        positions=positions      # 직위 목록 전달
    )

@emp_admin_bp.route("/detail/<employee_id>", methods=["POST"])
def employee_edit_submit(employee_id):
    if current_user.role not in ["admin", "system"]: abort(403)
    employee = get_hr_collection().find_one({"_id": ObjectId(employee_id)})
    if not employee: abort(404)
    update_data = {
        "name": request.form["name"], "email": request.form["email"], "position": request.form["position"],
        "job_title": request.form.get("job_title"), "department": request.form["department"], "phone": request.form["phone"],
        "hire_date": datetime.strptime(request.form["hire_date"], "%Y-%m-%d") if request.form.get("hire_date") else None,
        "status": request.form["status"], "role": request.form["role"],
        "annual_leave_days": int(request.form.get("annual_leave_days", 15)), "updated_at": datetime.now()
    }
    fs = get_fs()

    # --- 프로필 이미지 처리 로직 (수정) ---
    remove_image_flag = request.form.get('remove_profile_image')
    new_image_file = request.files.get('profile_image')

    # 1. 새 이미지가 업로드된 경우
    if new_image_file and new_image_file.filename != '':
        # 기존 이미지가 있으면 삭제
        if employee.get('profile_image_id'):
            try: fs.delete(ObjectId(employee['profile_image_id']))
            except Exception as e: print(f"기존 파일 삭제 실패: {e}")
        # 새 이미지 저장
        filename = secure_filename(new_image_file.filename)
        file_id = fs.put(new_image_file, filename=filename, content_type=new_image_file.content_type)
        update_data['profile_image_id'] = file_id
    
    # 2. '기본 이미지로 재설정'이 체크된 경우 (단, 새 이미지가 업로드되지 않았을 때)
    elif remove_image_flag:
        # 기존 이미지가 있으면 삭제
        if employee.get('profile_image_id'):
            try: fs.delete(ObjectId(employee['profile_image_id']))
            except Exception as e: print(f"기존 파일 삭제 실패: {e}")
        # DB에서 이미지 ID 필드를 null로 설정
        update_data['profile_image_id'] = None
    # --- 프로필 이미지 처리 로직 끝 ---

    if request.form.get("password"):
        password_plain = request.form["password"].encode("utf-8")
        update_data["password"] = bcrypt.hashpw(password_plain, bcrypt.gensalt())
    
    get_hr_collection().update_one({"_id": ObjectId(employee_id)}, {"$set": update_data})
    
    flash("✅ 직원 정보가 성공적으로 수정되었습니다.")
    return redirect(url_for("emp_admin.employee_list"))


# 신규 등록 폼 (GET) - 부서/직위 목록 전달
@emp_admin_bp.route("/new", methods=["GET"])
def employee_create_form():
    #  DB에서 고유한 부서/직위 목록 가져오기 
    all_departments = get_hr_collection().distinct("department")
    all_positions = get_hr_collection().distinct("position")

    # 빈 값 제거 및 정렬
    departments = sorted([d for d in all_departments if d])
    positions = sorted([p for p in all_positions if p])

    return render_template(
        "hr/emp_admin_detail.html", 
        employee=None,
        departments=departments, # 부서 목록 전달
        positions=positions      # 직위 목록 전달
    )

@emp_admin_bp.route("/new", methods=["POST"])
def employee_create():
    if current_user.role not in ["admin", "system"]: abort(403)
    password_plain = request.form["password"].encode("utf-8")
    employee_data = {
        "name": request.form["name"], "email": request.form["email"], "password": bcrypt.hashpw(password_plain, bcrypt.gensalt()),
        "position": request.form.get("position"), "job_title": request.form.get("job_title"),
        "department": request.form.get("department"), "phone": request.form.get("phone"),
        "hire_date": datetime.strptime(request.form["hire_date"], "%Y-%m-%d") if request.form.get("hire_date") else None,
        "status": request.form["status"], "role": request.form["role"],
        "annual_leave_days": int(request.form.get("annual_leave_days", 15)),
        "created_at": datetime.now(), "updated_at": datetime.now(), "profile_image_id": None
    }
    if 'profile_image' in request.files:
        file = request.files['profile_image']
        if file and file.filename != '':
            fs = get_fs()
            filename = secure_filename(file.filename)
            file_id = fs.put(file, filename=filename, content_type=file.content_type)
            employee_data['profile_image_id'] = file_id
    get_hr_collection().insert_one(employee_data)
    flash("✅ 새로운 직원이 등록되었습니다.")
    return redirect(url_for("emp_admin.employee_list"))

@emp_admin_bp.route("/deactivate/<employee_id>", methods=["POST"])
def employee_deactivate(employee_id):
    if current_user.role not in ["admin", "system"]: abort(403)
    try:
        result = get_hr_collection().update_one(
            {"_id": ObjectId(employee_id)}, {"$set": {"status": "퇴사", "updated_at": datetime.now()}}
        )
        if result.matched_count == 0: abort(404)
        flash("🚫 직원이 비활성화(퇴사) 처리되었습니다.")
    except Exception as e: flash(f"처리 중 오류가 발생했습니다: {e}", "error")
    return redirect(url_for("emp_admin.employee_list"))