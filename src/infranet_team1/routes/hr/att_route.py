from routes.hr.bp import hr_bp
from bson.objectid import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash

# 근태 Document
# {
#   "_id": ObjectId("..."),
#   "user_id": ObjectId("..."),  // 사용자의 _id
#   "date": "2025-06-18",        // ISO 날짜 문자열
#   "clock_in": "2025-06-18T08:57:00",
#   "clock_out": "2025-06-18T18:02:00",
#   "working_minutes": 545,
#   "status": "정상",             // 정상 / 지각 / 결근 / 미퇴근 등
#   "memo": "회의 준비로 조기 출근"
# }

@hr_bp.route("/att", methods=["GET"])
def attendance():
    return render_template("hr/attendance.html")