from datetime import timedelta
import io
import platform
import os # os 모듈 임포트 추가

from flask import Flask, jsonify, render_template, request, redirect, url_for, send_file
from flask_login import LoginManager, current_user
from db import mongo_db # db.py 파일이 같은 레벨에 있다고 가정

# Blueprint 임포트
from routes.write_route import write_bp
from routes.task_route import task_bp
from routes.issue_route import issue_bp
from routes.client_route import client_bp
from routes.auth_route import auth_bp

from routes.hr.att_route import att_bp
from routes.hr.vc_route import vacation_bp
from routes.hr.vc_admin_route import vacation_admin_bp
from routes.hr.emp_admin_route import emp_admin_bp
from routes.hr.hr_stats_route import hr_stats_bp

from bson.objectid import ObjectId
from models.user import User # models/user.py 파일이 있다고 가정
from extension import get_fs # extension.py 파일이 있다고 가정


import matplotlib
matplotlib.use('Agg')
os_system = platform.system()
if os_system == "Windows":
    matplotlib.rcParams['font.family'] = 'Malgun Gothic'
elif os_system == "Darwin":  # macOS
    matplotlib.rcParams['font.family'] = 'AppleGothic'
else:  # Linux (Ubuntu 등)
    matplotlib.rcParams['font.family'] = 'NanumGothic'
matplotlib.rcParams["axes.unicode_minus"] = False  # 마이너스 부호 깨짐 방지

app = Flask(__name__)
# 디버깅을 위해 Flask가 템플릿을 찾는 경로 출력 (문제 발생 시 확인용)
print(f"Flask is looking for templates in: {app.template_folder}")

app.config["SECRET_KEY"] = "bg21PZAji2190OnfnUj291AQmni21PpPSN0" # 강력한 시크릿 키로 변경 권장
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=False, # HTTPS 사용 시 True로 설정
    REMEMBER_COOKIE_HTTPONLY=True,
)
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)

login_manager = LoginManager(app)
login_manager.login_view = "auth.login_get" # 로그인 뷰 이름 변경
login_manager.session_protection = "strong"

@login_manager.user_loader
def load_user(user_id):
    user_data = mongo_db.hr.find_one({"_id": ObjectId(user_id)})
    if user_data:
        return User(user_data)
    return None

@app.before_request
def require_login():
    # 로그인 없이 접근 허용할 라우트 목록 (예: 로그인 페이지, 정적 파일)
    # 'auth.login' -> 'auth.login_get'으로 변경
    allowed_routes = ['auth.login_get', 'auth.login_post', 'static']
    if (not current_user.is_authenticated 
        and request.endpoint 
        and not any(request.endpoint.startswith(route) for route in allowed_routes)):
        return redirect(url_for('auth.login_get'))

@app.route("/", methods=['GET'])
def home():
    return render_template("index.html", user=current_user)


@app.route("/files/<file_id>", methods=['GET'])
def file_download(file_id):
    try:
        fs = get_fs() # extension.py에서 get_fs 함수를 가져옴
        file_obj = fs.get(ObjectId(file_id))
        return send_file(
            io.BytesIO(file_obj.read()),
            mimetype=file_obj.content_type or "application/octet-stream",
            download_name=file_obj.filename or "download",
            as_attachment=True
        )
    except Exception as e: # 실제 운영에서는 더 구체적인 예외 처리 필요
        print(f"File download error for {file_id}: {e}")
        return jsonify({"error": "파일을 찾을 수 없습니다."}), 404

# Blueprint 등록
app.register_blueprint(write_bp, url_prefix="/write")
app.register_blueprint(task_bp, url_prefix="/task")
app.register_blueprint(att_bp)
app.register_blueprint(vacation_bp)
app.register_blueprint(vacation_admin_bp)
app.register_blueprint(emp_admin_bp)
app.register_blueprint(hr_stats_bp)
app.register_blueprint(issue_bp, url_prefix="/issue") # 이슈 Blueprint는 /issue 접두사로 등록
app.register_blueprint(client_bp, url_prefix="/client")
app.register_blueprint(auth_bp, url_prefix="/auth")

if __name__ == '__main__':
    app.run(debug=True)