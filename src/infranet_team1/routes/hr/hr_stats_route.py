from collections import Counter
import io
from flask import Blueprint, jsonify, render_template, abort
from flask_login import current_user
from db import mongo_db
from datetime import date, datetime

hr_stats_bp = Blueprint("hr_stats", __name__, url_prefix="/hr/stats")

@hr_stats_bp.before_request
def check_admin():
    if current_user.role not in ['admin', 'system']: abort(403)

@hr_stats_bp.route("/")
def dashboard():
    stats = {
        "total_employees": mongo_db.hr.count_documents({}),
        "active_employees": mongo_db.hr.count_documents({"status": "재직중"}),
        "on_leave_employees": mongo_db.hr.count_documents({"status": "휴직"}),
        "resigned_employees": mongo_db.hr.count_documents({"status": "퇴사"}),
    }
    return render_template("hr/hr_stats.html", **stats)

def get_chart_department():
    pipeline = [
        {"$match": {"status": "재직중"}},
        {"$group": {"_id": "$department", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": -1}}
    ]
    return list(mongo_db.hr.aggregate(pipeline))

def get_chart_position():
    pipeline = [
        {"$match": {"status": "재직중"}},
        {"$group": {"_id": "$position", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": -1}}
    ]
    return list(mongo_db.hr.aggregate(pipeline))

def get_chart_job_title():
    pipeline = [
        {"$match": {"status": "재직중"}},
        {"$group": {"_id": "$job_title", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": -1}}
    ]
    return list(mongo_db.hr.aggregate(pipeline))

def get_chart_hires_vs_resignations():
    hires_pipeline = [
        {"$project": {"month": {"$dateToString": {"format": "%Y-%m", "date": "$hire_date"}}}},
        {"$group": {"_id": "$month", "count": {"$sum": 1}}}
    ]
    resigns_pipeline = [
        {"$match": {"status": "퇴사"}},
        {"$project": {"month": {"$dateToString": {"format": "%Y-%m", "date": "$updated_at"}}}},
        {"$group": {"_id": "$month", "count": {"$sum": 1}}}
    ]

    hires_data = {d['_id']: d['count'] for d in mongo_db.hr.aggregate(hires_pipeline)}
    resigns_data = {d['_id']: d['count'] for d in mongo_db.hr.aggregate(resigns_pipeline)}

    all_months = sorted(set(hires_data) | set(resigns_data), reverse=True)[:12]
    all_months.reverse()

    return {
        "labels": all_months,
        "datasets": [
            {"label": "입사자", "data": [hires_data.get(m, 0) for m in all_months]},
            {"label": "퇴사자", "data": [resigns_data.get(m, 0) for m in all_months]}
        ]
    }
    
    
def get_yos_label(years):
    thresholds = [1, 3, 5, 10, float('inf')]
    labels = ['1년 미만', '1-3년', '3-5년', '5-10년', '10년 이상']
    for t, label in zip(thresholds, labels):
        if years < t:
            return label


def get_chart_yos(chart_name):
    is_resigned = (chart_name == "yos_resigned")
    query = {
        "status": "퇴사" if is_resigned else "재직중",
        "hire_date": {"$ne": None},
        **({"updated_at": {"$ne": None}} if is_resigned else {})
    }

    counter = Counter()

    for emp in mongo_db.hr.find(query):
        start = emp['hire_date'].date()
        end = (emp.get('updated_at') or datetime.now()).date() if is_resigned else date.today()
        years = (end - start).days / 365.25
        label = get_yos_label(years)
        counter[label] += 1

    result = []
    for label, count in counter.items():
        if count > 0:
            result.append({"_id": label, "count": count})
    return result


@hr_stats_bp.route("/api/chart-data/<chart_name>")
def get_chart_data(chart_name):
    chart_funcs = {
        "department": get_chart_department,
        "position": get_chart_position,
        "job_title": get_chart_job_title,
        "hires_vs_resignations": get_chart_hires_vs_resignations,
        "yos_active": lambda: get_chart_yos("yos_active"),
        "yos_resigned": lambda: get_chart_yos("yos_resigned"),
    }

    if chart_name not in chart_funcs:
        return jsonify({"error": "Invalid chart name"}), 400

    result = chart_funcs[chart_name]()
    
    if chart_name == "hires_vs_resignations":
        return jsonify(result)

    # 나머지 chart들은 공통 포맷
    return jsonify({
        "labels": [d['_id'] if d['_id'] else '미지정' for d in result],
        "data": [d['count'] for d in result]
    })
