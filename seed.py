from database import create_app
from models import db, User, Department, EmployeeProfile, SalaryStructure
from werkzeug.security import generate_password_hash
from datetime import datetime

app = create_app()

def seed_db():
    with app.app_context():
        # Check if users already exist
        if User.query.first():
            return

        # Create Departments
        depts = ['IT', 'HR', 'Finance', 'Operations']
        dept_objs = []
        for d in depts:
            dept = Department(name=d)
            db.session.add(dept)
            dept_objs.append(dept)
        
        db.session.commit()

        # Create Users for each role
        roles_data = [
            ('admin', 'Admin User', 'admin@payroll.com', 'admin123', 'admin', 'IT'),
            ('hr_mgr', 'HR Manager', 'hr@payroll.com', 'hr123', 'hr', 'HR'),
            ('acc_mgr', 'Accounts Manager', 'acc@payroll.com', 'acc123', 'accounting', 'Finance'),
            ('emp1', 'John Doe', 'john@payroll.com', 'emp123', 'employee', 'IT'),
            ('emp2', 'Jane Smith', 'jane@payroll.com', 'emp123', 'employee', 'Operations'),
        ]

        for username, name, email, password, role, dept_name in roles_data:
            user = User(
                username=username,
                email=email,
                password=generate_password_hash(password),
                role=role
            )
            db.session.add(user)
            db.session.flush()

            dept = Department.query.filter_by(name=dept_name).first()
            profile = EmployeeProfile(
                user_id=user.id,
                dept_id=dept.id,
                job_title=f"{role.capitalize()} Specialist" if role != 'admin' else 'System Administrator',
                contact='1234567890',
                address='123 Main St'
            )
            db.session.add(profile)
            db.session.flush()

            # Add Salary Structure
            salary = SalaryStructure(
                profile_id=profile.id,
                base_salary=50000.0 if role == 'employee' else 80000.0,
                allowances=5000.0,
                deductions=2000.0
            )
            db.session.add(salary)

        db.session.commit()
        print("Database seeded successfully!")

if __name__ == "__main__":
    seed_db()
