from flask import Flask
from models import db
import os

def create_app():
    app = Flask(__name__)

    DATABASE_URL = os.environ.get("DATABASE_URL")

    if not DATABASE_URL:
        # Crucial for Vercel production to fail fast if config is missing
        raise ValueError("DATABASE_URL missing")

    # Debug log for Vercel Functions -> Logs (Only for debugging)
    # print("Connecting to DATABASE_URL:", DATABASE_URL[:20] + "...") 

    # Fix postgres:// issue
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    # Force SSL for Supabase
    if "sslmode" not in DATABASE_URL:
        DATABASE_URL += "?sslmode=require"

    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")

    db.init_app(app)

    # NOTE: db.create_all() removed for production serverless environment.
    # Schema initialization should be done via seed.py locally or migrations.

    return app
