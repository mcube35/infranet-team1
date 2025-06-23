from flask import Blueprint, render_template, redirect, request, url_for, jsonify
from db import mongo_db 
from datetime import datetime
from bson.objectid import ObjectId

# http://127.0.0.1:5000/issue
issue_bp = Blueprint("issue", __name__)

# --- 전역 상수/매핑 정의 ---

# 상태 ID와 이름 매핑 (1:신규, 2:진행중, 3:해결됨)
STATUS_MAP = {
    1: "신규",
    2: "진행중",
    3: "해결됨" 
}

# 컬렉션 반환 헬퍼 함수
# 유효한 family_name인지 이 함수에서 확인합니다.
def get_issue_collection(family_name):
    if family_name == "backend":
        return mongo_db["backend_issues"]
    elif family_name == "frontend":
        return mongo_db["frontend_issues"]
    elif family_name == "ui":
        return mongo_db["ui_issues"]
    else:
        raise ValueError(f"Invalid issue family: {family_name}")

def get_clients_collection():
    return mongo_db["clients"] 

# 임시 보고자 ID (실제 애플리케이션에서는 로그인된 사용자 ID를 사용해야 합니다.)
DUMMY_REPORTER_ID = ObjectId("60c72b2f9b1d8e001c8c4a03")

# --- 이슈 메인 페이지 (index.html 렌더링) ---
@issue_bp.route("/")
def home():
    # 화면에 표시될 "가족" 이름과 MongoDB 컬렉션 접두사 매핑
    # 이 딕셔너리를 템플릿으로도 전달하여, 올바른 URL 파라미터를 생성하는 데 사용합니다.
    family_categories = {
        "Back family": "backend",      
        "Front family": "frontend",    
        "Publisher family": "ui" 
    }
    
    # 화면에 표시될 "상태" 이름과 DB에 저장된 실제 'status' 필드 값을 매핑합니다.
    display_statuses_map = {
        "신규 이슈": STATUS_MAP[1],      
        "진행중인 이슈": STATUS_MAP[2],   
        "퇴마된 이슈": STATUS_MAP[3]      
    }

    issues_by_family_and_status = {}

    for display_family_name, db_family_prefix in family_categories.items():
        issues_by_family_and_status[display_family_name] = {}
        current_collection = get_issue_collection(db_family_prefix) 

        for display_status_name, db_status_value in display_statuses_map.items():
            issues_cursor = current_collection.find(
                {
                    "status": db_status_value         
                }
            ).sort("created_at", -1).limit(3) 

            issue_list = []
            for issue in issues_cursor:
                issue_list.append({
                    "title": issue.get("title", "제목없음"),
                    "mongo_id": str(issue.get("_id")),
                    "family_name": db_family_prefix # 이 이슈가 속한 family_name (backend, frontend, ui)
                })
            issues_by_family_and_status[display_family_name][display_status_name] = issue_list

    # issues_by_family_and_status와 함께 family_categories도 템플릿에 전달합니다.
    return render_template("issue/index.html", 
                           issues_by_family_and_status=issues_by_family_and_status,
                           family_categories=family_categories)


# --- 이슈 리스트 화면 (동적으로 컬렉션 선택) ---
@issue_bp.route("/list/<family_name>", methods=["GET"])
def show_list(family_name):
    try:
        current_collection = get_issue_collection(family_name)
    except ValueError as e:
        return str(e), 400 

    issues_cursor = current_collection.find().sort("created_at", -1)
    posts = []
    for i, issue in enumerate(issues_cursor, start=1):
        posts.append({
            "display_id": i, 
            "mongo_id": str(issue.get("_id")), 
            "title": issue.get("title", "제목없음"),
            "description": issue.get("description", "내용없음"), 
            "category": issue.get("category", "일반"), 
            "status": issue.get("status", "상태없음"), 
            "reported_by_id": str(issue.get("reported_by")) if issue.get("reported_by") else "없음", 
            "client_company_id": str(issue.get("client_company_id")) if issue.get("client_company_id") else "없음", 
            "client_company_name": issue.get("client_company_name", "고객사없음"), 
            "assigned_to_id": str(issue.get("assigned_to")) if issue.get("assigned_to") else "없음", 
            "created_at": issue.get("created_at").strftime("%Y-%m-%d %H:%M") if issue.get("created_at") else "날짜없음",
            "updated_at": issue.get("updated_at").strftime("%Y-%m-%d %H:%M") if issue.get("updated_at") else "날짜없음"
        })
    return render_template("issue/backend_list.html", posts=posts, current_family=family_name)

