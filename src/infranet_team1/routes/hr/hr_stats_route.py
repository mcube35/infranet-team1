import io
from flask import Blueprint, render_template, send_file
from db import mongo_db
from datetime import date, datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import platform

if platform.system() == 'Windows':
    plt.rc('font', family='Malgun Gothic')
else:
    plt.rc('font', family='AppleGothic')

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

@hr_stats_bp.route("/charts/employees_by_department.png")
def chart_employees_by_department():
    pipeline = [{"$match": {"status": "재직중"}}, {"$group": {"_id": "$department", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    data = list(mongo_db.hr.aggregate(pipeline))
    if not data: return send_file(io.BytesIO(), mimetype='image/png')
    labels = [d['_id'] if d['_id'] else '미지정' for d in data]; values = [d['count'] for d in data]
    fig, ax = plt.subplots(figsize=(10, 6)); ax.bar(labels, values, color='skyblue'); ax.set_ylabel('직원 수'); ax.set_title('부서별 직원 수 (재직중)'); plt.xticks(rotation=45, ha="right")
    if values: max_y = max(values); ax.set_yticks(range(0, max_y + 2))
    img = io.BytesIO(); fig.savefig(img, format='png', bbox_inches='tight'); img.seek(0); plt.close(fig)
    return send_file(img, mimetype='image/png')

@hr_stats_bp.route("/charts/employees_by_position.png")
def chart_employees_by_position():
    pipeline = [{"$match": {"status": "재직중"}}, {"$group": {"_id": "$position", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    data = list(mongo_db.hr.aggregate(pipeline))
    if not data: return send_file(io.BytesIO(), mimetype='image/png')
    labels = [d['_id'] if d['_id'] else '미지정' for d in data]; values = [d['count'] for d in data]
    fig, ax = plt.subplots(figsize=(10, 6)); ax.bar(labels, values, color='lightgreen'); ax.set_ylabel('직원 수'); ax.set_title('직급별 직원 수 (재직중)'); plt.xticks(rotation=45, ha="right")
    if values: max_y = max(values); ax.set_yticks(range(0, max_y + 2))
    img = io.BytesIO(); fig.savefig(img, format='png', bbox_inches='tight'); img.seek(0); plt.close(fig)
    return send_file(img, mimetype='image/png')

@hr_stats_bp.route("/charts/employees_by_job_title.png")
def chart_employees_by_job_title():
    pipeline = [{"$match": {"status": "재직중"}}, {"$group": {"_id": "$job_title", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    data = list(mongo_db.hr.aggregate(pipeline))
    if not data: return send_file(io.BytesIO(), mimetype='image/png')
    labels = [d['_id'] if d['_id'] else '미지정' for d in data]
    values = [d['count'] for d in data]
    fig, ax = plt.subplots(figsize=(10, 6)); ax.bar(labels, values, color='gold'); ax.set_ylabel('직원 수'); ax.set_title('직책/직무별 직원 수 (재직중)'); plt.xticks(rotation=45, ha="right")
    if values: max_y = max(values); ax.set_yticks(range(0, max_y + 2))
    img = io.BytesIO(); fig.savefig(img, format='png', bbox_inches='tight'); img.seek(0); plt.close(fig)
    return send_file(img, mimetype='image/png')

@hr_stats_bp.route("/charts/monthly_hires.png")
def chart_monthly_hires():
    pipeline = [{"$project": {"hire_month": {"$dateToString": {"format": "%Y-%m", "date": "$hire_date"}}}}, {"$group": {"_id": "$hire_month", "hires": {"$sum": 1}}}, {"$sort": {"_id": -1}}, {"$limit": 12}]
    data = sorted(list(mongo_db.hr.aggregate(pipeline)), key=lambda x: x['_id'])
    if not data: return send_file(io.BytesIO(), mimetype='image/png')
    labels = [d['_id'] for d in data]; values = [d['hires'] for d in data]
    fig, ax = plt.subplots(figsize=(12, 6)); ax.plot(labels, values, marker='o', linestyle='-', color='#1f77b4'); ax.set_title('월별 입사자 수 (최근 12개월)'); ax.set_ylabel('인원 수'); plt.xticks(rotation=45); plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    if values: max_y = max(values); ax.set_yticks(range(0, max_y + 2))
    img = io.BytesIO(); fig.savefig(img, format='png', bbox_inches='tight'); img.seek(0); plt.close(fig)
    return send_file(img, mimetype='image/png')

@hr_stats_bp.route("/charts/monthly_resignations.png")
def chart_monthly_resignations():
    pipeline = [{"$match": {"status": "퇴사"}}, {"$project": {"resignation_month": {"$dateToString": {"format": "%Y-%m", "date": "$updated_at"}}}}, {"$group": {"_id": "$resignation_month", "resignations": {"$sum": 1}}}, {"$sort": {"_id": -1}}, {"$limit": 12}]
    data = sorted(list(mongo_db.hr.aggregate(pipeline)), key=lambda x: x['_id'])
    if not data: return send_file(io.BytesIO(), mimetype='image/png')
    labels = [d['_id'] for d in data]; values = [d['resignations'] for d in data]
    fig, ax = plt.subplots(figsize=(12, 6)); ax.plot(labels, values, marker='o', linestyle='-', color='#d62728'); ax.set_title('월별 퇴사자 수 (최근 12개월)'); ax.set_ylabel('인원 수'); plt.xticks(rotation=45); plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    if values: max_y = max(values); ax.set_yticks(range(0, max_y + 2))
    img = io.BytesIO(); fig.savefig(img, format='png', bbox_inches='tight'); img.seek(0); plt.close(fig)
    return send_file(img, mimetype='image/png')

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
    fig, ax = plt.subplots(figsize=(8, 8)); ax.pie(final_values, labels=final_labels, autopct='%1.1f%%', startangle=90, colors=plt.cm.Paired.colors); ax.axis('equal'); ax.set_title('재직자 근속 연수 분포')
    img = io.BytesIO(); fig.savefig(img, format='png', bbox_inches='tight'); img.seek(0); plt.close(fig)
    return send_file(img, mimetype='image/png')

# 퇴사자 근속 연수 차트
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
    fig, ax = plt.subplots(figsize=(10, 6)); ax.bar(final_labels, final_values, color='salmon'); ax.set_ylabel('퇴사자 수'); ax.set_title('퇴사자 근속 연수 분포')
    
    if final_values:
        max_y = max(final_values)
        ax.set_yticks(range(0, max_y + 2))

    img = io.BytesIO(); fig.savefig(img, format='png', bbox_inches='tight'); img.seek(0); plt.close(fig)
    return send_file(img, mimetype='image/png')