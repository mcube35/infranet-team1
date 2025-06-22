from datetime import timedelta
import io
from flask import Flask, jsonify, render_template, request, redirect, url_for, send_file
from flask_login import LoginManager, current_user
from db import mongo

from routes.write_route import write_bp
from routes.task_route import task_bp
from routes.issue_route import issue_bp
from routes.client_route import client_bp
from routes.auth_route import auth_bp

from routes.hr.bp import hr_bp
import routes.hr.att_route

from bson.objectid import ObjectId
from models.user import User

def get_fs():
    from gridfs import GridFS
    return GridFS(mongo.db)

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://localhost:27017/infranet"
app.config["SECRET_KEY"] = "bg21PZAji2190OnfnUj291AQmni21PpPSN0"
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    REMEMBER_COOKIE_HTTPONLY=True,
)
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)

mongo.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "auth.login"
login_manager.session_protection = "strong"

@login_manager.user_loader
def load_user(user_id):
    user_data = mongo.db.hr.find_one({"_id": ObjectId(user_id)})
    if user_data:
        return User(user_data)
    return None

@app.before_request
def require_login():
    allowed_routes = ['auth.login', 'auth.register', 'static']
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
        fs = get_fs()
        file_obj = fs.get(ObjectId(file_id))
        return send_file(
            io.BytesIO(file_obj.read()),
            mimetype=file_obj.content_type or "application/octet-stream",
            download_name=file_obj.filename or "download",
            as_attachment=True
        )
    except Exception:
        return jsonify({"error": "파일을 찾을 수 없습니다."}), 404

app.register_blueprint(write_bp, url_prefix="/write")
app.register_blueprint(task_bp, url_prefix="/task")
app.register_blueprint(hr_bp, url_prefix="/hr")
app.register_blueprint(issue_bp, url_prefix="/issue")
app.register_blueprint(client_bp, url_prefix="/client")
app.register_blueprint(auth_bp, url_prefix="/auth")

if __name__ == '__main__':
    app.run(debug=True)