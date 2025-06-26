from flask import Blueprint, render_template, request, redirect, url_for, abort
from bson.objectid import ObjectId
from flask_login import current_user
from db import mongo_db
import datetime
import os

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

def get_posts_collection():
    return mongo_db["posts"]

def get_hr_collection():
    return mongo_db["hr"]

@write_bp.route("/")
def home():
    # 1. 검색어와 카테고리 필터 받기
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    # 2. 쿼리 조건 구성
    query = {}
    if category:
        query["category"] = category  # 'tags'가 아닌 'category'로 수정
    if q:
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"content": {"$regex": q, "$options": "i"}}
        ]

    # 3. 게시글 조회
    posts = list(get_posts_collection().find(query).sort("created_at", -1))

    # 4. 작성자 매핑
    author_ids = list(set(post["author_id"] for post in posts))
    authors = list(get_hr_collection().find({"_id": {"$in": author_ids}}))
    author_map = {author["_id"]: author["name"] for author in authors}

    # 5. 활동 순위 (전체 기준)
    pipeline = [
        {"$group": {"_id": "$author_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    agg_result = list(get_posts_collection().aggregate(pipeline))
    top_users = []
    if agg_result:
        top_author_ids = [doc["_id"] for doc in agg_result]
        top_authors = list(get_hr_collection().find({"_id": {"$in": top_author_ids}}))
        id_to_name = {a["_id"]: a["name"] for a in top_authors}
        for doc in agg_result:
            name = id_to_name.get(doc["_id"], "알 수 없음")
            top_users.append((name, doc["count"]))

    # 6. 워드 클라우드 이미지 경로
    wordcloud_path = os.path.join("static", "images", "wordcloud.png")
    wordcloud_url = "/" + wordcloud_path.replace("\\", "/") if os.path.exists(wordcloud_path) else None

    return render_template(
        "write/index.html",
        posts=posts,
        author_map=author_map,
        top_users=top_users,
        wordcloud_url=wordcloud_url,
        request=request,
        selected_category=category
    )


# 게시글 작성 폼
@write_bp.route("/new", methods=["GET"])
def write_form():
    return render_template("write/write.html")


# 게시글 작성 POST처리
@write_bp.route("/new", methods=["POST"])
def save_post():
    title = request.form.get("title").strip()
    content = request.form.get("content").strip()
    category = request.form.get("category")  # ✅ 카테고리 추가

    if not title or not content or not category:
        return "모든 필드를 입력하세요.", 400

    post = {
        "title": title,
        "content": content,
        "category": category,  # ✅ 카테고리 저장
        "author_id": ObjectId(current_user.id),
        "tags": [],
        "created_at": datetime.datetime.utcnow(),
        "updated_at": None,
        "comments": []
    }

    get_posts_collection().insert_one(post)
    return redirect(url_for("write.home", category=category))  # ✅ 작성 후 해당 카테고리로 리디렉션



# 게시글 상세보기
@write_bp.route("/post/<post_id>", methods=["GET"])
def detail(post_id):
    post = get_posts_collection().find_one({"_id": ObjectId(post_id)})
    if not post:
        abort(404)

    author_ids = list(set({comment["author_id"] for comment in post.get("comments", [])}))
    authors = get_hr_collection().find({"_id": {"$in": author_ids}})
    author_map = {author["_id"]: author["name"] for author in authors}
    
    post_author = get_hr_collection().find_one({"_id": post["author_id"]})
    user_name = post_author["name"] if post_author else "알 수 없음"

    return render_template(
        "write/detail.html",
        post=post, 
        author_map=author_map,
        user_name=user_name
                        )


# 댓글 작성 POST처리
@write_bp.route("/post/<post_id>/comment", methods=["POST"])
def add_comment(post_id):
    post = get_posts_collection().find_one({"_id": ObjectId(post_id)})
    if not post:
        abort(404)
    
    comment_content = request.form.get("comment_content")
    if not comment_content:
        return "댓글 내용을 입력하세요.", 400

    comment = {
        "comment_id": ObjectId(),
        "author_id": ObjectId(current_user.id),
        "content": comment_content,
        "created_at": datetime.datetime.utcnow()
    }

    get_posts_collection().update_one(
        {"_id": ObjectId(post_id)},
        {"$push": {"comments": comment}}
    )
    return redirect(url_for("write.detail", post_id=post_id))

# 댓글 삭제 기능 
@write_bp.route("/post/<post_id>/comment/delete", methods=["POST"])
def delete_comment(post_id):
    post = get_posts_collection().find_one({"_id": ObjectId(post_id)})
    if not post:
        abort(404)

    comment_id = request.form.get("comment_id")

    # 댓글 찾기
    target_comment = None
    for c in post.get("comments", []):
        if str(c["comment_id"]) == comment_id:
            target_comment = c
            break
    if not target_comment:
        abort(404)

    # 권한 확인
    is_comment_author = target_comment["author_id"] == ObjectId(current_user.id)
    is_post_author = post["author_id"] == ObjectId(current_user.id)
    is_admin = getattr(current_user, "role", "") in ["admin", "system"]

    if not (is_comment_author or is_post_author or is_admin):
        abort(403)

    get_posts_collection().update_one(
        {"_id": ObjectId(post_id)},
        {"$pull": {"comments": {"comment_id": ObjectId(comment_id)}}}
    ) 

    return redirect(url_for("write.detail", post_id=post_id))



# 게시글 수정 폼
@write_bp.route("/edit/<post_id>", methods=["GET"])
def edit_form(post_id):
    post = get_posts_collection().find_one({"_id": ObjectId(post_id)})
    if not post:
        abort(404)

    # 권한 체크
    is_author = post["author_id"] == ObjectId(current_user.id)
    is_admin = getattr(current_user, "role", "") in ["admin", "system"]
    if not (is_author or is_admin):
        abort(403)

    return render_template("write/write.html", post=post)


# 게시글 수정 POST처리
@write_bp.route("/edit/<post_id>", methods=["POST"])
def edit_post(post_id):
    post = get_posts_collection().find_one({"_id": ObjectId(post_id)})
    if not post:
        abort(404)

    # 권한 체크
    is_author = post["author_id"] == ObjectId(current_user.id)
    is_admin = getattr(current_user, "role", "") in ["admin", "system"]
    if not (is_author or is_admin):
        abort(403)

    title = request.form.get("title")
    content = request.form.get("content")

    if not title or not content:
        return "제목과 내용을 입력하세요.", 400

    get_posts_collection().update_one(
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
    post = get_posts_collection().find_one({"_id": ObjectId(post_id)})
    if not post:
        abort(404)

    # 권한 체크
    is_author = post["author_id"] == ObjectId(current_user.id)
    is_admin = getattr(current_user, "role", "") in ["admin", "system"]
    if not (is_author or is_admin):
        abort(403)

    result = get_posts_collection().delete_one({"_id": ObjectId(post_id)})
    if result.deleted_count == 0:
        abort(404)

    return redirect(url_for("write.home"))