# --- 이슈 작성 폼 및 처리 (동적으로 컬렉션 선택) ---
@issue_bp.route("/write/<family_name>", methods=["GET", "POST"])
def write(family_name):
    try:
        current_collection = get_issue_collection(family_name)
    except ValueError as e:
        return str(e), 400

    DUMMY_CLIENT_COMPANY_ID_OBJ = ObjectId("60c72b2f9b1d8e001c8c4a04") 
    DUMMY_CLIENT_COMPANY_NAME = "ABC 주식회사" 

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description") 
        status_id_str = request.form.get("status_id") 
        selected_client_company_id_str = request.form.get("client_company_id") 

        status_id = int(status_id_str)
        status_name = STATUS_MAP.get(status_id, "알 수 없음") 

        client_company_name = None 
        client_company_obj_id = None
        if selected_client_company_id_str:
            try:
                client_company_obj_id = ObjectId(selected_client_company_id_str)
                client_doc = get_clients_collection().find_one({"_id": client_company_obj_id})
                if client_doc:
                    client_company_name = client_doc.get("name", "알 수 없음")
            except Exception as e:
                print(f"고객사 ID 변환 또는 조회 오류: {e}")
                return "유효하지 않은 고객사 ID입니다.", 400

        issue_data = {
            "title": title,
            "description": description,
            "category": "일반",
            "reported_by": DUMMY_REPORTER_ID,
            "assigned_to": None,
            "status_id": status_id, 
            "status": status_name,   
            "client_company_id": client_company_obj_id, 
            "client_company_name": client_company_name, 
            "project_family": family_name, # 현재 URL의 family_name을 project_family로 저장
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        
        current_collection.insert_one(issue_data) 
        
        return redirect(url_for("issue.show_list", family_name=family_name)) 
    
    else: 
        return render_template(
            "issue/write.html",
            category_name=STATUS_MAP.get(1), 
            current_family=family_name 
        )

# --- 이슈 상세보기 (동적으로 컬렉션 선택) ---
@issue_bp.route("/detail/<family_name>/<issue_id>")
def detail(family_name, issue_id):
    try:
        current_collection = get_issue_collection(family_name)
    except ValueError as e:
        return str(e), 400

    try:
        issue = current_collection.find_one({"_id": ObjectId(issue_id)})
        if issue:
            issue['reported_by_str'] = str(issue['reported_by']) if 'reported_by' in issue and issue['reported_by'] else '없음'
            issue['assigned_to_str'] = str(issue['assigned_to']) if 'assigned_to' in issue and issue['assigned_to'] else '없음'
            issue['client_company_id_str'] = str(issue['client_company_id']) if 'client_company_id' in issue and issue['client_company_id'] else '없음'
            issue['created_at_str'] = issue['created_at'].strftime("%Y-%m-%d %H:%M") if 'created_at' in issue else '날짜없음'
            issue['updated_at_str'] = issue['updated_at'].strftime("%Y-%m-%d %H:%M") if 'updated_at' in issue else '날짜없음'
            issue['client_company_name_display'] = issue.get('client_company_name', '고객사없음') 

            return render_template("issue/detail.html", issue=issue, current_family=family_name)
        else:
            return "이슈를 찾을 수 없습니다.", 404
    except Exception as e:
        return f"유효하지 않은 이슈 ID입니다: {e}", 400

# --- 이슈 상태 업데이트 라우트 (동적으로 컬렉션 선택) ---
@issue_bp.route("/update_status/<family_name>/<issue_id>", methods=["POST"])
def update_status(family_name, issue_id):
    try:
        current_collection = get_issue_collection(family_name)
    except ValueError as e:
        return str(e), 400

    new_status = request.form.get("new_status")
    if not new_status:
        return "새로운 상태가 필요합니다.", 400

    try:
        current_collection.update_one(
            {"_id": ObjectId(issue_id)},
            {"$set": {"status": new_status, "updated_at": datetime.now()}}
        )
        return redirect(url_for("issue.detail", family_name=family_name, issue_id=issue_id))
    except Exception as e:
        return f"상태 업데이트 오류: {e}", 500

# --- 고객사 검색 API 엔드포인트 ---
@issue_bp.route("/search_client", methods=["POST"])
def search_client():
    search_term = request.json.get("search_term", "").strip()
    
    if not search_term:
        return jsonify([])

    clients_cursor = get_clients_collection().find({
        "$or": [
            {"name": {"$regex": search_term, "$options": "i"}},
        ]
    }).limit(10)

    results = []
    for client in clients_cursor:
        results.append({
            "id": str(client["_id"]), 
            "name": client["name"]
        })
    return jsonify(results)
