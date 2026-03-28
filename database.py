from flask import Flask
from models import db
from sqlalchemy import text
import os

def create_app():
    app = Flask(__name__)

    DATABASE_URL = os.environ.get("DATABASE_URL")

    if not DATABASE_URL:
        raise ValueError("DATABASE_URL missing")

    # Debug logs for Vercel Runtime Logs
    print("Initializing Database Connection...")
    # print("DATABASE_URL:", DATABASE_URL) # Be careful with logging credentials in real production

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

    # ✅ STEP 3: Force DB Test (Connection Health Check)
    with app.app_context():
        try:
            db.session.execute(text("SELECT 1"))
            print("DB CONNECTED ✅")
        except Exception as e:
            print("DB ERROR ❌", e)
            # We don't raise here to allow the app to start, 
            # but it will be visible in the logs.

    return app
