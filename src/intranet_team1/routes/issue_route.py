import json 
from flask import Blueprint, render_template, redirect, request, url_for, jsonify
from flask_login import current_user
from db import mongo_db 
from datetime import datetime
from bson.objectid import ObjectId

issue_bp = Blueprint("issue", __name__, url_prefix="/issue")

ISSUE_STATUS = {1: "신규", 2: "진행중", 3: "해결됨"}

def get_issues(): return mongo_db["issues"]
def get_clients(): return mongo_db["clients"]
def get_hr_collection(): return mongo_db["hr"] 

def is_valid_family(family_name):
    return family_name in ["backend", "frontend", "ui"]

def _to_str_or_default(value, default="없음"):
    return str(value) if value is not None else default

def _format_datetime(dt, default="날짜없음"):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else default

def _get_reporter_name(reporter_id_obj):
    if reporter_id_obj:
        try:
            if not isinstance(reporter_id_obj, ObjectId):
                reporter_id_obj = ObjectId(str(reporter_id_obj))
            
            user_doc = get_hr_collection().find_one({"_id": reporter_id_obj}, {"name": 1})
            
            return user_doc.get("name", "알 수 없는 사용자") if user_doc else "알 수 없는 사용자"
        except Exception as e:
            print(f"Error getting reporter name for ID {reporter_id_obj}: {e}") # 디버깅용
            return "알 수 없는 사용자"
    return "알 수 없는 사용자"


@issue_bp.route("/")
def home():
    family_map = {"Back family": "backend", "Front family": "frontend", "Publisher family": "ui"}
    status_map = {"신규 이슈": ISSUE_STATUS[1], "진행중인 이슈": ISSUE_STATUS[2], "퇴마된 이슈": ISSUE_STATUS[3]}

    users_map = {str(u["_id"]): u.get("name", "알 수 없는 사용자") 
                  for u in get_hr_collection().find({}, {"name": 1})}

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


@issue_bp.route("/list/<family_name>")
def show_list(family_name):
    if not is_valid_family(family_name): return "Invalid family", 400

    main_issue_collection = get_issues()
    
    total_issues_count = main_issue_collection.count_documents({"project_family": family_name})

    issues_cursor = main_issue_collection.find(
        {"project_family": family_name}
    ).sort("created_at", -1)

    users_map = {str(u["_id"]): u.get("name", "알 수 없는 사용자") 
                  for u in get_hr_collection().find({}, {"name": 1})}

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
            "client_company_name": issue.get("client_company_name", "고객사없음"), # DB에서 가져온 고객사 이름
            "created_at": _format_datetime(issue.get("created_at")),
            "updated_at": _format_datetime(issue.get("updated_at"))
        })

    # write_post에서 넘어온 고객사 이름을 받습니다.
    # 만약 URL에 이 파라미터가 없다면, 기본값 (예: "전체 고객사")을 사용합니다.
    # 'selected_client_name_from_write'로 이름을 명확히 했습니다.
    selected_client_name_from_write = request.args.get("selected_client_name_from_write", "전체 고객사")

    return render_template("issue/list.html", 
                           posts=posts, 
                           current_family=family_name,
                           # 이 변수를 템플릿으로 전달합니다.
                           client_company_display_name_on_top=selected_client_name_from_write)


@issue_bp.route("/write/<family_name>", methods=["GET"])
def write_get(family_name):
    if not is_valid_family(family_name): return "Invalid family", 400
    
    return render_template(
        "issue/write.html",
        current_family=family_name 
    )

