from flask import Blueprint, render_template
from db import mongo

# http://127.0.0.1:5000/issue
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

@issue_bp.route("/list")
def list():
    issues_collection = mongo.db.issues
    issues_cursor = issues_collection.find().sort("created_at", -1)
    posts = []
    for i, issue in enumerate(issues_cursor, start=1):
        posts.append({
            "id": i,
            "category": issue.get("category", "카테고리없음"),
            "title": issue.get("title", "제목없음"),
            "author": issue.get("author", "작성자없음"),
            "date": issue.get("created_at").strftime("%Y-%m-%d %H:%M") if issue.get("created_at") else "날짜없음"
        })
    return render_template("issue/list.html", posts=posts)

@issue_bp.route("/write")
def write():
    # MongoDB에서 _id가 1인 카테고리 가져오기
    category = mongo.db.categories.find_one({"_id": 1})
    category_name = category["name"] if category else "1번 카테고리"  # 없을 경우 기본값

    return render_template("issue/write.html", category_name=category_name)


@issue_bp.route("/detail")
def detail():
    return render_template("issue/detail.html")