from flask import Blueprint, render_template
from db import mongo

# http://127.0.0.1:5000/write
write_bp = Blueprint("write", __name__)

# {
#   "_id": ObjectId,
#   "title": "게시글 제목",
#   "content": "게시글 내용",
#   "author_id": ObjectId,
#   "tags": ["공지", "자유"],
#   "created_at": ISODate,
#   "updated_at": ISODate,
#   "comments": [
#     {
#       "comment_id": ObjectId,
#       "author_id": ObjectId,
#       "content": "댓글 내용",
#       "created_at": ISODate
#     }
#   ]
# }

@write_bp.route("/")
def home():
    return render_template("write/index.html")