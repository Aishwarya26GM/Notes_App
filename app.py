import datetime

import jwt
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///notes.db"

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


with app.app_context():
    db.create_all()


def create_token(user):
    payload = {
        "user_id": user.id,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def get_current_user():
    token = request.cookies.get("token")
    if not token:
        return None
    try:
        data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
    return db.session.get(User, data["user_id"])


@app.context_processor
def add_user_to_templates():
    return {"current_user": get_current_user()}


@app.route("/")
def home():
    if get_current_user():
        return redirect(url_for("notes"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or len(password) < 4:
            flash("Enter a username and a password of at least 4 characters.")
        elif User.query.filter_by(username=username).first():
            flash("Username already taken.")
        else:
            user = User(username=username, password=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            flash("Account created. Please log in.")
            return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            response = redirect(url_for("notes"))
            response.set_cookie("token", create_token(user), httponly=True, max_age=24 * 60 * 60)
            return response
        flash("Wrong username or password.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    response = redirect(url_for("login"))
    response.delete_cookie("token")
    return response


@app.route("/notes", methods=["GET", "POST"])
def notes():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["title"].strip()
        content = request.form["content"].strip()
        if title and content:
            db.session.add(Note(title=title, content=content, user_id=user.id))
            db.session.commit()
        else:
            flash("Title and content are required.")
        return redirect(url_for("notes"))

    my_notes = Note.query.filter_by(user_id=user.id).order_by(Note.id.desc()).all()
    return render_template("notes.html", notes=my_notes)


@app.route("/notes/<int:note_id>/edit", methods=["GET", "POST"])
def edit_note(note_id):
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    note = Note.query.filter_by(id=note_id, user_id=user.id).first_or_404()

    if request.method == "POST":
        title = request.form["title"].strip()
        content = request.form["content"].strip()
        if title and content:
            note.title = title
            note.content = content
            db.session.commit()
            return redirect(url_for("notes"))
        flash("Title and content are required.")

    return render_template("edit.html", note=note)


@app.route("/notes/<int:note_id>/delete", methods=["POST"])
def delete_note(note_id):
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    note = Note.query.filter_by(id=note_id, user_id=user.id).first_or_404()
    db.session.delete(note)
    db.session.commit()
    return redirect(url_for("notes"))


if __name__ == "__main__":
    app.run(debug=True)
