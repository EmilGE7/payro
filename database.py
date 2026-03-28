from flask import Flask
from models import db
import os

def create_app():
    app = Flask(__name__)

    DATABASE_URL = os.environ.get("DATABASE_URL")

    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is missing!")

    # Fix postgres:// issue
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    # Force SSL for Supabase
    if "sslmode" not in DATABASE_URL:
        DATABASE_URL += "?sslmode=require"

    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ✅ FIX SECRET KEY
    app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")

    db.init_app(app)

    with app.app_context():
        db.create_all()

    return app
