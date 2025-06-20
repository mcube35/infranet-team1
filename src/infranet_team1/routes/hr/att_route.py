from bson.objectid import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for
from datetime import datetime
from flask_login import current_user
from db import mongo

att_bp = Blueprint('att', __name__, url_prefix="/hr/att")

def get_att_collection():
    return mongo.db.att

@att_bp.route("/", methods=["GET"])
def show_list():
    today_date_str = datetime.now().strftime('%Y-%m-%d')
    today_record = get_att_collection().find_one({"user_id": current_user.id, "date": today_date_str})

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    query = {"user_id": current_user.id}
    if start_date_str and end_date_str:
        query["date"] = {"$gte": start_date_str, "$lte": end_date_str}
    elif start_date_str:
        query["date"] = {"$gte": start_date_str}
    elif end_date_str:
        query["date"] = {"$lte": end_date_str}

    all_att_records = list(get_att_collection().find(query).sort("date", -1))

    processed_records = []
    for record in all_att_records:
        clock_in_dt = record.get('clock_in', None)
        clock_out_dt = record.get('clock_out', None)

        working_minutes = record.get('working_minutes')
        working_time_str = '-'
        if working_minutes is not None:
            hours = working_minutes // 60
            minutes = working_minutes % 60
            working_time_str = f"{hours}시간 {minutes}분"

        processed_records.append({
            "date": record['date'],
            "clock_in": clock_in_dt.strftime('%H:%M') if clock_in_dt else '-',
            "clock_out": clock_out_dt.strftime('%H:%M') if clock_out_dt else '-',
            "working_time": working_time_str,
            "status": record['status'],
            "memo": record.get('memo', '')
        })

    return render_template(
        "hr/attendance.html",
        today_record=today_record, # 오늘 기록 (출퇴근 버튼 활성화에 사용)
        records=processed_records, # 필터링 및 가공된 전체 기록
        start_date=start_date_str, # 필터링 시작 날짜 (HTML input 값 유지용)
        end_date=end_date_str # 필터링 종료 날짜 (HTML input 값 유지용)
    )


def calc_working_min(clock_in_dt, clock_out_dt):
    """
    출근 시간과 퇴근 시간을 기준으로 근무 시간을 분 단위로 계산합니다.
    """
    if not clock_in_dt or not clock_out_dt:
        return None

    duration = clock_out_dt - clock_in_dt
    total_minutes = int(duration.total_seconds() / 60)

    return max(0, total_minutes) # 근무 시간이 음수가 되지 않도록


def get_att_status(clock_in_dt):
    """
    출근 시간을 기준으로 '정상' 또는 '지각' 상태를 반환합니다.
    """

    if not clock_in_dt:
        return "결근"

    # 출근 기준 시간은 오전 9시로 고정합니다.
    standard_in_time = clock_in_dt.replace(hour=9, minute=0, second=0, microsecond=0)

    if clock_in_dt > standard_in_time:
        return "지각"
    else:
        return "정상"


# 출근하기 버튼 처리 POST
@att_bp.route("/clock_in", methods=["POST"])
def clock_in():
    now = datetime.now()
    today_date_str = now.strftime('%Y-%m-%d')

    # 오늘 사용자의 출근 기록이 있는지 확인
    existing_record = get_att_collection().find_one({"user_id": current_user.id, "date": today_date_str})

    if not existing_record:
        status = get_att_status(now) # 출근 시간에 따른 상태 결정
        if existing_record: # 날짜는 있지만 출근 기록이 없는 경우 (예: 전날 미퇴근 처리 후 다음날 출근)
            get_att_collection().update_one(
                {"_id": existing_record["_id"]},
                {"$set": {
                    "clock_in": now,
                    "status": status, # 출근 시 상태 업데이트
                }}
            )
        else: # 완전히 새로운 출근 기록
            new_att_doc = {
                "_id": ObjectId(), # 새로운 ObjectId 생성
                "user_id": current_user.id, # 현재 사용자의 ObjectId
                "date": today_date_str,
                "clock_in": now,
                "clock_out": None, # 퇴근 전이므로 None
                "working_minutes": None, # 퇴근 시 계산 예정
                "status": status,
                "memo": ""
            }
            get_att_collection().insert_one(new_att_doc)

    return redirect(url_for('att.show_list'))

# 퇴근하기 버튼 처리 POST
@att_bp.route("/clock_out", methods=["POST"])
def clock_out():
    now = datetime.now()
    today_date_str = now.strftime('%Y-%m-%d')

    # 오늘 사용자의 근태 기록을 찾아옴
    att_record = get_att_collection().find_one({"user_id": current_user.id, "date": today_date_str})

    if att_record.get('clock_in', None):
        clock_in_dt = att_record.get('clock_in', None)
        working_minutes = calc_working_min(clock_in_dt, now)

        # 퇴근 시 상태 업데이트는 출근 시 결정된 상태를 유지하는 것이 일반적입니다.
        # (예: 지각 상태로 출근했다면, 퇴근해도 여전히 '지각'입니다.)
        # 다만, '미퇴근' 상태로 남아있던 기록이 있었다면, 퇴근으로 인해 상태가 변경될 수 있습니다.
        # 여기서는 기본적으로 출근 시 결정된 상태를 유지하고,
        # 미퇴근 처리는 별도의 배치 작업이나 관리자 기능으로 처리하는 것을 권장합니다.

        get_att_collection().update_one(
            {"_id": att_record["_id"]},
            {
                "$set": {
                    "clock_out": now,
                    "working_minutes": working_minutes,
                    # "status": att_record.get('status') # 기존 상태 유지
                    # 만약 퇴근 시 특정 상태 변경 로직이 필요하면 여기에 추가
                } 
            }
        )
    return redirect(url_for('att.show_list'))

