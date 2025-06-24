from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, abort, flash
from flask_login import current_user
from db import mongo_db
from datetime import datetime, timezone
import math

vacation_bp = Blueprint("vacation", __name__, url_prefix="/hr/vacation")

def get_vacation_collection():
    return mongo_db["vacation"]

# 휴가 신청목록 화면 (연차 계산 로직 수정)
@vacation_bp.route("/list", methods=["GET"])
def show_list():
    PAGE_SIZE = 10
    try: page = int(request.args.get('page', 1))
    except (TypeError, ValueError): page = 1
    skip_count = (page - 1) * PAGE_SIZE

    query = {"user_id": ObjectId(current_user.id)}
    total_vacations = get_vacation_collection().count_documents(query)
    total_pages = math.ceil(total_vacations / PAGE_SIZE)
    vacations = list(get_vacation_collection().find(query).sort("created_at", -1).skip(skip_count).limit(PAGE_SIZE))

    # --- 남은 연차 계산 로직 (전체 수정) ---
    
    # 해결 1: DB에서 직접 사용자 정보를 가져와 총 연차일수 설정 
    user = mongo_db.hr.find_one({"_id": ObjectId(current_user.id)})
    total_leave_days = user.get("annual_leave_days", 0) if user else 0

    # 3. 사용한 연차 일수를 계산합니다.
    used_leave_days = 0
    
    # 해결 2: '반차'는 0.5일로, '연차'는 기간으로 계산하도록 파이프라인 수정
    pipeline = [
        {
            "$match": {
                "user_id": ObjectId(current_user.id),
                "status": "승인",
                "vacation_type": {"$in": ["연차", "반차"]} # 연차와 반차 모두 포함
            }
        },
        {
            "$project": {
                "days_used": {
                    # $cond: if (vacation_type == "반차") then 0.5 else (날짜 계산)
                    "$cond": {
                        "if": {"$eq": ["$vacation_type", "반차"]},
                        "then": 0.5,
                        "else": {
                            "$add": [
                                {"$divide": [
                                    {"$subtract": [
                                        {"$dateFromString": {"dateString": "$end_date"}},
                                        {"$dateFromString": {"dateString": "$start_date"}}
                                    ]},
                                    1000 * 60 * 60 * 24
                                ]},
                                1
                            ]
                        }
                    }
                }
            }
        },
        {
            "$group": {
                "_id": None,
                "total_used": {"$sum": "$days_used"}
            }
        }
    ]

    result = list(get_vacation_collection().aggregate(pipeline))
    if result:
        used_leave_days = result[0]['total_used']

    # 4. 남은 연차를 계산합니다.
    remaining_days = total_leave_days - used_leave_days
    # 남은 연차 계산 로직 끝

    return render_template("hr/vc_list.html", 
                        vacations=vacations, 
                        remaining_days=remaining_days,
                        total_leave_days=total_leave_days,
                        total_pages=total_pages,
                        current_page=page,
                        total_vacations=total_vacations,
                        page_size=PAGE_SIZE)

@vacation_bp.route("/apply", methods=["GET"])
def apply_form():
    return render_template("hr/vc_apply.html")

@vacation_bp.route("/apply", methods=["POST"])
def apply_vacation():
    vacation_type = request.form["vacation_type"]; start_date = request.form["start_date"]
    end_date = request.form["end_date"]; reason = request.form["reason"]
    if start_date > end_date:
        flash("시작일은 종료일보다 늦을 수 없습니다.", "error")
        return redirect(url_for("vacation.apply_form"))
    new_vacation = {
        "user_id": ObjectId(current_user.id), "vacation_type": vacation_type,
        "start_date": start_date, "end_date": end_date, "reason": reason,
        "status": "대기", "created_at": datetime.now(timezone.utc)
    }
    get_vacation_collection().insert_one(new_vacation)
    flash("휴가 신청이 완료되었습니다.", "success")
    return redirect(url_for("vacation.show_list"))

@vacation_bp.route("/edit/<vacation_id>", methods=["GET"])
def edit_form(vacation_id):
    vacation = get_vacation_collection().find_one({"_id": ObjectId(vacation_id), "user_id": ObjectId(current_user.id)})
    if not vacation or vacation.get('status') != '대기':
        flash("수정할 수 없는 휴가 신청입니다.", "error")
        return redirect(url_for("vacation.show_list"))
    return render_template("hr/vc_edit.html", vacation=vacation)

@vacation_bp.route("/edit/<vacation_id>", methods=["POST"])
def edit_vacation(vacation_id):
    vacation_type = request.form["vacation_type"]; start_date = request.form["start_date"]
    end_date = request.form["end_date"]; reason = request.form["reason"]
    if start_date > end_date:
        flash("시작일은 종료일보다 늦을 수 없습니다.", "error")
        return redirect(url_for("vacation.edit_form", vacation_id=vacation_id))
    update_data = {
        "vacation_type": vacation_type, "start_date": start_date,
        "end_date": end_date, "reason": reason, "updated_at": datetime.now(timezone.utc)
    }
    result = get_vacation_collection().update_one(
        {"_id": ObjectId(vacation_id), "user_id": ObjectId(current_user.id), "status": "대기"},
        {"$set": update_data}
    )
    if result.matched_count == 0: abort(404)
    flash("휴가 신청이 수정되었습니다.", "success")
    return redirect(url_for("vacation.show_list"))

@vacation_bp.route("/delete/<vacation_id>", methods=["POST"])
def delete_vacation(vacation_id):
    result = get_vacation_collection().delete_one({
        "_id": ObjectId(vacation_id), "user_id": ObjectId(current_user.id), "status": "대기"
    })
    if result.deleted_count == 0:
        flash("삭제할 수 없는 휴가 신청입니다.", "error")
        return redirect(url_for("vacation.show_list"))
    flash("휴가 신청이 삭제되었습니다.", "success")
    return redirect(url_for("vacation.show_list"))