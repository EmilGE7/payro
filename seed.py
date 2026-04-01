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

        # 2. Create Test Users for all Roles
        users_to_create = [
            {'email': 'admin@payroll.com', 'name': 'System Admin', 'role': 'admin', 'password': 'admin123', 'dept': 'Executive', 'title': 'Chief Administrator', 'salary': 120000},
            {'email': 'hr@payroll.com', 'name': 'HR Manager', 'role': 'hr', 'password': 'hr123', 'dept': 'HR', 'title': 'HR Director', 'salary': 85000},
            {'email': 'accounting@payroll.com', 'name': 'Chief Accountant', 'role': 'accounting', 'password': 'finance123', 'dept': 'Finance', 'title': 'Head of Finance', 'salary': 90000},
            {'email': 'employee@payroll.com', 'name': 'John Doe', 'role': 'employee', 'password': 'user123', 'dept': 'IT', 'title': 'Software Engineer', 'salary': 75000}
        ]

        print("\nCreating accounts...")
        for user_data in users_to_create:
            user = User.query.filter_by(email=user_data['email']).first()
            if not user:
                user = User(
                    name=user_data['name'],
                    email=user_data['email'],
                    password=generate_password_hash(user_data['password']),
                    role=user_data['role']
                )
                db.session.add(user)
                db.session.flush()
                
                profile = EmployeeProfile(
                    user_id=user.id,
                    dept_id=dept_objects[user_data['dept']].id,
                    job_title=user_data['title']
                )
                db.session.add(profile)
                db.session.flush()

                db.session.add(SalaryStructure(profile_id=profile.id, base_salary=user_data['salary']))
                print(f"Added {user_data['role'].upper()}: {user_data['email']}")

        db.session.commit()
        print("\n✅ Database Seeded Successfully!")
        print(f"\n🚀 TEST LOGIN CREDENTIALS:")
        for user_data in users_to_create:
            print(f"- {user_data['role'].upper()}: {user_data['email']} | Pass: {user_data['password']}")


if __name__ == "__main__":
    seed_db()
