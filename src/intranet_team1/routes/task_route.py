from io import BytesIO
from flask import Blueprint, jsonify, render_template, request, redirect, url_for, send_from_directory, Response, current_app, flash
from matplotlib.figure import Figure
from db import mongo_db
from bson import ObjectId
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import gridfs

fs = gridfs.GridFS(mongo_db)  # mongo_db는 MongoClient().db

task_bp = Blueprint('task', __name__, url_prefix="/task")

# {
#   "_id": ObjectId,
#   "team": "개발팀" | "영업팀",
#   "title": "업무 제목",
#   "description": "업무 상세 설명",
#   "status": "대기중" | "진행중" | "완료",
#   "priority": "낮음" | "보통" | "높음",
#   "due_date": ISODate,
#   "created_at": ISODate,
#   "file": "첨부파일 포함" | "첨부파일 없음"
# }

def get_tasks_collection():
    return mongo_db["tasks"]


# 업무 메인화면
@task_bp.route('/', methods=['GET'])
def home():
    team_filter = request.args.get('team')
    status_filter = request.args.get('status')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = {}
    filter_reset = False # 초기화 여부 플래그
    
    if team_filter and team_filter != '전체':
        query['team'] = team_filter
    if status_filter and status_filter != '전체':
        query['status'] = status_filter
    if start_date and end_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            if start_dt > end_dt:
                flash("⚠ 시작일은 종료일보다 늦을 수 없습니다.", "warning")
                team_filter = None
                status_filter = None
                start_date = None
                end_date = None
                query = {}  # 전체 조회로 초기화
                filter_reset = True
            else:
                query['due_date'] = {"$gte": start_dt, "$lte": end_dt}
        except ValueError:
            flash("⚠ 날짜 형식이 잘못되었습니다.", "warning")
            team_filter = None
            status_filter = None
            start_date = None
            end_date = None
            query = {}
            filter_reset = True

    task_list = get_tasks_collection().find(query).sort("due_date", -1)
    departments = mongo_db["hr"].distinct("department")
    return render_template('task/index.html', tasks=task_list, today=datetime.today().date(), departments=departments, filter_reset=filter_reset)

# 업무 추가 폼
@task_bp.route('/add', methods=['GET'])
def add_get():
    departments = mongo_db["hr"].distinct("department")
    return render_template('task/add.html', departments=departments)

# 업무 추가 처리 POST함수
@task_bp.route('/add', methods=['POST'])
def add_post():
    # 마감일 처리
    if 'no_due_date' in request.form:
        due_date = None
    else:
        due_date_str = request.form.get('due_date')
        if not due_date_str:
            flash("⚠ 마감일은 반드시 입력하거나 '미정'을 선택해야 합니다.", "danger")
            return redirect(url_for('task.add_get'))
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d')

    file = request.files.get('file')
    if file and file.filename:
        file_id = fs.put(file, filename=file.filename)
        file_name = file.filename
    else:
        file_id = None
        file_name = None

    data = {
        'title': request.form['title'],
        'team': request.form['team'],
        'status': request.form['status'],
        'priority': request.form['priority'],
        'due_date': due_date,
        'file_id': file_id,
        'file_name': file_name,
        'created_at': datetime.now(),
        'updated_at': datetime.now()
    }

    get_tasks_collection().insert_one(data)
    flash("업무가 등록되었습니다.", "success")
    return redirect(url_for('task.home'))

# 업무 수정 폼
@task_bp.route('/edit/<task_id>', methods=['GET'])
def edit_get(task_id):
    departments = mongo_db["hr"].distinct("department")
    task = get_tasks_collection().find_one({'_id': ObjectId(task_id)})
    return render_template('task/edit.html', task=task, today=datetime.today().date(), departments=departments)

# 업무 수정 처리 POST함수
@task_bp.route('/edit/<task_id>', methods=['POST'])
def edit_post(task_id):
    update = {
        'title': request.form['title'],
        'team': request.form['team'],
        'status': request.form['status'],
        'priority': request.form['priority'],
        'updated_at': datetime.now()
    }

    # 마감일 처리
    if 'no_due_date' in request.form:
        update['due_date'] = None
    else:
        due_date_str = request.form.get('due_date')
        if not due_date_str:
            flash("⚠ 마감일은 반드시 입력하거나 '미정'을 선택해야 합니다.", "danger")
            return redirect(url_for('task.edit_get', task_id=task_id))
        update['due_date'] = datetime.strptime(due_date_str, '%Y-%m-%d')

    # 파일 업로드 처리
    file = request.files.get('file')
    if file and file.filename:
        file_id = fs.put(file, filename=file.filename)
        update['file_id'] = file_id
        update['file_name'] = file.filename
        
    get_tasks_collection().update_one({'_id': ObjectId(task_id)}, {'$set': update})
    flash("업무가 수정되었습니다.", "success")
    return redirect(url_for('task.home'))

# 업무 삭제 처리 POST함수
@task_bp.route('/delete/<task_id>', methods=['POST'])
def delete(task_id):
    task = get_tasks_collection().find_one({'_id': ObjectId(task_id)})

    # 파일 삭제
    file_id = task.get('file_id')
    if file_id:
        try:
            fs.delete(ObjectId(file_id))
        except:
            pass  # 파일이 없거나 이미 삭제된 경우 무시

    # 업무 삭제
    get_tasks_collection().delete_one({'_id': ObjectId(task_id)})
    flash("업무가 삭제되었습니다.", "success")
    return redirect(url_for('task.home'))

@task_bp.route('/stat')
def stat():
    return render_template('task/stat.html')

@task_bp.route('/api/chart-data')
def chart_data():
    result = list(get_tasks_collection().aggregate([
        {"$group": {"_id": {"date": "$due_date", "status": "$status"}, "count": {"$sum": 1}}},
        {"$sort": {"_id.date": 1}}
    ]))

    data = {}
    for item in result:
        date = item['_id']['date'].strftime('%Y-%m-%d') if hasattr(item['_id']['date'], 'strftime') else str(item['_id']['date'])
        status = item['_id']['status']
        if date not in data:
            data[date] = {}
        data[date][status] = item['count']

    return jsonify(data)

@task_bp.route('/api/chart-by-team')
def chart_by_team_api():
    result = list(get_tasks_collection().aggregate([
        {"$group": {"_id": {"team": "$team", "status": "$status"}, "count": {"$sum": 1}}},
        {"$sort": {"_id.team": 1}}
    ]))

    data = {}
    for item in result:
        team = item['_id']['team']
        status = item['_id']['status']
        if team not in data:
            data[team] = {}
        data[team][status] = item['count']

    return jsonify(data)