@issue_bp.route("/write/<family_name>", methods=["POST"])
def write_post(family_name):
    if not is_valid_family(family_name): return "Invalid family", 400

    main_issue_collection = get_issues() 

    title = request.form.get("title")
    description = request.form.get("description")
    selected_client_company_id_str = request.form.get("client_company_id")
    # write.html에서 추가한 name="client_company_name_for_display" 필드의 값을 받습니다.
    # 이 값이 사용자가 선택한 고객사 이름입니다.
    selected_client_company_name_from_form = request.form.get("client_company_name_for_display")
    
    final_reporter_id = None 

    if current_user.is_authenticated:
        try:
            final_reporter_id = ObjectId(current_user.get_id()) 
        except Exception as e:
            print(f"Error converting current_user.id ({current_user.get_id()}) to ObjectId: {e}")
            final_reporter_id = None 
    else:
        print(f"No user logged in. Using None for reporter ID.")

    client_name_for_db, client_obj_id = None, None
    if selected_client_company_id_str:
        try:
            client_obj_id = ObjectId(selected_client_company_id_str)
            client_doc = get_clients().find_one({"_id": client_obj_id})
            if client_doc:
                # DB에 저장할 고객사 이름은 DB에서 조회된 이름 (정확한 데이터)을 사용합니다.
                client_name_for_db = client_doc.get("company_name", "알 수 없음")
        except Exception as e:
            print(f"Error processing client_company_id: {e}")
            return "유효하지 않은 고객사 ID입니다.", 400

    issue_data = {
        "title": title,
        "description": description,
        "category": "일반", 
        "reported_by": final_reporter_id, 
        "status": "신규", 
        "client_company_id": client_obj_id, 
        "client_company_name": client_name_for_db, # DB에 저장될 고객사 이름
        "project_family": family_name, 
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    
    main_issue_collection.insert_one(issue_data) 
    
    # 리다이렉트할 때, 폼에서 받은 고객사 이름을 URL 파라미터로 넘겨줍니다.
    # 이렇게 하면 show_list에서 이 값을 바로 사용할 수 있습니다.
    return redirect(url_for("issue.show_list", 
                            family_name=family_name,
                            selected_client_name_from_write=selected_client_company_name_from_form))
    

@issue_bp.route("/detail/<family_name>/<issue_id>")
def detail(family_name, issue_id):
    if not is_valid_family(family_name): return "Invalid family", 400
    
    try:
        issue = get_issues().find_one({"_id": ObjectId(issue_id), "project_family": family_name})
        if not issue: return "이슈를 찾을 수 없습니다.", 404

        issue["mongo_id"] = _to_str_or_default(issue.get("_id"))
        issue["reporter_name_display"] = _get_reporter_name(issue.get("reported_by")) 
        issue["client_company_id_str"] = _to_str_or_default(issue.get("client_company_id"))
        issue["created_at_str"] = _format_datetime(issue.get("created_at"))
        issue["updated_at_str"] = _format_datetime(issue.get("updated_at"))
        issue["client_company_name_display"] = issue.get("client_company_name", "고객사없음")

        return render_template("issue/detail.html", issue=issue, current_family=family_name)
    except Exception as e:
        print(f"Error loading issue detail: {e}") 
        return f"유효하지 않은 이슈 ID입니다: {e}", 400


@issue_bp.route("/edit/<family_name>/<issue_id>", methods=["GET"])
def edit_get(family_name, issue_id):
    if not is_valid_family(family_name): return "Invalid family", 400

    main_issue_collection = get_issues()

    try:
        issue = main_issue_collection.find_one({"_id": ObjectId(issue_id), "project_family": family_name})
        if not issue:
            return "수정할 이슈를 찾을 수 없습니다.", 404

        issue['mongo_id'] = _to_str_or_default(issue.get("_id"))
        issue['client_company_id_str'] = _to_str_or_default(issue.get("client_company_id"))
        # client_company_name_for_input 값을 edit 페이지 폼에 미리 채워줍니다.
        issue['client_company_name_for_input'] = issue.get("client_company_name", "")

        status_options = []
        for id, name in ISSUE_STATUS.items():
            status_options.append({"id": id, "name": name, "selected": (name == issue.get("status"))})
        
        return render_template("issue/update.html",
                               issue=issue, 
                               current_family=family_name,
                               status_options=status_options)
    except Exception as e:
        print(f"Error loading issue for edit: {e}") 
        return f"이슈 로드 오류: {e}", 400

@issue_bp.route("/edit/<family_name>/<issue_id>", methods=["POST"])
def edit_post(family_name, issue_id):
    if not is_valid_family(family_name): return "Invalid family", 400

    main_issue_collection = get_issues()

    title = request.form.get("title")
    description = request.form.get("description")
    status_name = request.form.get("status") 
    selected_client_company_id_str = request.form.get("client_company_id")
    # edit 페이지에서도 고객사 이름 입력 필드에 name을 추가했다면 받아올 수 있습니다.
    # 여기서는 DB에 저장된 이름을 사용하므로 이 변수는 필수는 아닙니다.
    # selected_client_company_name_from_form = request.form.get("client_company_name_for_display")


    client_name_to_save, client_obj_id = None, None
    if selected_client_company_id_str:
        try:
            client_obj_id = ObjectId(selected_client_company_id_str)
            client_doc = get_clients().find_one({"_id": client_obj_id})
            if client_doc:
                client_name_to_save = client_doc.get("company_name", "알 수 없음")
        except Exception as e:
            print(f"Error processing client_company_id for update: {e}")
            return "유효하지 않은 고객사 ID입니다.", 400

    update_data = {
        "$set": {
            "title": title,
            "description": description,
            "status": status_name, 
            "client_company_id": client_obj_id,
            "client_company_name": client_name_to_save, # DB에 저장될 고객사 이름
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
        print(f"이슈 업데이트 오류: {e}") 
        return f"이슈 업데이트 오류: {e}", 500


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
        print(f"상태 업데이트 오류: {e}")
        return f"상태 업데이트 오류: {e}", 500


@issue_bp.route("/search_client", methods=["POST"])
def search_client():
    term = request.json.get("search_term", "").strip()
    if not term: return jsonify([])

    results = get_clients().find({"company_name": {"$regex": term, "$options": "i"}}).limit(10)
    return jsonify([{"id": _to_str_or_default(c.get("_id")), "name": c.get("company_name", "이름없음")} for c in results])

@issue_bp.route("/stats")
def stats():
    project_families = ["backend", "frontend", "ui"]
    
    all_family_stats = {}

    for family_name in project_families:
        pipeline = [
            {"$match": {"project_family": family_name}}, 
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            {"$project": {"_id": 0, "status": "$_id", "count": 1}}
        ]
        
        status_counts_cursor = get_issues().aggregate(pipeline)
        
        status_data = {}
        for item in status_counts_cursor:
            status_data[item['status']] = item['count']
                
        chart_data_for_family = []
        for status_id, status_name in ISSUE_STATUS.items():
            count = status_data.get(status_name, 0)
            chart_data_for_family.append({
                "label": status_name,
                "value": count
            })
        
        total_issues_for_family = get_issues().count_documents({"project_family": family_name})

        all_family_stats[family_name] = {
            "chart_data": chart_data_for_family,
            "total_issues": total_issues_for_family
        }
    
    overall_total_issues = get_issues().count_documents({})
            
    return render_template(
        "issue/stats.html",
        all_family_stats_json=json.dumps(all_family_stats), 
        overall_total_issues=overall_total_issues 
    )

@issue_bp.route("/api/stats")
def api_status_statistics():
    project_families = ["backend", "frontend", "ui"]
    all_family_stats = {}

    for family_name in project_families:
        pipeline = [
            {"$match": {"project_family": family_name}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            {"$project": {"_id": 0, "status": "$_id", "count": 1}}
        ]
        
        status_counts_cursor = get_issues().aggregate(pipeline)
        
        status_data = {}
        for item in status_counts_cursor:
            status_data[item['status']] = item['count']
                
        chart_data_for_family = []
        for status_id, status_name in ISSUE_STATUS.items():
            count = status_data.get(status_name, 0)
            chart_data_for_family.append({
                "label": status_name,
                "value": count
            })
        
        total_issues_for_family = get_issues().count_documents({"project_family": family_name})

        all_family_stats[family_name] = {
            "chart_data": chart_data_for_family,
            "total_issues": total_issues_for_family
        }
            
    overall_total_issues = get_issues().count_documents({})

    return jsonify({
        "all_family_stats": all_family_stats,
        "overall_total_issues": overall_total_issues
    })