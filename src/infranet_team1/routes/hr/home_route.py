from routes.hr.bp import hr_bp
from bson.objectid import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash


temp_employee_id = ObjectId("667104d496a7d575001a1c32")

# ===============================================
# 메인 대시보드 페이지 (URL: /hr/)
# ===============================================
@hr_bp.route("/")
def home():
    return render_template("hr/index.html")

# --- 인메모리 데이터 저장소 (실제 앱에서는 데이터베이스로 대체) ---
# 형식: {사용자_ID: [{"type": "check_in/check_out", "timestamp": datetime_객체}]}
att_records = {}

# 형식: {사용자_ID: {"name": "사용자 이름", "department": "부서", "position": "직위"}}
users = {
    "user1": {"name": "홍길동", "department": "개발팀", "position": "사원"},
    "user2": {"name": "김철수", "department": "인사팀", "position": "대리"},
    "admin": {"name": "관리자", "department": "경영지원팀", "position": "부장"}
}

# --- 근태 계산 유틸리티 함수 (간소화된 예시) ---
def calculate_att_summary(user_id):
    records = att_records.get(user_id, [])

    daily_logs = {} # {날짜: {'check_in': datetime, 'check_out': datetime}}
    for record in records:
        record_date = record['timestamp'].date()
        if record_date not in daily_logs:
            daily_logs[record_date] = {}
        daily_logs[record_date][record['type']] = record['timestamp']

    total_work_seconds = 0
    lates = 0
    early_leaves = 0
    # 간단화를 위해 결근은 실제 근무일을 알지 못하므로 정확히 계산하지 않습니다.
    # 여기서는 레코드에 없는 날짜를 잠재적 결근으로 간주할 수 있지만, 실제 시스템에서는 고정된 근무 일정이 필요합니다.

    # 이 사용자의 모든 기록된 날짜 가져오기
    recorded_dates = sorted(daily_logs.keys())

    # 각 기록된 날짜에 대해 계산
    for d in recorded_dates:
        day_info = daily_logs[d]
        check_in_time = day_info.get('check_in')
        check_out_time = day_info.get('check_out')

        if check_in_time and check_out_time:
            # 근무 시간 계산
            duration = check_out_time - check_in_time
            total_work_seconds += duration.total_seconds()

            # 지각 확인 (예: 오전 9시 이후 출근)
            if check_in_time.hour > 9 or (check_in_time.hour == 9 and check_in_time.minute > 0):
                lates += 1

            # 조퇴 확인 (예: 오후 6시 이전 퇴근)
            if check_out_time.hour < 18:
                early_leaves += 1
        # 특정 날짜에 출근 또는 퇴근만 있는 경우 미완료로 간주합니다.
        # 결근 계산은 더 복잡하며 일반적으로 근무 일정을 필요로 합니다.

    return {
        "total_work_hours": round(total_work_seconds / 3600, 2),
        "lates": lates,
        "early_leaves": early_leaves,
        "absences": 0 # 플레이스홀더: 더 복잡한 로직 필요
    }

# --- 라우트 ---
@hr_bp.route('/')
def index():
    # 메인 페이지의 프로필 섹션에 샘플 사용자 데이터를 전달
    return render_template('index.html', user_profile_data=users.get("user1"))

@hr_bp.route('/attendance')
def attendance():
    # 이 페이지는 개별 직원이 자신의 근태를 확인하고 출근/퇴근을 할 수 있는 페이지입니다.
    current_user_id = "user1" # 시연을 위해 user1이 로그인했다고 가정

    user_records = att_records.get(current_user_id, [])

    # 출근/퇴근 버튼 활성화 여부 결정
    has_checked_in_today = False
    last_record = user_records[-1] if user_records else None

    if last_record and last_record['timestamp'].date() == datetime.now().date():
        if last_record['type'] == 'check_in':
            has_checked_in_today = True

    # 개별 요약 계산
    summary = calculate_att_summary(current_user_id)

    return render_template('attendance.html',
                        user_name=users.get(current_user_id, {}).get('name', '알 수 없음'),
                        user_records=user_records,
                        has_checked_in_today=has_checked_in_today,
                        summary=summary)

@hr_bp.route('/att/check_in', methods=['POST'])
def check_in():
    current_user_id = "user1" # user1이 출근했다고 가정

    # 같은 날 중복 출근 방지
    if current_user_id not in att_records:
        att_records[current_user_id] = []

    last_record = att_records[current_user_id][-1] if att_records[current_user_id] else None
    if last_record and last_record['timestamp'].date() == datetime.now().date() and last_record['type'] == 'check_in':
        # 이미 오늘 출근했음
        pass
    else:
        att_records[current_user_id].append({
            "type": "check_in",
            "timestamp": datetime.now()
        })
    return redirect(url_for('attendance'))

@hr_bp.route('/attendance/check_out', methods=['POST'])
def check_out():
    current_user_id = "user1" # user1이 퇴근한다고 가정

    if current_user_id not in att_records:
        # 출근 기록이 없으므로 퇴근 불가
        return redirect(url_for('attendance'))

    last_record = att_records[current_user_id][-1] if att_records[current_user_id] else None

    # 마지막 행동이 같은 날 출근이었는지 확인
    if last_record and last_record['timestamp'].date() == datetime.now().date() and last_record['type'] == 'check_in':
        att_records[current_user_id].append({
            "type": "check_out",
            "timestamp": datetime.now()
        })
    return redirect(url_for('attendance'))

@hr_bp.route('/att/dashboard')
def attendance_dashboard():
    # 이 페이지는 관리자가 개요를 볼 수 있는 페이지입니다.
    # 실제 앱에서는 인증 및 권한 부여가 필요합니다.

    dashboard_summary = {}
    for user_id, user_data in users.items():
        if user_id == "admin": # 관리자 사용자는 일반 직원 목록에서 제외
            continue

        summary = calculate_att_summary(user_id)
        dashboard_summary[user_id] = {
            "name": user_data["name"],
            **summary # 요약 딕셔너리 언팩
        }

    return render_template('att_dashboard.html', dashboard_summary=dashboard_summary)
