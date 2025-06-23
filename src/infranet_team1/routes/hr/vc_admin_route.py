from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, abort, flash
from flask_login import current_user
from db import mongo_db
from datetime import datetime, timezone

vacation_admin_bp = Blueprint("vacation_admin", __name__, url_prefix="/hr/vacation/admin")

def get_vacation_collection():
    return mongo_db["vacation"]

# 관리자 휴가 승인 대기 목록 페이지
@vacation_admin_bp.route("/list", methods=["GET"])
def admin_list():
    # ... (이전과 동일한 aggregation 파이프라인 코드) ...
    pipeline = [
        {"$match": {"status": "대기"}},
        {"$lookup": {"from": "hr", "localField": "user_id", "foreignField": "_id", "as": "user_info"}},
        {"$sort": {"created_at": -1}}
    ]
    vacations = list(get_vacation_collection().aggregate(pipeline))
    return render_template("hr/vc_admin_list.html", vacations=vacations)

# 휴가 승인 처리(POST)
@vacation_admin_bp.route("/approve/<vacation_id>", methods=["POST"])
def approve_vacation(vacation_id):
    result = get_vacation_collection().update_one(
        {"_id": ObjectId(vacation_id), "status": "대기"},
        {"$set": {"status": "승인", "approved_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        abort(404)
    flash("✅ 휴가 신청을 승인했습니다.")
    return redirect(url_for("vacation_admin.admin_list"))

# 휴가 거절 처리(POST)
@vacation_admin_bp.route("/reject/<vacation_id>", methods=["POST"])
def reject_vacation(vacation_id):
    result = get_vacation_collection().update_one(
        {"_id": ObjectId(vacation_id), "status": "대기"},
        {"$set": {"status": "거절", "rejected_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        abort(404)
    flash("❌ 휴가 신청을 거절했습니다.")
    return redirect(url_for("vacation_admin.admin_list"))