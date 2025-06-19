from flask import Blueprint, render_template, request, redirect, url_for, abort
from bson.objectid import ObjectId
from flask_login import current_user
from db import mongo
import datetime

# http://127.0.0.1:5000/write/
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
    posts = mongo.db.posts.find().sort("created_at", -1)
    return render_template("write/index.html", posts = posts)


# 글쓰기
@write_bp.route("/new", methods=["GET", "POST"])
def new_post():
    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")

        if not title or not content:
            return "모든 필드를 입력하세요.", 400

        post = {
            "title": title,
            "content": content,
            "author_id": ObjectId(current_user.id),
            "tags": [],  # 기본은 빈 리스트
            "created_at": datetime.datetime.utcnow(),
            "updated_at": None,
            "comments": []
        }

        mongo.db.posts.insert_one(post)
        return redirect(url_for("write.home"))
    
    user_name = current_user.name
    return render_template("write/write.html", user_name=user_name)


# 게시글 상세보기 및 댓글 작성
@write_bp.route("/post/<post_id>", methods=["GET", "POST"])
def detail(post_id):
    post = mongo.db.posts.find_one({"_id": ObjectId(post_id)})
    if not post:
        abort(404)

    if request.method == "POST":
        comment_content = request.form.get("comment_content")

        if not comment_content:
            return "댓글 내용을 입력하세요.", 400

        comment = {
            "comment_id": ObjectId(),
            "author_id": ObjectId(current_user.id),
            "content": comment_content,
            "created_at": datetime.datetime.utcnow()
        }

        mongo.db.posts.update_one(
            {"_id": ObjectId(post_id)},
            {"$push": {"comments": comment}}
        )
        return redirect(url_for("write.detail", post_id=post_id))
    
    author_ids = [comment["author_id"] for comment in post.get("comments", [])]

    authors = mongo.db.hr.find({"_id": {"$in": author_ids}})
    author_map = {author["_id"]: author["name"] for author in authors}
    
    user_name = current_user.name
    return render_template("write/detail.html", post=post, user_name=user_name, author_map=author_map)


# 게시글 수정
@write_bp.route("/edit/<post_id>", methods=["GET", "POST"])
def edit(post_id):
    post = mongo.db.posts.find_one({"_id": ObjectId(post_id)})
    if not post:
        abort(404)

    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")

        if not title or not content:
            return "제목과 내용을 입력하세요.", 400

        mongo.db.posts.update_one(
            {"_id": ObjectId(post_id)},
            {
                "$set": {
                    "title": title,
                    "content": content,
                    "updated_at": datetime.datetime.utcnow()
                }
            }
        )
        return redirect(url_for("write.detail", post_id=post_id))

    return render_template("write/write.html", post=post)


# 게시글 삭제
@write_bp.route("/delete/<post_id>", methods=["POST"])
def delete(post_id):
    result = mongo.db.posts.delete_one({"_id": ObjectId(post_id)})
    if result.deleted_count == 0:
        abort(404)
    return redirect(url_for("write.home"))