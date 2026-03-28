from flask import render_template, redirect, url_for, request, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from database import create_app
from models import db, User, EmployeeProfile, Department, SalaryStructure, Attendance, LeaveRequest, PayrollRecord
from werkzeug.security import check_password_hash
from functools import wraps
from datetime import datetime

app = create_app()
# Vercel needs the 'app' object to be accessible at the module level
# For serverless, we handle DB check in app factory
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# RBAC Decorator
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                flash("You do not have permission to access this page.", "danger")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Routes ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    from datetime import datetime
    # Role-specific data would be fetched here
    return render_template('dashboard.html', user=current_user, now=datetime.now())

# --- Admin Routes ---
@app.route('/employees', methods=['GET', 'POST'])
@role_required('admin', 'hr')
def view_employees():
    if request.method == 'POST' and current_user.role == 'admin':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        dept_id = request.form.get('dept_id')
        
        from werkzeug.security import generate_password_hash
        user = User(username=username, email=email, role=role, password=generate_password_hash(password))
        db.session.add(user)
        db.session.flush()
        
        profile = EmployeeProfile(user_id=user.id, dept_id=dept_id, job_title=f"{role.capitalize()} Staff")
        db.session.add(profile)
        
        # Initial salary structure
        salary = SalaryStructure(profile_id=profile.id, base_salary=50000)
        db.session.add(salary)
        
        db.session.commit()
        flash(f"Employee {username} added successfully!", "success")
        return redirect(url_for('view_employees'))

    employees = User.query.all()
    departments = Department.query.all()
    return render_template('employees.html', employees=employees, departments=departments)

# --- HR Routes ---
@app.route('/attendance', methods=['GET', 'POST'])
@role_required('hr', 'admin', 'employee')
def view_attendance():
    if request.method == 'POST':
        if current_user.role == 'employee':
            # Submit leave request
            start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
            reason = request.form.get('reason')
            
            leave = LeaveRequest(user_id=current_user.id, start_date=start_date, end_date=end_date, reason=reason)
            db.session.add(leave)
            db.session.commit()
            flash("Leave request submitted!", "success")
        elif current_user.role in ['hr', 'admin']:
            # Approve/Reject leave
            leave_id = request.form.get('leave_id')
            action = request.form.get('action') # Approved, Rejected
            leave = LeaveRequest.query.get(leave_id)
            if leave:
                leave.status = action
                db.session.commit()
                flash(f"Leave {action.lower()}!", "success")
        return redirect(url_for('view_attendance'))

    pending_leaves = LeaveRequest.query.filter_by(status='Pending').all()
    my_leaves = LeaveRequest.query.filter_by(user_id=current_user.id).all()
    return render_template('attendance.html', pending_leaves=pending_leaves, my_leaves=my_leaves)

# --- Accounting Routes ---
@app.route('/payroll', methods=['GET', 'POST'])
@role_required('accounting', 'admin')
def view_payroll():
    if request.method == 'POST':
        # Process payroll for a specific month/year
        month = int(request.form.get('month'))
        year = int(request.form.get('year'))
        
        # Check if already processed
        exists = PayrollRecord.query.filter_by(month=month, year=year).first()
        if exists:
            flash("Payroll for this period already exists!", "warning")
        else:
            all_employees = EmployeeProfile.query.all()
            for ep in all_employees:
                ss = ep.salary_structure
                net = (ss.base_salary + ss.allowances) - ss.deductions
                record = PayrollRecord(
                    user_id=ep.user_id,
                    month=month,
                    year=year,
                    net_amount=net,
                    status='Paid'
                )
                db.session.add(record)
            db.session.commit()
            flash(f"Payroll for {month}/{year} processed successfully!", "success")
        return redirect(url_for('view_payroll'))

    records = PayrollRecord.query.order_by(PayrollRecord.year.desc(), PayrollRecord.month.desc()).all()
    return render_template('payroll.html', records=records)

if __name__ == '__main__':
    app.run(debug=True, port=5000)

def handler(request, context):
    return app
