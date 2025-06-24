from flask import Blueprint, render_template, redirect, request, url_for, jsonify
from flask_login import current_user
from db import mongo_db
from datetime import datetime
from bson.objectid import ObjectId

issue_bp = Blueprint("issue", __name__)

# --- 전역 상수/매핑 정의 ---
STATUS_MAP = {1: "신규", 2: "진행중", 3: "해결됨"}

# --- 컬렉션 헬퍼 함수 ---
def get_issues(): return mongo_db["issues"]
def get_clients(): return mongo_db["clients"]
def get_users(): return mongo_db["users"]

# 임시 보고자 ID (로그인 기능이 없을 때의 기본값)
DUMMY_REPORTER_ID = ObjectId("60c72b2f9b1d8e001c8c4a03")

# --- 헬퍼 함수 ---
def is_valid_family(family_name):
    """주어진 family_name이 유효한지 검사합니다."""
    return family_name in ["backend", "frontend", "ui"]

def _to_str_or_default(value, default="없음"):
    """ObjectId나 None 값을 문자열로 변환하고 기본값을 제공합니다."""
    return str(value) if value is not None else default

def _format_datetime(dt, default="날짜없음"):
    """datetime 객체를 특정 형식의 문자열로 변환하고 기본값을 제공합니다."""
    return dt.strftime("%Y-%m-%d %H:%M") if dt else default

def _get_reporter_name(reporter_id_obj):
    """작성자 ObjectId로 사용자 이름을 조회합니다."""
    if reporter_id_obj:
        try:
            if not isinstance(reporter_id_obj, ObjectId):
                reporter_id_obj = ObjectId(str(reporter_id_obj))
            
            user_doc = mongo_db.hr.find_one({"_id": reporter_id_obj}, {"name": 1})
            
            return user_doc.get("name", "알 수 없는 사용자") if user_doc else "알 수 없는 사용자"
        except Exception as e:
            return "알 수 없는 사용자"
    return "알 수 없는 사용자"


# --- 이슈 메인 페이지 라우트 ---
@issue_bp.route("/")
def home():
    family_map = {"Back family": "backend", "Front family": "frontend", "Publisher family": "ui"}
    status_map = {"신규 이슈": STATUS_MAP[1], "진행중인 이슈": STATUS_MAP[2], "퇴마된 이슈": STATUS_MAP[3]}

    users_map = {str(u["_id"]): u.get("name", "알 수 없는 사용자") 
                 for u in mongo_db.hr.find({}, {"name": 1})}

    result = {}
    for fname, fval in family_map.items():
        result[fname] = {}
        for sname, sval in status_map.items():
            issues = get_issues().find({"project_family": fval, "status": sval}).sort("created_at", -1).limit(3)
            result[fname][sname] = [{
                "title": i.get("title", "제목없음"),
                "mongo_id": _to_str_or_default(i.get("_id")),
                "family_name": fval,
                "reporter_name": users_map.get(_to_str_or_default(i.get("reported_by"), None), "알 수 없는 사용자")
            } for i in issues]
    return render_template("issue/index.html", issues_by_family_and_status=result, family_categories=family_map)


# --- 이슈 리스트 화면 라우트 ---
@issue_bp.route("/list/<family_name>")
def show_list(family_name):
    if not is_valid_family(family_name): return "Invalid family", 400

    main_issue_collection = get_issues()
    
    total_issues_count = main_issue_collection.count_documents({"project_family": family_name})

    issues_cursor = main_issue_collection.find(
        {"project_family": family_name}
    ).sort("created_at", -1)

    users_map = {str(u["_id"]): u.get("name", "알 수 없는 사용자") 
                 for u in mongo_db.hr.find({}, {"name": 1})}

    posts = []
    for idx, issue in enumerate(issues_cursor):
        display_id_reversed = total_issues_count - idx 

        posts.append({
            "display_id": display_id_reversed, 
            "mongo_id": _to_str_or_default(issue.get("_id")),
            "title": issue.get("title", "제목없음"),
            "description": issue.get("description", "내용없음"),
            "category": issue.get("category", "일반"),
            "status": issue.get("status", "상태없음"),
            "reporter_name": users_map.get(_to_str_or_default(issue.get("reported_by"), None), "알 수 없는 사용자"),
            "client_company_id": _to_str_or_default(issue.get("client_company_id")),
            "client_company_name": issue.get("client_company_name", "고객사없음"),
            "assigned_to_id": _to_str_or_default(issue.get("assigned_to")),
            "created_at": _format_datetime(issue.get("created_at")),
            "updated_at": _format_datetime(issue.get("updated_at"))
        })
    return render_template("issue/list.html", posts=posts, current_family=family_name)


