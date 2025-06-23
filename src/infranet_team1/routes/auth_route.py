from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
import bcrypt
from db import mongo_db
from models.user import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/register", methods=["GET"])
def register_form():
    if not current_user.role in ["admin", "system"]:
        return redirect(url_for("home"))
    return render_template("auth/register.html")


@auth_bp.route("/register", methods=["POST"])
def register_post():
    if not current_user.role in ["admin", "system"]:
        return redirect(url_for("home"))

    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    password_confirm = request.form.get("password_confirm")
    position = request.form.get("position")
    department = request.form.get("department")
    phone = request.form.get("phone")

    if password != password_confirm:
        flash("비밀번호가 일치하지 않습니다.", "danger")
        return redirect(url_for("auth.register_form"))

    existing_user = mongo_db.hr.find_one({"email": email})
    if existing_user:
        flash("이미 존재하는 이메일입니다.", "warning")
        return redirect(url_for("auth.register_form"))
    
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    new_user = {
        "name": name,
        "email": email,
        "password": hashed_password,
        "position": position,
        "department": department,
        "phone": phone,
        "hire_date": datetime.now(timezone.utc),
        "status": "재직중",
        "role": "user",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    mongo_db.hr.insert_one(new_user)

    flash("계정이 성공적으로 등록되었습니다.", "success")
    return redirect(url_for("auth.register_form"))


@auth_bp.route("/login", methods=["GET"])
def login_get():
    return render_template("auth/login.html")


@auth_bp.route("/login", methods=["POST"])
def login_post():
    email = request.form.get("email")
    password = request.form.get("password").encode("utf-8")

    user = mongo_db.hr.find_one({"email": email})
    if user and bcrypt.checkpw(password, user["password"]):
        user_obj = User(user)
        login_user(user_obj)
        flash("로그인 성공!", "success")
        return redirect(url_for("home"))
    else:
        flash("이메일 또는 비밀번호가 올바르지 않습니다.", "danger")
        return redirect(url_for("auth.login_get"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flash("로그아웃 되었습니다.", "info")
    return redirect(url_for("auth.login_get"))

