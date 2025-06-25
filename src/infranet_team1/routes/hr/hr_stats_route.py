import bisect
import io
from flask import Blueprint, abort, render_template, send_file
from flask_login import current_user
from db import mongo_db
from datetime import date
from matplotlib.figure import Figure

hr_stats_bp = Blueprint("hr_stats", __name__, url_prefix="/hr/stats")

# MongoDB에서 특정 필드 기준으로 집계하여 카운트 리스트를 반환하는 함수
def count_by_field(group_field, *, match=None, date_format=None, limit=None):
    pipeline = []
    if match:
        pipeline.append({'$match': match})
    group_by = f"${group_field}"
    if date_format:
        date_field = f"{group_field}_str"
        pipeline.append({'$project': {date_field: {'$dateToString': {'format': date_format, 'date': group_by}}}})
        group_by = f"${date_field}"
    pipeline += [
        {'$group': {'_id': group_by, 'count': {'$sum': 1}}},
        {'$sort': {'_id' if date_format else 'count': -1}}
    ]
    if limit:
        pipeline.append({'$limit': limit})
    data = list(mongo_db.hr.aggregate(pipeline))
    if date_format:
        data.sort(key=lambda d: d['_id'])
    return data

# matplotlib로 차트(막대 또는 선)를 그리고 PNG 이미지로 반환하는 함수
def plot_chart(labels, values, *, chart_type='bar', title='', color='skyblue', ylabel='직원 수'):
    fig = Figure(figsize=(12, 6))
    ax = fig.subplots()

    if chart_type == 'bar':
        ax.bar(labels, values, color=color)
    elif chart_type == 'line':
        ax.plot(labels, values, marker='o', linestyle='-', color=color)
        ax.grid(True, linestyle='--', linewidth=0.5)

    ax.set_title(title)
    ax.set_ylabel(ylabel)
    
    ax.tick_params(axis='x', rotation=45)

    if values:
        ax.set_yticks(range(0, max(values) + 2))

    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    return send_file(img, mimetype='image/png')

# 집계 데이터를 가져와 차트를 생성하고 PNG 이미지로 반환하는 함수
def generate_chart(group_field, *, match=None, date_format=None, limit=None,
                   chart_type='bar', title='', color='skyblue', default_label='미지정'):
    data = count_by_field(group_field, match=match, date_format=date_format, limit=limit)
    if not data:
        return send_file(io.BytesIO(), mimetype='image/png')
    labels = [d['_id'] if d['_id'] else default_label for d in data]
    values = [d['count'] for d in data]
    return plot_chart(labels, values, chart_type=chart_type, title=title, color=color)

# 요청 시 관리자 권한 확인, 아니면 403 에러 반환하는 before_request 훅
@hr_stats_bp.before_request
def check_admin():
    if current_user.role not in ['admin', 'system']:
        abort(403)

# HR 통계 대시보드 메인 페이지 렌더링 - 전체, 재직, 휴직, 퇴사 직원 수 통계 제공
@hr_stats_bp.route("/")
def dashboard():
    total_employees = mongo_db.hr.count_documents({})
    active_employees = mongo_db.hr.count_documents({"status": "재직중"})
    on_leave_employees = mongo_db.hr.count_documents({"status": "휴직"})
    resigned_employees = mongo_db.hr.count_documents({"status": "퇴사"})
    return render_template("hr/hr_stats.html", 
                        total_employees=total_employees, active_employees=active_employees,
                        on_leave_employees=on_leave_employees, resigned_employees=resigned_employees)

# 재직 중인 직원들을 부서별로 집계해 막대차트 PNG로 반환
@hr_stats_bp.route("/charts/employees_by_department.png")
def chart_employees_by_department():
    return generate_chart(
        group_field="department",
        match={"status": "재직중"},
        title="부서별 직원 수 (재직중)",
        color="skyblue"
    )

# 재직 중인 직원들을 직급별로 집계해 막대차트 PNG로 반환
@hr_stats_bp.route("/charts/employees_by_position.png")
def chart_employees_by_position():
    return generate_chart(
        group_field="position",
        match={"status": "재직중"},
        title="직급별 직원 수 (재직중)",
        color="lightgreen"
    )

