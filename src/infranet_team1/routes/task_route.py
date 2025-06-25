from io import BytesIO
from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, Response, current_app, flash
from matplotlib.figure import Figure
from db import mongo_db
from bson import ObjectId
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import gridfs

fs = gridfs.GridFS(mongo_db)  # mongo_db는 MongoClient().db

task_bp = Blueprint('task', __name__, url_prefix='/task')

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
    if team_filter and team_filter != '전체':
        query['team'] = team_filter
    if status_filter and status_filter != '전체':
        query['status'] = status_filter
    if start_date and end_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            query['due_date'] = {"$gte": start_dt, "$lte": end_dt}
        except ValueError:
            pass

    task_list = get_tasks_collection().find(query).sort("due_date", -1)
    return render_template('task/index.html', tasks=task_list)

# 업무 추가 폼
@task_bp.route('/add', methods=['GET'])
def add_get():
    return render_template('task/add.html')

# 업무 추가 처리 POST함수
@task_bp.route('/add', methods=['POST'])
def add_post():
    due_date_str = request.form.get('due_date')
    if not due_date_str:
        flash("⚠ 마감일은 반드시 입력해야 합니다.")
        return redirect(url_for('task.add_get'))

    file = request.files.get('file')
    file_id = None

    if file and file.filename:
        file_id = fs.put(file, filename=file.filename)

    data = {
        'title': request.form['title'],
        'team': request.form['team'],
        'status': request.form['status'],
        'priority': request.form['priority'],
        'due_date': datetime.strptime(due_date_str, '%Y-%m-%d'),
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
        'file_id': file_id,
    }

    get_tasks_collection().insert_one(data)
    flash("업무가 등록되었습니다.", "success")
    return redirect(url_for('task.home'))

# 업무 수정 폼
@task_bp.route('/edit/<task_id>', methods=['GET'])
def edit_get(task_id):
    task = get_tasks_collection().find_one({'_id': ObjectId(task_id)})
    return render_template('task/edit.html', task=task)

# 업무 수정 처리 POST함수
@task_bp.route('/edit/<task_id>', methods=['POST'])
def edit_post(task_id):
    due_date_str = request.form.get('due_date')
    if not due_date_str:
        flash("⚠ 마감일은 반드시 입력해야 합니다.", "danger")
        return redirect(url_for('task.edit_get', task_id=task_id))
    
    update = {
        'title': request.form['title'],
        'team': request.form['team'],
        'status': request.form['status'],
        'priority': request.form['priority'],
        'due_date': datetime.strptime(due_date_str, '%Y-%m-%d'),
        'updated_at': datetime.now()
    }

    file = request.files.get('file')
    if file and file.filename:
        file_id = fs.put(file, filename=file.filename)
        update['file_id'] = file_id

    get_tasks_collection().update_one({'_id': ObjectId(task_id)}, {'$set': update})
    flash("업무가 수정되었습니다.", "success")
    return redirect(url_for('task.home'))

# 업무 삭제 처리 POST함수
@task_bp.route('/delete/<task_id>', methods=['POST'])
def delete(task_id):
    get_tasks_collection().delete_one({'_id': ObjectId(task_id)})
    return redirect(url_for('task.home'))

@task_bp.route('/file/<file_id>', methods=['GET'])
def download_file(file_id):
    try:
        file_obj = fs.get(ObjectId(file_id))
        return Response(
            file_obj.read(),
            mimetype='application/octet-stream',
            headers={"Content-Disposition": f"attachment;filename={file_obj.filename}"}
        )
    except Exception:
        return "파일을 찾을 수 없습니다.", 404

# 통계 시각화 이미지
@task_bp.route('/chart-image', methods=['GET'])
def chart_image():
    result = list(get_tasks_collection().aggregate([
        {"$group": {"_id": {"date": "$due_date", "status": "$status"}, "count": {"$sum": 1}}},
        {"$sort": {"_id.date": 1}}
    ]))

    # 날짜별로 상태별 집계
    data = {}
    for item in result:
        date = item['_id']['date'].strftime('%Y-%m-%d') if isinstance(item['_id']['date'], datetime) else str(item['_id']['date'])
        status = item['_id']['status']
        if date not in data:
            data[date] = {'대기중': 0, '진행중': 0, '완료': 0}
        data[date][status] = item['count']

    # matplotlib 시각화
    dates = sorted(data)
    wait = [data[d]['대기중'] for d in dates]
    doing = [data[d]['진행중'] for d in dates]
    done = [data[d]['완료'] for d in dates]

    fig = Figure(figsize=(10, 5))
    ax = fig.subplots()
    ax.bar(dates, wait, label='대기중')
    ax.bar(dates, doing, bottom=wait, label='진행중')
    ax.bar(dates, done, bottom=[w + d for w, d in zip(wait, doing)], label='완료')
    ax.set_xticklabels(dates, rotation=45)
    ax.legend()
    fig.tight_layout()

    img = BytesIO()
    fig.savefig(img, format='png')
    img.seek(0)
    return Response(img.getvalue(), content_type='image/png')

@task_bp.route('/chart-by-team', methods=['GET'])
def chart_by_team():
    result = list(get_tasks_collection().aggregate([
        {"$group": {
            "_id": {"team": "$team", "status": "$status"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id.team": 1}}
    ]))

    data = {}
    for item in result:
        team = item['_id']['team']
        status = item['_id']['status']
        if team not in data:
            data[team] = {'대기중': 0, '진행중': 0, '완료': 0}
        data[team][status] = item['count']

    teams = list(data.keys())
    wait = [data[t]['대기중'] for t in teams]
    doing = [data[t]['진행중'] for t in teams]
    done = [data[t]['완료'] for t in teams]

    fig = Figure(figsize=(10, 5))
    ax = fig.subplots()
    ax.bar(teams, wait, label='대기중')
    ax.bar(teams, doing, bottom=wait, label='진행중')
    ax.bar(teams, done, bottom=[w + d for w, d in zip(wait, doing)], label='완료')
    ax.set_title('팀별 업무 상태 분포')
    ax.set_ylabel('업무 수')
    ax.set_xticklabels(teams, rotation=0)
    ax.legend()
    fig.tight_layout()

    img = BytesIO()
    fig.savefig(img, format='png')
    img.seek(0)
    return Response(img.getvalue(), content_type='image/png')

@task_bp.route('/stat', methods=['GET'])
def stat():
    return render_template('task/stat.html')