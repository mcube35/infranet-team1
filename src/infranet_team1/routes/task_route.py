from io import BytesIO
from flask import Blueprint, Response, render_template, request, redirect, url_for, send_from_directory, jsonify, current_app
from matplotlib import pyplot as plt
from db import mongo, task_repo
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
from datetime import datetime
import os

import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams["font.family"] = "Malgun Gothic"

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

@task_bp.route('/')
def home():
    team = request.args.get('team')
    status = request.args.get('status')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    task_list = task_repo.get_filtered_tasks(team, status, start_date, end_date)
    return render_template('task/index.html', tasks=task_list)


@task_bp.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
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

        mongo.db.tasks.insert_one(data)
        return redirect(url_for('task.home'))

    return render_template('task/add.html')


@task_bp.route('/edit/<task_id>', methods=['GET', 'POST'])
def edit(task_id):
    task = mongo.db.tasks.find_one({'_id': ObjectId(task_id)})
    if request.method == 'POST':
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

        mongo.db.tasks.update_one({'_id': ObjectId(task_id)}, {'$set': update})
        return redirect(url_for('task.home'))

    return render_template('task/edit.html', task=task)


@task_bp.route('/delete/<task_id>')
def delete(task_id):
    mongo.db.tasks.delete_one({'_id': ObjectId(task_id)})
    return redirect(url_for('task.home'))


@task_bp.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@task_bp.route('/chart-image')
def chart_image():
    raw_result = task_repo.daily_status_counts()

    # 날짜별 상태별 집계 정리
    data = {}
    for item in raw_result:
        date = item['_id']['date']
        if isinstance(date, datetime):
            date = date.strftime('%Y-%m-%d')
        else:
            date = str(date)

        status = item['_id']['status']
        if date not in data:
            data[date] = {'대기중': 0, '진행중': 0, '완료': 0}
        data[date][status] = item['count']

    # 데이터 분리
    dates = sorted(data)
    wait = [data[d]['대기중'] for d in dates]
    doing = [data[d]['진행중'] for d in dates]
    done = [data[d]['완료'] for d in dates]

    # 시각화
    plt.figure(figsize=(10, 5))
    plt.bar(dates, wait, label='대기중')
    plt.bar(dates, doing, bottom=wait, label='진행중')
    plt.bar(dates, done, bottom=[w + d for w, d in zip(wait, doing)], label='완료')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.legend()

    # 이미지 응답
    img = BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    return Response(img.getvalue(), content_type='image/png')