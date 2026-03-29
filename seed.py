from app import app, db, User, Department, EmployeeProfile, SalaryStructure
from werkzeug.security import generate_password_hash
import os

def seed_db():
    print("Seeding Initial Data...")
    with app.app_context():
        # 1. Create Departments
        depts = ['IT', 'HR', 'Finance', 'Operations', 'Executive']
        dept_objects = {}
        for name in depts:
            dept = Department.query.filter_by(name=name).first()
            if not dept:
                dept = Department(name=name)
                db.session.add(dept)
                print(f"Added Department: {name}")
            dept_objects[name] = dept
        db.session.commit()

        # 2. Create Admin User
        admin_email = 'admin@payroll.com'
        admin = User.query.filter_by(email=admin_email).first()
        if not admin:
            admin = User(
                name='System Admin',
                email=admin_email,
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print(f"Added Admin User: {admin_email}")

            # Create profile for admin
            profile = EmployeeProfile(
                user_id=admin.id,
                dept_id=dept_objects['Executive'].id,
                job_title='Chief Administrator'
            )
            db.session.add(profile)
            db.session.commit()
            
            db.session.add(SalaryStructure(profile_id=profile.id, base_salary=100000))
            db.session.commit()

        print("\n✅ Database Seeded Successfully!")
        print(f"\n🚀 LOGIN CREDENTIALS:")
        print(f"Email: {admin_email}")
        print(f"Password: admin123")

if __name__ == "__main__":
    seed_db()
