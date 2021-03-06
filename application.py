import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_session import Session
from flask_bcrypt import Bcrypt
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker

# Import api request module
from goodreads_api import retrieve_data

app = Flask(__name__)
bcrypt = Bcrypt(app)

# Load dotenv
load_dotenv('.env')

# Check for database and api key environment variables
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")
elif not os.getenv("API_KEY"):
    raise RuntimeError("API_KEY is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/books/<isbn>")
def books(isbn):
    # Get book info from database
    query = text("SELECT isbn, title, authors.author, year FROM books JOIN \
                 authors ON books.author_id = authors.id WHERE isbn = :isbn")
    book = db.execute(query, {"isbn": isbn}).fetchone()
    title = book[1]
    author = book[2]

    # Get data from Goodreads API
    data = retrieve_data(isbn)

    # Handle status code
    if data is None:
        rating = "Unavailable"
    else:
        rating = data["books"][0]["average_rating"]

    return render_template("books.html", isbn=isbn, title=title, author=author,
                           rating=rating)


@app.route("/search", methods=["POST"])
def search():
    search_keys = {"book": "title", "author": "authors.author", "isbn": "isbn"}
    search_for = f"%{request.form.get('searchfor')}%".lower()
    search_by = request.form.get("searchby").lower()
    try:
        search_by = search_keys[search_by]
    except KeyError:
        return "An error has occurred"
    query = text(f"SELECT isbn, title, authors.author, year FROM books JOIN \
                 authors ON books.author_id = authors.id WHERE LOWER \
                 ({search_by}) LIKE :search_for")
    books = db.execute(query, {"search_for": search_for}).fetchall()
    if books:
        return render_template("search.html", books=books)
    else:
        term = search_for.lstrip("%").rstrip("%")
        return render_template("search.html", term=term)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if db.execute("SELECT * FROM users WHERE LOWER (username) = :username",
                      {"username": username.lower()}).rowcount == 0:
            pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
            query = text("INSERT INTO users (username, password)\
                     VALUES (:username, :password)")
            db.execute(query, {"username": username, "password": pw_hash})
            db.commit()
            return render_template("index.html")
        else:
            return render_template("register.html", feedback=True,
                                   username=username)
    else:
        return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        candidate = request.form.get("password")
        if db.execute("SELECT * FROM users WHERE LOWER (username) = :username",
                      {"username": username.lower()}).rowcount == 0:
            return render_template("login.html", user_error=True,
                                   username=username)
        else:
            pw_hash = db.execute("SELECT password FROM users WHERE username = \
                                 :username", {"username": username}).fetchone()
            pw_hash = pw_hash[0]
            if bcrypt.check_password_hash(pw_hash, candidate):
                return render_template("index.html")
            else:
                return render_template("login.html", password_error=True,
                                       username=username)
    else:
        return render_template("login.html")


@app.route("/api/<isbn>", methods=["GET"])
def api(isbn):
    query = text("SELECT title, authors.author, year, isbn FROM books JOIN \
                 authors ON books.author_id = authors.id WHERE isbn = :isbn")
    book = db.execute(query, {"isbn": isbn}).fetchone()
    if book is None:
        return "ERROR (404): ISBN not found\n"
    else:
        data = jsonify(title=book[0], author=book[1],
                       year=book[2], isbn=book[3])
        return data
