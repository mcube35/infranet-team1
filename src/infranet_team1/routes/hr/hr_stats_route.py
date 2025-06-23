import io
from flask import Blueprint, render_template, send_file
from db import mongo_db
from datetime import datetime, date

# matplotlib 설정 (이전과 동일)
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 한글 폰트 설정
try:
    font_path = "c:/Windows/Fonts/malgun.ttf"
    font_prop = fm.FontProperties(fname=font_path)
    plt.rc('font', family=font_prop.get_name())
    plt.rcParams['axes.unicode_minus'] = False # 마이너스 기호 깨짐 방지
except:
    print("한글 폰트를 찾을 수 없습니다. 차트의 한글이 깨질 수 있습니다.")

hr_stats_bp = Blueprint("hr_stats", __name__, url_prefix="/hr/stats")

# 메인 통계 대시보드 페이지 (변경 없음)
@hr_stats_bp.route("/")
def dashboard():
    total_employees = mongo_db.hr.count_documents({})
    active_employees = mongo_db.hr.count_documents({"status": "재직중"})
    return render_template("hr/hr_stats.html", 
                        total_employees=total_employees,
                        active_employees=active_employees)

# 부서별 직원 수 차트 (변경 없음)
@hr_stats_bp.route("/charts/employees_by_department.png")
def chart_employees_by_department():
    pipeline = [{"$group": {"_id": "$department", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    data = list(mongo_db.hr.aggregate(pipeline))

    if not data: return send_file(io.BytesIO(), mimetype='image/png')
        
    labels = [d['_id'] if d['_id'] else '미지정' for d in data]
    values = [d['count'] for d in data]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(labels, values, color='skyblue')
    ax.set_ylabel('직원 수')
    ax.set_title('부서별 직원 수')
    plt.xticks(rotation=45, ha="right")

    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plt.close(fig)
    return send_file(img, mimetype='image/png')

# ✅ 월별 입사자 수 차트 (pandas 없이 구현)
@hr_stats_bp.route("/charts/monthly_hires.png")
def chart_monthly_hires():
    pipeline = [
        {"$project": {"hire_month": {"$dateToString": {"format": "%Y-%m", "date": "$hire_date"}}}},
        {"$group": {"_id": "$hire_month", "hires": {"$sum": 1}}},
        {"$sort": {"_id": -1}},
        {"$limit": 12} # 최근 12개월 데이터만
    ]
    data = sorted(list(mongo_db.hr.aggregate(pipeline)), key=lambda x: x['_id'])
    
    if not data: return send_file(io.BytesIO(), mimetype='image/png')

    labels = [d['_id'] for d in data]
    values = [d['hires'] for d in data]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(labels, values, marker='o', linestyle='-', color='#1f77b4')
    ax.set_title('월별 입사자 수 (최근 12개월)')
    ax.set_ylabel('인원 수')
    ax.set_xlabel('연-월')
    plt.xticks(rotation=45)
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)

    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plt.close(fig)
    return send_file(img, mimetype='image/png')

# ✅ 근속 연수 분포 차트 (pandas 없이 구현)
@hr_stats_bp.route("/charts/years_of_service.png")
def chart_years_of_service():
    employees = list(mongo_db.hr.find({"status": "재직중", "hire_date": {"$ne": None}}))
    if not employees: return send_file(io.BytesIO(), mimetype='image/png')

    today = date.today()
    
    # 1. 구간별 카운트를 저장할 딕셔너리 초기화
    labels = ['1년 미만', '1-3년', '3-5년', '5-10년', '10년 이상']
    service_dist = {label: 0 for label in labels}

    # 2. 각 직원의 근속 연수를 계산하고 구간에 맞게 카운트
    for emp in employees:
        years = (today - emp['hire_date'].date()).days / 365.25
        if years < 1:
            service_dist['1년 미만'] += 1
        elif years < 3:
            service_dist['1-3년'] += 1
        elif years < 5:
            service_dist['3-5년'] += 1
        elif years < 10:
            service_dist['5-10년'] += 1
        else:
            service_dist['10년 이상'] += 1

    # 3. 데이터가 있는 구간만 차트에 표시
    final_labels = [k for k, v in service_dist.items() if v > 0]
    final_values = [v for v in service_dist.values() if v > 0]

    if not final_values: return send_file(io.BytesIO(), mimetype='image/png')

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(final_values, labels=final_labels, autopct='%1.1f%%', startangle=90, colors=plt.cm.Paired.colors)
    ax.axis('equal')
    ax.set_title('재직자 근속 연수 분포')

    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plt.close(fig)
    return send_file(img, mimetype='image/png')