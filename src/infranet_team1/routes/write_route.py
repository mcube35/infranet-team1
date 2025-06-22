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
    posts = list(mongo.db.posts.find().sort("created_at", -1))
    author_ids = list(set({post["author_id"] for post in posts}))

    authors = mongo.db.hr.find({"_id": {"$in": author_ids}})
    author_map = {author["_id"]: author["name"] for author in authors}

    return render_template("write/index.html", posts=posts, author_map=author_map)


# 게시글 작성 폼
@write_bp.route("/new", methods=["GET"])
def write_form():
    return render_template("write/write.html")


# 게시글 작성 POST처리
@write_bp.route("/new", methods=["POST"])
def save_post():
    title = request.form.get("title").strip()
    content = request.form.get("content").strip()

    if not title or not content:
        return "모든 필드를 입력하세요.", 400

    post = {
        "title": title,
        "content": content,
        "author_id": current_user.id,
        "tags": [],  # 기본은 빈 리스트
        "created_at": datetime.datetime.utcnow(),
        "updated_at": None,
        "comments": []
    }

    mongo.db.posts.insert_one(post)
    return redirect(url_for("write.home"))


# 게시글 상세보기
@write_bp.route("/post/<post_id>", methods=["GET"])
def detail(post_id):
    post = mongo.db.posts.find_one({"_id": ObjectId(post_id)})
    if not post:
        abort(404)

    author_ids = list(set({comment["author_id"] for comment in post.get("comments", [])}))

    authors = mongo.db.hr.find({"_id": {"$in": author_ids}})
    author_map = {author["_id"]: author["name"] for author in authors}

    return render_template("write/detail.html", post=post, author_map=author_map)


# 댓글 작성 POST처리
@write_bp.route("/post/<post_id>/comment", methods=["POST"])
def add_comment(post_id):
    post = mongo.db.posts.find_one({"_id": ObjectId(post_id)})
    if not post:
        abort(404)
    
    comment_content = request.form.get("comment_content")
    if not comment_content:
        return "댓글 내용을 입력하세요.", 400

    comment = {
        "comment_id": ObjectId(),
        "author_id": current_user.id,
        "content": comment_content,
        "created_at": datetime.datetime.utcnow()
    }

    mongo.db.posts.update_one(
        {"_id": ObjectId(post_id)},
        {"$push": {"comments": comment}}
    )
    return redirect(url_for("write.detail", post_id=post_id))

# 댓글 삭제 기능 
@write_bp.route("/post/<post_id>/comment/delete", methods=["POST"])
def delete_comment(post_id):
    post = mongo.db.posts.find_one({"_id": ObjectId(post_id)})
    if not post:
        abort(404)

    # 해당 댓글을 찾고, 작성자가 본인인지 확인
    comment_id = request.form.get("comment_id")
    target_comment = next((c for c in post.get("comments", []) if str(c["comment_id"]) == comment_id), None)
    if not target_comment or target_comment["author_id"] != current_user.id:
        abort(403)  # 권한 없음

    # 댓글 삭제
    mongo.db.posts.update_one(
        {"_id": ObjectId(post_id)},
        {"$pull": {"comments": {"comment_id": ObjectId(comment_id)}}}
    )

    return redirect(url_for("write.detail", post_id=post_id))



# 게시글 수정 폼
@write_bp.route("/edit/<post_id>", methods=["GET"])
def edit_form(post_id):
    post = mongo.db.posts.find_one({"_id": ObjectId(post_id)})
    if not post:
        abort(404)
    return render_template("write/write.html", post=post)


# 게시글 수정 POST처리
@write_bp.route("/edit/<post_id>", methods=["POST"])
def edit_post(post_id):
    post = mongo.db.posts.find_one({"_id": ObjectId(post_id)})
    if not post:
        abort(404)

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


# 게시글 삭제 POST처리
@write_bp.route("/delete/<post_id>", methods=["POST"])
def delete(post_id):
    result = mongo.db.posts.delete_one({"_id": ObjectId(post_id)})
    if result.deleted_count == 0:
        abort(404)
    return redirect(url_for("write.home"))