# 재직 중인 직원들을 직책/직무별로 집계해 막대차트 PNG로 반환
@hr_stats_bp.route("/charts/employees_by_job_title.png")
def chart_employees_by_job_title():
    return generate_chart(
        group_field="job_title",
        match={"status": "재직중"},
        title="직책/직무별 직원 수 (재직중)",
        color="gold"
    )

# 최근 12개월간 월별 입사자 수를 선 그래프로 PNG 반환
@hr_stats_bp.route("/charts/monthly_hires.png")
def chart_monthly_hires():
    return generate_chart(
        group_field="hire_date",
        date_format="%Y-%m",
        limit=12,
        chart_type="line",
        title="월별 입사자 수 (최근 12개월)",
        color="#1f77b4"
    )

# 최근 12개월간 월별 퇴사자 수를 선 그래프로 PNG 반환
@hr_stats_bp.route("/charts/monthly_resignations.png")
def chart_monthly_resignations():
    return generate_chart(
        group_field="updated_at",
        match={"status": "퇴사"},
        date_format="%Y-%m",
        limit=12,
        chart_type="line",
        title="월별 퇴사자 수 (최근 12개월)",
        color="#d62728"
    )

# 직원 리스트로부터 근속 연수 분포(범주별 직원 수)를 계산하는 함수
def calc_work_dist(employees, start_key, end_key=None):
    # 근속 연수 분포 계산 함수
    labels = ['1년 미만', '1-3년', '3-5년', '5-10년', '10년 이상']
    bins = [1, 3, 5, 10]
    work_dist = {label: 0 for label in labels}
    today = date.today()

    for emp in employees:
        start = emp[start_key].date()
        end = emp[end_key].date() if end_key else today
        years = (end - start).days / 365.25
        idx = bisect.bisect_right(bins, years)
        work_dist[labels[idx]] += 1

    labels_filtered = [k for k, v in work_dist.items() if v > 0]
    values_filtered = [v for v in work_dist.values() if v > 0]
    return labels_filtered, values_filtered

# 재직자 근속 연수 분포를 원형 차트로 렌더링해 PNG 이미지 반환
@hr_stats_bp.route("/charts/years_of_service.png")
def chart_years_of_service():
    employees = list(mongo_db.hr.find({"status": "재직중", "hire_date": {"$ne": None}}))
    if not employees:
        return send_file(io.BytesIO(), mimetype='image/png')

    labels, values = calc_work_dist(employees, start_key='hire_date')

    if not values:
        return send_file(io.BytesIO(), mimetype='image/png')

    fig = Figure(figsize=(8, 8))
    ax = fig.subplots()

    colors = ['#a6cee3', '#1f78b4', '#b2df8a', '#33a02c', '#fb9a99']
    ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors[:len(values)])
    ax.axis('equal')
    ax.set_title('재직자 근속 연수 분포')

    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    return send_file(img, mimetype='image/png')

# 퇴사자 근속 연수 분포를 막대 차트로 렌더링해 PNG 이미지 반환
@hr_stats_bp.route("/charts/resigned_yos.png")
def chart_resigned_years_of_service():
    employees = list(mongo_db.hr.find({"status": "퇴사", "hire_date": {"$ne": None}, "updated_at": {"$ne": None}}))
    if not employees:
        return send_file(io.BytesIO(), mimetype='image/png')

    labels, values = calc_work_dist(employees, start_key='hire_date', end_key='updated_at')

    if not values:
        return send_file(io.BytesIO(), mimetype='image/png')

    fig = Figure(figsize=(10, 6))
    ax = fig.subplots()

    ax.bar(labels, values, color='salmon')
    ax.set_ylabel('퇴사자 수')
    ax.set_title('퇴사자 근속 연수 분포')

    max_y = max(values)
    ax.set_yticks(range(0, max_y + 2))

    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    return send_file(img, mimetype='image/png')
