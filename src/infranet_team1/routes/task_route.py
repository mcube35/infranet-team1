from flask import Blueprint, render_template
from db import mongo

# http://127.0.0.1:5000/task
task_bp = Blueprint("task", __name__)

# {
#   "_id": ObjectId,
#   "title": "업무 제목",
#   "description": "업무 상세 설명",
#   "assigned_to": ObjectId,      // 담당자 (hr 직원 ID)
#   "status": "대기중" | "진행중" | "완료",
#   "priority": "낮음" | "보통" | "높음",
#   "due_date": ISODate,
#   "created_at": ISODate,
#   "updated_at": ISODate
# }

@task_bp.route("/")
def home():
    return render_template("task/index.html")