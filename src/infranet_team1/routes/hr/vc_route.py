from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import current_user
from db import mongo_db
from datetime import datetime, timezone

vacation_bp = Blueprint("vacation", __name__, url_prefix="/hr/vacation")

def get_vacation_collection():
    return mongo_db["vacation"]

# 휴가 신청목록 화면
@vacation_bp.route("/list", methods=["GET"])
def show_list():
    query = {"user_id": ObjectId(current_user.id)}
    vacations = list(get_vacation_collection().find(query).sort("start_date", -1))
    return render_template("hr/vc_list.html", vacations=vacations)

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
    return redirect(url_for("vacation.show_list"))
