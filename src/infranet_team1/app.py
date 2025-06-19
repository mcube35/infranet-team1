from datetime import timedelta
from flask import Flask, render_template
from flask_wtf import CSRFProtect
from flask_login import LoginManager, current_user
from db import mongo

from routes import write_bp, task_bp, issue_bp, hr_bp, client_bp, auth_bp

from bson.objectid import ObjectId
from models.user import User

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

@app.route("/")
def home():
    return render_template("index.html", user=current_user)

app.register_blueprint(write_bp, url_prefix="/write")
app.register_blueprint(task_bp, url_prefix="/task")
app.register_blueprint(hr_bp, url_prefix="/hr")
app.register_blueprint(issue_bp, url_prefix="/issue")
app.register_blueprint(client_bp, url_prefix="/client")
app.register_blueprint(auth_bp, url_prefix="/auth")

if __name__ == '__main__':
    app.run(debug=True)