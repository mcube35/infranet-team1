from io import BytesIO
from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, Response, current_app
from matplotlib import pyplot as plt
from db import mongo_db
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
from datetime import datetime
import os

task_bp = Blueprint('task', __name__)

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
        query['due_date'] = {"$gte": start_date, "$lte": end_date}

    task_list = get_tasks_collection().find(query).sort("due_date", -1)
    return render_template('task/index.html', tasks=task_list)


# 업무 추가 폼
@task_bp.route('/add', methods=['GET'])
def add_form():
    return render_template('task/add.html')

# 업무 추가 처리 POST함수
@task_bp.route('/add', methods=['POST'])
def add():
    data = {
        'title': request.form['title'],
        'description': request.form['description'],
        'status': request.form['status'],
        'priority': request.form['priority'],
        'team': request.form['team'],
        'due_date': datetime.strptime(request.form['due_date'], '%Y-%m-%d'),
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
    }

    file = request.files['file']
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
        data['file'] = filename
    else:
        data['file'] = '첨부파일 없음'

    get_tasks_collection().insert_one(data)
    return redirect(url_for('task.home'))

# 업무 수정 폼
@task_bp.route('/edit/<task_id>', methods=['GET'])
def edit_form(task_id):
    task = get_tasks_collection().find_one({'_id': ObjectId(task_id)})
    return render_template('task/edit.html', task=task)

# 업무 수정 처리 POST함수
@task_bp.route('/edit/<task_id>', methods=['POST'])
def edit(task_id):
    update = {
        'title': request.form['title'],
        'description': request.form['description'],
        'status': request.form['status'],
        'priority': request.form['priority'],
        'team': request.form['team'],
        'due_date': datetime.strptime(request.form['due_date'], '%Y-%m-%d'),
        'updated_at': datetime.now()
    }

    file = request.files['file']
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
        update['file'] = filename

    get_tasks_collection().update_one({'_id': ObjectId(task_id)}, {'$set': update})
    return redirect(url_for('task.home'))

# 업무 삭제 처리 POST함수
@task_bp.route('/delete/<task_id>', methods=['POST'])
def delete(task_id):
    get_tasks_collection().delete_one({'_id': ObjectId(task_id)})
    return redirect(url_for('task.home'))


@task_bp.route('/uploads/<filename>', methods=['GET'])
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


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

    plt.figure(figsize=(10, 5))
    plt.bar(dates, wait, label='대기중')
    plt.bar(dates, doing, bottom=wait, label='진행중')
    plt.bar(dates, done, bottom=[w + d for w, d in zip(wait, doing)], label='완료')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.legend()

    img = BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    return Response(img.getvalue(), content_type='image/png')