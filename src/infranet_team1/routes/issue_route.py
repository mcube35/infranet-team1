from flask import Blueprint, render_template
from db import mongo

issue_bp = Blueprint("issue", __name__)

# {
#   "_id": ObjectId,
#   "title": "이슈 제목",
#   "description": "이슈 내용",
#   "reported_by": ObjectId,      // 신고자 (hr 직원 ID)
#   "assigned_to": ObjectId,      // 처리 담당자
#   "status": "열림" | "진행중" | "해결됨" | "닫힘",
#   "severity": "낮음" | "중간" | "높음",
#   "created_at": ISODate,
#   "updated_at": ISODate,
#   "comments": [
#     {
#       "author_id": ObjectId,
#       "content": "댓글 내용",
#       "created_at": ISODate
#     }
#   ]
# }

@issue_bp.route("/")
def home():
    return render_template("issue/index.html")