# --- 이슈 작성 폼 및 처리 라우트 ---
@issue_bp.route("/write/<family_name>", methods=["GET", "POST"])
def write(family_name):
    if not is_valid_family(family_name): return "Invalid family", 400

    main_issue_collection = get_issues() 

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        status_id = int(request.form.get("status_id")) # '신규'는 1로 고정될 것임
        selected_client_company_id_str = request.form.get("client_company_id")
        
        final_reporter_id = DUMMY_REPORTER_ID # 기본값은 더미 ID

        if current_user.is_authenticated: # 사용자가 로그인되어 있다면
            try:
                final_reporter_id = ObjectId(current_user.get_id()) 
            except Exception as e:
                print(f"Error converting current_user.id ({current_user.get_id()}) to ObjectId: {e}")
                final_reporter_id = DUMMY_REPORTER_ID 
        else:
            print(f"No user logged in. Using DUMMY_REPORTER_ID: {final_reporter_id}")

        status_name = STATUS_MAP.get(status_id, "알 수 없음") 

        client_name, client_obj_id = None, None
        if selected_client_company_id_str:
            try:
                client_obj_id = ObjectId(selected_client_company_id_str)
                client_doc = get_clients().find_one({"_id": client_obj_id})
                if client_doc:
                    client_name = client_doc.get("company_name", "알 수 없음")
            except:
                return "유효하지 않은 고객사 ID입니다.", 400

        issue_data = {
            "title": title,
            "description": description,
            "category": "일반", 
            "reported_by": final_reporter_id, # 로그인된 사용자 ID 또는 더미 ID 사용
            "assigned_to": None, 
            "status_id": status_id, 
            "status": status_name,   
            "client_company_id": client_obj_id, 
            "client_company_name": client_name, 
            "project_family": family_name, 
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        
        main_issue_collection.insert_one(issue_data) 
        
        return redirect(url_for("issue.show_list", family_name=family_name)) 
    
    else: 
        return render_template(
            "issue/write.html",
            category_name=STATUS_MAP.get(1), 
            current_family=family_name 
        )

# --- 이슈 상세보기 라우트 ---
@issue_bp.route("/detail/<family_name>/<issue_id>")
def detail(family_name, issue_id):
    if not is_valid_family(family_name): return "Invalid family", 400
    
    try:
        issue = get_issues().find_one({"_id": ObjectId(issue_id), "project_family": family_name})
        if not issue: return "이슈를 찾을 수 없습니다.", 404

        issue.update({
            "mongo_id": _to_str_or_default(issue.get("_id")),
            "reporter_name_display": _get_reporter_name(issue.get("reported_by")), 
            "assigned_to_str": _to_str_or_default(issue.get("assigned_to")),
            "client_company_id_str": _to_str_or_default(issue.get("client_company_id")),
            "created_at_str": _format_datetime(issue.get("created_at")),
            "updated_at_str": _format_datetime(issue.get("updated_at")),
            "client_company_name_display": issue.get("client_company_name", "고객사없음")
        })
        return render_template("issue/detail.html", issue=issue, current_family=family_name)
    except Exception as e:
        return f"유효하지 않은 이슈 ID입니다: {e}", 400


# --- 이슈 수정 폼 및 처리 라우트 ---
# URL: /issue/edit/<family_name>/<issue_id>
# 이 라우트가 존재해야 합니다!
@issue_bp.route("/edit/<family_name>/<issue_id>", methods=["GET", "POST"])
def edit(family_name, issue_id):
    if not is_valid_family(family_name): return "Invalid family", 400

    main_issue_collection = get_issues()

    if request.method == "GET":
        try:
            issue = main_issue_collection.find_one({"_id": ObjectId(issue_id), "project_family": family_name})
            if not issue:
                return "수정할 이슈를 찾을 수 없습니다.", 404

            issue['mongo_id'] = _to_str_or_default(issue.get("_id"))
            issue['client_company_id_str'] = _to_str_or_default(issue.get("client_company_id"))

            issue['client_company_name_for_input'] = issue.get("client_company_name", "")

            status_options = []
            for id, name in STATUS_MAP.items():
                status_options.append({"id": id, "name": name, "selected": (name == issue.get("status"))})
            
            return render_template("issue/update.html", # 'update.html'로 변경
                                   issue=issue, 
                                   current_family=family_name,
                                   status_options=status_options)
        except Exception as e:
            return f"이슈 로드 오류: {e}", 400

    elif request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        status_name = request.form.get("status") 
        selected_client_company_id_str = request.form.get("client_company_id")

        client_name_to_save, client_obj_id = None, None
        if selected_client_company_id_str:
            try:
                client_obj_id = ObjectId(selected_client_company_id_str)
                client_doc = get_clients().find_one({"_id": client_obj_id})
                if client_doc:
                    client_name_to_save = client_doc.get("company_name", "알 수 없음")
            except:
                return "유효하지 않은 고객사 ID입니다.", 400

        update_data = {
            "$set": {
                "title": title,
                "description": description,
                "status": status_name, 
                "client_company_id": client_obj_id,
                "client_company_name": client_name_to_save,
                "updated_at": datetime.now()
            }
        }

        try:
            result = main_issue_collection.update_one(
                {"_id": ObjectId(issue_id), "project_family": family_name},
                update_data
            )
            if result.matched_count == 0:
                print(f"No issue matched for update (edit POST): _id={issue_id}, project_family={family_name}")
                return "수정할 이슈를 찾을 수 없습니다.", 404

            return redirect(url_for("issue.detail", family_name=family_name, issue_id=issue_id))
        except Exception as e:
            return f"이슈 업데이트 오류: {e}", 500


# --- 이슈 삭제 라우트 ---
# URL: /issue/delete/<family_name>/<issue_id>
@issue_bp.route("/delete/<family_name>/<issue_id>", methods=["POST"])
def delete(family_name, issue_id):
    if not is_valid_family(family_name): return "Invalid family", 400

    main_issue_collection = get_issues()

    try:
        obj_issue_id = ObjectId(issue_id)
        
        result = main_issue_collection.delete_one(
            {"_id": obj_issue_id, "project_family": family_name}
        )
        
        if result.deleted_count == 0:
            print(f"No issue found for deletion: _id={issue_id}, project_family={family_name}")
            return "삭제할 이슈를 찾을 수 없습니다.", 404
        
        return redirect(url_for("issue.show_list", family_name=family_name))

    except Exception as e:
        print(f"Error during deletion: {e}")
        return f"이슈 삭제 오류: {e}", 500


# --- 이슈 상태 업데이트 라우트 (기존 상세페이지용 - 이제 edit/update에서 처리하므로 중복 고려) ---
# 이 라우트는 이제 edit 페이지와 기능이 겹치므로, 필요 없다면 제거를 고려할 수 있습니다.
@issue_bp.route("/update_status/<family_name>/<issue_id>", methods=["POST"])
def update_status(family_name, issue_id):
    if not is_valid_family(family_name): return "Invalid family", 400
    new_status = request.form.get("new_status")
    if not new_status: return "새로운 상태가 필요합니다.", 400

    try:
        obj_issue_id = ObjectId(issue_id)
        result = get_issues().update_one(
            {"_id": obj_issue_id, "project_family": family_name},
            {"$set": {"status": new_status, "updated_at": datetime.now()}}
        )
        if result.matched_count == 0:
            print(f"No issue matched for update: _id={issue_id}, project_family={family_name}") 

        return redirect(url_for("issue.detail", family_name=family_name, issue_id=issue_id))
    except Exception as e:
        return f"상태 업데이트 오류: {e}", 500


# --- 고객사 검색 API 엔드포인트 ---
@issue_bp.route("/search_client", methods=["POST"])
def search_client():
    term = request.json.get("search_term", "").strip()
    if not term: return jsonify([])

    results = get_clients().find({"company_name": {"$regex": term, "$options": "i"}}).limit(10)
    return jsonify([{"id": _to_str_or_default(c.get("_id")), "name": c.get("company_name", "이름없음")} for c in results])
