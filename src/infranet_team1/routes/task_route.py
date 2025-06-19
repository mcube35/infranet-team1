from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, jsonify, current_app
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
from datetime import datetime
import os

client = MongoClient('mongodb://localhost:27017/')
db = client['task_dashboard']
tasks = db['tasks']

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

    task_list = tasks.find(query).sort("due_date", -1)
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
            'due_date': request.form['due_date'],
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

        tasks.insert_one(data)
        return redirect(url_for('task.home'))

    return render_template('task/add.html')

@task_bp.route('/edit/<task_id>', methods=['GET', 'POST'])
def edit(task_id):
    task = tasks.find_one({'_id': ObjectId(task_id)})
    if request.method == 'POST':
        update = {
            'title': request.form['title'],
            'description': request.form['description'],
            'status': request.form['status'],
            'priority': request.form['priority'],
            'team': request.form['team'],
            'due_date': request.form['due_date'],
            'updated_at': datetime.now()
        }

        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            update['file'] = filename

        tasks.update_one({'_id': ObjectId(task_id)}, {'$set': update})
        return redirect(url_for('task.home'))

    return render_template('task/edit.html', task=task)

@task_bp.route('/delete/<task_id>')
def delete(task_id):
    tasks.delete_one({'_id': ObjectId(task_id)})
    return redirect(url_for('task.home'))

@task_bp.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@task_bp.route('/chart-data')
def chart_data():
    pipeline = [
        {"$group": {"_id": {"date": "$due_date", "status": "$status"}, "count": {"$sum": 1}}},
        {"$sort": {"_id.date": 1}}
    ]
    result = list(tasks.aggregate(pipeline))
    data = {}
    for item in result:
        date = item['_id']['date']
        status = item['_id']['status']
        if date not in data:
            data[date] = {'대기중': 0, '진행중': 0, '완료': 0}
        data[date][status] = item['count']
    return jsonify(data)