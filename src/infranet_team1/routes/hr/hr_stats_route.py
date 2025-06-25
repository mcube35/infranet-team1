import io
from flask import Blueprint, render_template, send_file
from db import mongo_db
from datetime import date
# 변경: figure를 대문자 Figure로 수정
from matplotlib.figure import Figure

hr_stats_bp = Blueprint("hr_stats", __name__, url_prefix="/hr/stats")

@hr_stats_bp.route("/")
def dashboard():
    total_employees = mongo_db.hr.count_documents({})
    active_employees = mongo_db.hr.count_documents({"status": "재직중"})
    on_leave_employees = mongo_db.hr.count_documents({"status": "휴직"})
    resigned_employees = mongo_db.hr.count_documents({"status": "퇴사"})
    return render_template("hr/hr_stats.html", 
                        total_employees=total_employees, active_employees=active_employees,
                        on_leave_employees=on_leave_employees, resigned_employees=resigned_employees)

def get_mongo_counts(group_field, *, match=None, date_format=None, limit=None, count_key='count'):
    pipeline = []
    if match:
        pipeline.append({'$match': match})
    group_by = f"${group_field}"
    if date_format:
        date_field = f"{group_field}_str"
        pipeline.append({'$project': {date_field: {'$dateToString': {'format': date_format, 'date': group_by}}}})
        group_by = f"${date_field}"
    pipeline += [
        {'$group': {'_id': group_by, count_key: {'$sum': 1}}},
        {'$sort': {'_id' if date_format else count_key: -1}}
    ]
    if limit:
        pipeline.append({'$limit': limit})
    data = list(mongo_db.hr.aggregate(pipeline))
    if date_format:
        data.sort(key=lambda d: d['_id'])
    return data

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
        if values:
            ax.set_yticks(range(0, max(values) + 2))

    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    return send_file(img, mimetype='image/png')

def generate_chart(group_field, *, match=None, date_format=None, limit=None,
                   chart_type='bar', title='', color='skyblue', default_label='미지정', count_key='count'):
    data = get_mongo_counts(group_field, match=match, date_format=date_format, limit=limit, count_key=count_key)
    if not data:
        return send_file(io.BytesIO(), mimetype='image/png')
    labels = [d['_id'] if d['_id'] else default_label for d in data]
    values = [d[count_key] for d in data]
    return plot_chart(labels, values, chart_type=chart_type, title=title, color=color)


@hr_stats_bp.route("/charts/employees_by_department.png")
def chart_employees_by_department():
    return generate_chart(
        group_field="department",
        match={"status": "재직중"},
        title="부서별 직원 수 (재직중)",
        color="skyblue"
    )

@hr_stats_bp.route("/charts/employees_by_position.png")
def chart_employees_by_position():
    return generate_chart(
        group_field="position",
        match={"status": "재직중"},
        title="직급별 직원 수 (재직중)",
        color="lightgreen"
    )

@hr_stats_bp.route("/charts/employees_by_job_title.png")
def chart_employees_by_job_title():
    return generate_chart(
        group_field="job_title",
        match={"status": "재직중"},
        title="직책/직무별 직원 수 (재직중)",
        color="gold"
    )

@hr_stats_bp.route("/charts/monthly_hires.png")
def chart_monthly_hires():
    return generate_chart(
        group_field="hire_date",
        date_format="%Y-%m",
        limit=12,
        chart_type="line",
        title="월별 입사자 수 (최근 12개월)",
        color="#1f77b4",
        count_key="count"
    )

@hr_stats_bp.route("/charts/monthly_resignations.png")
def chart_monthly_resignations():
    return generate_chart(
        group_field="updated_at",
        match={"status": "퇴사"},
        date_format="%Y-%m",
        limit=12,
        chart_type="line",
        title="월별 퇴사자 수 (최근 12개월)",
        color="#d62728",
        count_key="count"
    )

@hr_stats_bp.route("/charts/years_of_service.png")
def chart_years_of_service():
    employees = list(mongo_db.hr.find({"status": "재직중", "hire_date": {"$ne": None}}))
    if not employees: return send_file(io.BytesIO(), mimetype='image/png')
    today = date.today(); labels = ['1년 미만', '1-3년', '3-5년', '5-10년', '10년 이상']; service_dist = {label: 0 for label in labels}
    for emp in employees:
        years = (today - emp['hire_date'].date()).days / 365.25
        if years < 1: service_dist['1년 미만'] += 1
        elif years < 3: service_dist['1-3년'] += 1
        elif years < 5: service_dist['3-5년'] += 1
        elif years < 10: service_dist['5-10년'] += 1
        else: service_dist['10년 이상'] += 1
    final_labels = [k for k, v in service_dist.items() if v > 0]; final_values = [v for v in service_dist.values() if v > 0]
    if not final_values: return send_file(io.BytesIO(), mimetype='image/png')

    fig = Figure(figsize=(8, 8))
    ax = fig.subplots()
    
    colors = ['#a6cee3', '#1f78b4', '#b2df8a', '#33a02c', '#fb9a99', '#e31a1c', '#fdbf6f', '#ff7f00', '#cab2d6', '#6a3d9a']
    ax.pie(final_values, labels=final_labels, autopct='%1.1f%%', startangle=90, colors=colors[:len(final_values)])
    ax.axis('equal')
    ax.set_title('재직자 근속 연수 분포')
    img = io.BytesIO(); fig.savefig(img, format='png', bbox_inches='tight'); img.seek(0)
    return send_file(img, mimetype='image/png')

@hr_stats_bp.route("/charts/resigned_yos.png")
def chart_resigned_years_of_service():
    employees = list(mongo_db.hr.find({"status": "퇴사", "hire_date": {"$ne": None}, "updated_at": {"$ne": None}}))
    if not employees: return send_file(io.BytesIO(), mimetype='image/png')
    labels = ['1년 미만', '1-3년', '3-5년', '5-10년', '10년 이상']; service_dist = {label: 0 for label in labels}
    for emp in employees:
        years = (emp['updated_at'].date() - emp['hire_date'].date()).days / 365.25
        if years < 1: service_dist['1년 미만'] += 1
        elif years < 3: service_dist['1-3년'] += 1
        elif years < 5: service_dist['3-5년'] += 1
        elif years < 10: service_dist['5-10년'] += 1
        else: service_dist['10년 이상'] += 1
    final_labels = [k for k, v in service_dist.items() if v > 0]; final_values = [v for v in service_dist.values() if v > 0]
    if not final_values: return send_file(io.BytesIO(), mimetype='image/png')
    
    fig = Figure(figsize=(10, 6))
    ax = fig.subplots()
    
    ax.bar(final_labels, final_values, color='salmon')
    ax.set_ylabel('퇴사자 수')
    ax.set_title('퇴사자 근속 연수 분포')
    
    if final_values:
        max_y = max(final_values)
        ax.set_yticks(range(0, max_y + 2))

    img = io.BytesIO(); fig.savefig(img, format='png', bbox_inches='tight'); img.seek(0)
    return send_file(img, mimetype='image/png')