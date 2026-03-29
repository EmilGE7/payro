from database import create_app
from models import db, Department
import os

app = create_app()

def seed_db():
    print("Seeding Initial Data...")
    with app.app_context():
        # 1. Create Departments (The core backbone)
        depts = ['IT', 'HR', 'Finance', 'Operations', 'Executive']
        for name in depts:
            exists = Department.query.filter_by(name=name).first()
            if not exists:
                dept = Department(name=name)
                db.session.add(dept)
                print(f"Added Department: {name}")
        
        db.session.commit()
        print("\n✅ Basic Setup Complete!")
        print("\n⚠️  NOTE ON USERS:")
        print("Users are now managed by Supabase Auth.")
        print("To create your first admin:")
        print("1. Go to Supabase Dashboard -> Authentication -> Users")
        print("2. Add User -> 'admin@example.com' with password")
        print("3. Run the SQL Migration script in Supabase to sync the profile.")
        print("4. Manually update the 'role' in 'public.users' to 'admin' using the SQL Editor.")

if __name__ == "__main__":
    seed_db()
