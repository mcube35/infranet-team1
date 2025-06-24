from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, abort, flash
from flask_login import current_user
from db import mongo_db
from datetime import datetime, timezone
import math # 페이지네이션 추가

vacation_admin_bp = Blueprint("vacation_admin", __name__, url_prefix="/hr/vacation/admin")

def get_vacation_collection():
    return mongo_db["vacation"]

# 관리자 휴가 목록 페이지 (대시보드 기능 추가)
@vacation_admin_bp.route("/list", methods=["GET"])
def admin_list():
    if current_user.role not in ['admin', 'system']:
        abort(403)

    page_size = 15
    try:
        page = request.args.get('page', 1, type=int)
    except (TypeError, ValueError):
        page = 1
    skip_count = (page - 1) * page_size

    # 1. 상태 필터링 기능 추가
    status_filter = request.args.get('status', '대기') # 기본값은 '대기'
    query = {}
    if status_filter != '전체':
        query['status'] = status_filter
    
    total_records = get_vacation_collection().count_documents(query)
    total_pages = math.ceil(total_records / page_size)

    pipeline = [
        {"$match": query},
        {"$lookup": {"from": "hr", "localField": "user_id", "foreignField": "_id", "as": "user_info"}},
        {"$sort": {"created_at": -1}},
        {"$skip": skip_count},
        {"$limit": page_size}
    ]
    vacations = list(get_vacation_collection().aggregate(pipeline))
    
    return render_template(
        "hr/vc_admin_list.html", 
        vacations=vacations,
        total_pages=total_pages,
        current_page=page,
        status_filter=status_filter,
        page_size=page_size, # No. 계산을 위해 추가
        total_records=total_records # No. 계산을 위해 추가
    )

# 휴가 승인 처리(POST) - 처리자 정보 기록 추가
@vacation_admin_bp.route("/approve/<vacation_id>", methods=["POST"])
def approve_vacation(vacation_id):
    if current_user.role not in ['admin', 'system']: abort(403)
    
    result = get_vacation_collection().update_one(
        {"_id": ObjectId(vacation_id), "status": "대기"},
        {"$set": {
            "status": "승인", 
            "approved_at": datetime.now(timezone.utc),
            "processed_by_id": ObjectId(current_user.id), # 처리자 ID 기록
            "processed_by_name": current_user.name # 처리자 이름 기록
        }}
    )
    if result.matched_count == 0: abort(404)
    flash("✅ 휴가 신청을 승인했습니다.")
    return redirect(request.referrer or url_for("vacation_admin.admin_list"))

# 휴가 거절 처리(POST) - 거절 사유 및 처리자 정보 기록 추가
@vacation_admin_bp.route("/reject/<vacation_id>", methods=["POST"])
def reject_vacation(vacation_id):
    if current_user.role not in ['admin', 'system']: abort(403)
    
    rejection_reason = request.form.get('rejection_reason', '사유 없음')

    result = get_vacation_collection().update_one(
        {"_id": ObjectId(vacation_id), "status": "대기"},
        {"$set": {
            "status": "거절", 
            "rejected_at": datetime.now(timezone.utc),
            "rejection_reason": rejection_reason, # 거절 사유 저장
            "processed_by_id": ObjectId(current_user.id), # 처리자 ID 기록
            "processed_by_name": current_user.name # 처리자 이름 기록
        }}
    )
    if result.matched_count == 0: abort(404)
    flash("❌ 휴가 신청을 거절했습니다.")
    return redirect(request.referrer or url_for("vacation_admin.admin_list"))

# 처리 취소(대기 상태로 되돌리기) 라우트
@vacation_admin_bp.route("/revert/<vacation_id>", methods=["POST"])
def revert_vacation_status(vacation_id):
    if current_user.role not in ['admin', 'system']:
        abort(403)

    # 처리 정보를 삭제하고 상태를 '대기'로 변경
    result = get_vacation_collection().update_one(
        {"_id": ObjectId(vacation_id)},
        {
            "$set": {"status": "대기"},
            # $unset을 사용하여 처리 관련 필드들을 완전히 제거
            "$unset": {
                "approved_at": "",
                "rejected_at": "",
                "rejection_reason": "",
                "processed_by_id": "",
                "processed_by_name": ""
            }
        }
    )

    if result.matched_count == 0:
        abort(404)
    
    flash("🔄 휴가 상태를 '대기'로 되돌렸습니다.")
    return redirect(request.referrer or url_for("vacation_admin.admin_list"))