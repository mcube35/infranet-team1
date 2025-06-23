from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, abort, flash # flash 추가
from flask_login import current_user
from db import mongo_db
from datetime import datetime, timezone

vacation_bp = Blueprint("vacation", __name__, url_prefix="/hr/vacation")

def get_vacation_collection():
    return mongo_db["vacation"]

# 휴가 신청목록 화면
@vacation_bp.route("/list", methods=["GET"])
def show_list():
    # 1. 로그인한 유저의 전체 휴가 목록을 가져옵니다.
    query = {"user_id": ObjectId(current_user.id)}
    vacations = list(get_vacation_collection().find(query).sort("start_date", -1))

    # --- 남은 연차 계산 로직 시작 ---
    
    # 2. 유저의 총 연차 일수를 가져옵니다. (기본값: 0일)
    total_leave_days = getattr(current_user, "annual_leave_days", 0)


    # 3. 사용한 연차 일수를 계산합니다.
    used_leave_days = 0
    # Aggregation을 사용해 '승인' 상태의 '연차'만 필터링하고 날짜 차이를 계산합니다.
    pipeline = [
        {
            "$match": {
                "user_id": ObjectId(current_user.id),
                "status": "승인",
                "vacation_type": "연차"
            }
        },
        {
            "$project": {
                "days_diff": {
                    "$add": [
                        {
                            "$divide": [
                                {"$subtract": [
                                    {"$dateFromString": {"dateString": "$end_date"}},
                                    {"$dateFromString": {"dateString": "$start_date"}}
                                ]},
                                1000 * 60 * 60 * 24  # 밀리초를 일 단위로 변환
                            ]
                        },
                        1 # 시작일과 종료일이 같을 경우 1일이 되도록 1을 더함
                    ]
                }
            }
        },
        {
            "$group": {
                "_id": None,
                "total_used": {"$sum": "$days_diff"}
            }
        }
    ]

    result = list(get_vacation_collection().aggregate(pipeline))
    if result:
        used_leave_days = result[0]['total_used']

    # 4. 남은 연차를 계산합니다.
    remaining_days = total_leave_days - used_leave_days

    # --- 남은 연차 계산 로직 끝 ---

    # 5. 계산된 남은 연차를 템플릿으로 전달합니다.
    return render_template("hr/vc_list.html", 
                        vacations=vacations, 
                        remaining_days=remaining_days,
                        total_leave_days=total_leave_days)

# 휴가신청 화면
@vacation_bp.route("/apply", methods=["GET"])
def apply_form():
    return render_template("hr/vc_apply.html")

# 휴가신청 POST 처리
@vacation_bp.route("/apply", methods=["POST"])
def apply_vacation():
    vacation_type = request.form["vacation_type"]
    start_date = request.form["start_date"]
    end_date = request.form["end_date"]
    reason = request.form["reason"]

    # 날짜 유효성 검사 (시작일이 종료일보다 늦으면 안됨)
    if start_date > end_date:
        flash("시작일은 종료일보다 늦을 수 없습니다.", "error")
        return redirect(url_for("vacation.apply_form"))

    new_vacation = {
        "user_id": ObjectId(current_user.id),
        "vacation_type": vacation_type,
        "start_date": start_date,
        "end_date": end_date,
        "reason": reason,
        "status": "대기",
        "created_at": datetime.now(timezone.utc)
    }
    get_vacation_collection().insert_one(new_vacation)
    flash("휴가 신청이 완료되었습니다.", "success")
    return redirect(url_for("vacation.show_list"))

# 휴가 수정 폼 (GET)
@vacation_bp.route("/edit/<vacation_id>", methods=["GET"])
def edit_form(vacation_id):
    vacation = get_vacation_collection().find_one({"_id": ObjectId(vacation_id), "user_id": ObjectId(current_user.id)})
    if not vacation or vacation.get('status') != '대기':
        flash("수정할 수 없는 휴가 신청입니다.", "error")
        return redirect(url_for("vacation.show_list"))
    return render_template("hr/vc_edit.html", vacation=vacation)

# 휴가 수정 처리 (POST)
@vacation_bp.route("/edit/<vacation_id>", methods=["POST"])
def edit_vacation(vacation_id):
    vacation_type = request.form["vacation_type"]
    start_date = request.form["start_date"]
    end_date = request.form["end_date"]
    reason = request.form["reason"]

    if start_date > end_date:
        flash("시작일은 종료일보다 늦을 수 없습니다.", "error")
        return redirect(url_for("vacation.edit_form", vacation_id=vacation_id))

    update_data = {
        "vacation_type": vacation_type,
        "start_date": start_date,
        "end_date": end_date,
        "reason": reason,
        "updated_at": datetime.now(timezone.utc)
    }

    result = get_vacation_collection().update_one(
        {"_id": ObjectId(vacation_id), "user_id": ObjectId(current_user.id), "status": "대기"},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        abort(404)
    flash("휴가 신청이 수정되었습니다.", "success")
    return redirect(url_for("vacation.show_list"))

# 휴가 삭제
@vacation_bp.route("/delete/<vacation_id>", methods=["POST"]) # GET -> POST로 변경
def delete_vacation(vacation_id):
    result = get_vacation_collection().delete_one({
        "_id": ObjectId(vacation_id),
        "user_id": ObjectId(current_user.id),
        "status": "대기"
    })
    if result.deleted_count == 0:
        flash("삭제할 수 없는 휴가 신청입니다.", "error")
        return redirect(url_for("vacation.show_list"))
    
    flash("휴가 신청이 삭제되었습니다.", "success")
    return redirect(url_for("vacation.show_list"))