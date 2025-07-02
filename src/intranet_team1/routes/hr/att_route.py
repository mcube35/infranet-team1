from bson.objectid import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
from flask_login import current_user
from db import mongo_db
import math

att_bp = Blueprint('att', __name__, url_prefix="/hr/att")

def get_att_collection():
    # 출결 컬렉션 (attendance) 반환
    return mongo_db["attendance"]

# 근태 목록 페이지 렌더링
@att_bp.route("/", methods=["GET"])
def show_list():
    # 페이지네이션 처리 및 출결 데이터 조회
    page_size = 15
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    skip_count = (page - 1) * page_size
    
    user_id = ObjectId(current_user.id)

    today_date_str = datetime.now().strftime('%Y-%m-%d')
    today_record = get_att_collection().find_one({"user_id": user_id, "date": today_date_str})

    first_day_of_month = datetime.today().replace(day=1).strftime('%Y-%m-%d')
    start_date_str = request.args.get('start_date', first_day_of_month) 
    end_date_str = request.args.get('end_date', datetime.today().strftime('%Y-%m-%d'))

    query = {
        "user_id": user_id,
        "date": {"$gte": start_date_str, "$lte": end_date_str}
    }

    total_records = get_att_collection().count_documents(query)
    total_pages = math.ceil(total_records / page_size)
    all_att_records = list(get_att_collection().find(query).sort("date", -1).skip(skip_count).limit(page_size))

    processed_records = []
    for rec in all_att_records:
        clock_in = rec.get('clock_in')
        clock_out = rec.get('clock_out')
        working_minutes = rec.get('working_minutes')
        working_time_str = '-'
        if working_minutes is not None:
            hours = working_minutes // 60
            minutes = working_minutes % 60
            working_time_str = f"{hours}시간 {minutes}분"

        processed_records.append({
            "_id": rec['_id'],
            "date": rec['date'],
            "clock_in": clock_in.strftime('%H:%M') if clock_in else '-',
            "clock_out": clock_out.strftime('%H:%M') if clock_out else '-',
            "working_time": working_time_str,
            "status": rec.get('status', '미기록'),
            "memo": rec.get('memo', '')
        })

    return render_template(
        "hr/attendance.html",
        today_record=today_record,
        records=processed_records,
        start_date=start_date_str,
        end_date=end_date_str,
        total_pages=total_pages,
        current_page=page
    )

# 출근-퇴근 시간 차이로 근무 시간(분) 계산
def calc_working_min(clock_in_dt, clock_out_dt):
    if not clock_in_dt or not clock_out_dt: return None
    duration = clock_out_dt - clock_in_dt
    total_minutes = int(duration.total_seconds() / 60)
    return max(0, total_minutes)

# 출근 시간 기준 지각 여부 판정
def get_att_status(clock_in_dt):
    if not clock_in_dt: return "결근"
    standard_in_time = clock_in_dt.replace(hour=9, minute=0, second=0, microsecond=0)
    return "지각" if clock_in_dt > standard_in_time else "정상"

# 출근 처리 (출근 시간 저장)
@att_bp.route("/clock_in", methods=["POST"])
def clock_in():
    now = datetime.now()
    today_date_str = now.strftime('%Y-%m-%d')
    existing_record = get_att_collection().find_one({"user_id": ObjectId(current_user.id), "date": today_date_str})

    if not existing_record:
        status = get_att_status(now)
        new_att_doc = {
            "user_id": ObjectId(current_user.id), "date": today_date_str, "clock_in": now, "clock_out": None,
            "working_minutes": None, "status": status, "memo": ""
        }
        get_att_collection().insert_one(new_att_doc)
    return redirect(url_for('att.show_list'))

# 퇴근 처리 (퇴근 시간 저장 및 근무 시간 계산)
@att_bp.route("/clock_out", methods=["POST"])
def clock_out():
    now = datetime.now()
    today_date_str = now.strftime('%Y-%m-%d')
    att_record = get_att_collection().find_one({"user_id": ObjectId(current_user.id), "date": today_date_str})

    if att_record and att_record.get('clock_in'):
        working_minutes = calc_working_min(att_record.get('clock_in'), now)
        get_att_collection().update_one(
            {"_id": att_record["_id"]},
            {"$set": {"clock_out": now, "working_minutes": working_minutes}}
        )
    return redirect(url_for('att.show_list'))

# 비고 저장 처리 (출결 기록 메모 저장)
@att_bp.route("/memo/<record_id>", methods=["POST"])
def save_memo(record_id):
    memo_text = request.form.get('memo', '')
    result = get_att_collection().update_one(
        {"_id": ObjectId(record_id), "user_id": ObjectId(current_user.id)},
        {"$set": {"memo": memo_text}}
    )
    if result.matched_count:
        flash(f"saved_{record_id}", "success")
    else:
        flash("비고를 저장하는 데 실패했습니다.", "error")
    
    page = request.args.get('page', 1)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    return redirect(url_for('att.show_list', page=page, start_date=start_date, end_date=end_date))
