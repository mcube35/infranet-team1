import io
from flask import Blueprint, render_template, send_file
from db import mongo_db

hr_stats_bp = Blueprint("hr_stats", __name__, url_prefix="/hr/stats")

# 메인 통계 대시보드 페이지
@hr_stats_bp.route("/")
def dashboard():
    # 여기서 필요한 주요 숫자들을 계산해서 전달할 수 있습니다.
    total_employees = mongo_db.hr.count_documents({})
    return render_template("hr/hr_stats.html", total_employees=total_employees)

# 부서별 직원 수 차트 이미지를 생성하는 라우트
@hr_stats_bp.route("/charts/employees_by_department.png")
def chart_employees_by_department():
    # 1. Aggregation으로 부서별 직원 수 계산
    pipeline = [
        {"$group": {"_id": "$department", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    data = list(mongo_db.hr.aggregate(pipeline))

    # 2. Matplotlib으로 차트 그리기
    departments = [d['_id'] for d in data]
    counts = [d['count'] for d in data]

    fig, ax = plt.subplots()
    ax.bar(departments, counts, color='skyblue')
    ax.set_ylabel('직원 수')
    ax.set_title('부서별 직원 수')

    # 3. 차트를 이미지 파일(in-memory)로 저장
    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    
    # 닫아주어 메모리 누수 방지
    plt.close(fig)

    return send_file(img, mimetype='image/png')

# ✅ 월별 입사자 vs 퇴사자 수 차트 (신규 추가)
@hr_stats_bp.route("/charts/monthly_turnover.png")
def chart_monthly_turnover():
    # 지난 12개월간의 입사자/퇴사자 데이터를 집계합니다.
    pipeline = [
        {
            "$project": {
                "hire_month": {"$dateToString": {"format": "%Y-%m", "date": "$hire_date"}},
                "is_resigned": {
                    "$cond": [{"$eq": ["$status", "퇴사"]}, 1, 0]
                }
            }
        },
        {
            "$group": {
                "_id": "$hire_month",
                "hires": {"$sum": 1}, # 해당 월의 입사자 수는 hire_month 그룹의 총 개수
            }
        },
        {
            "$sort": {"_id": 1}
        }
    ]
    # 실제 구현에서는 퇴사 날짜 필드가 필요하지만, 여기서는 hire_date를 기준으로 임시 구현합니다.
    # 더 정확한 구현을 위해서는 hr 컬렉션에 'resignation_date' 필드가 필요합니다.
    # 지금은 '입사 월별' 인원만 보여주는 것으로 단순화합니다.
    
    hire_data = list(mongo_db.hr.aggregate(pipeline))
    if not hire_data:
        return send_file(io.BytesIO(), mimetype='image/png')

    df = pd.DataFrame(hire_data)
    df = df.rename(columns={"_id": "month", "hires": "입사"})
    df = df.set_index("month")

    fig, ax = plt.subplots(figsize=(12, 6))
    df.plot(kind='bar', ax=ax, color=['#1f77b4'])
    ax.set_title('월별 입사자 수')
    ax.set_ylabel('인원 수')
    ax.set_xlabel('연-월')
    plt.xticks(rotation=45)

    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plt.close(fig)
    return send_file(img, mimetype='image/png')

# ✅ 근속 연수 분포 차트 (신규 추가)
@hr_stats_bp.route("/charts/years_of_service.png")
def chart_years_of_service():
    employees = list(mongo_db.hr.find({"status": "재직중", "hire_date": {"$ne": None}}))
    
    if not employees:
        return send_file(io.BytesIO(), mimetype='image/png')

    today = date.today()
    service_years = []
    for emp in employees:
        years = (today - emp['hire_date'].date()).days / 365.25
        service_years.append(years)

    bins = [0, 1, 3, 5, 10, float('inf')]
    labels = ['1년 미만', '1-3년', '3-5년', '5-10년', '10년 이상']
    
    # pandas를 사용하여 구간별로 그룹화
    service_dist = pd.cut(service_years, bins=bins, labels=labels, right=False).value_counts().sort_index()

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(service_dist, labels=service_dist.index, autopct='%1.1f%%', startangle=90, colors=plt.cm.Paired.colors)
    ax.axis('equal') # 원 모양 유지
    ax.set_title('재직자 근속 연수 분포')

    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plt.close(fig)
    return send_file(img, mimetype='image/png')