from flask import render_template, redirect, url_for, request, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from database import create_app
from database import create_app
from models import db, User, EmployeeProfile, Department, SalaryStructure, Attendance, LeaveRequest, PayrollRecord
from ai_engine import analyze_payroll_data
from payslip_gen import generate_payslip_pdf
from flask import send_file, Response
import io
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
    try:
        # user_id is passed as a string (UUID)
        return User.query.get(user_id)
    except Exception:
        return None

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
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            # Authenticate with Supabase
            auth_response = app.supabase.auth.sign_in_with_password({"email": email, "password": password})
            
            if auth_response.user:
                # Get the user from our local DB (synced via trigger)
                user = User.query.filter_by(email=email).first()
                if user:
                    login_user(user)
                    return redirect(url_for('dashboard'))
                else:
                    flash('User record not found in database.', 'warning')
        except Exception as e:
            flash(f'Login failed: {str(e)}', 'danger')
            
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
    now = datetime.now()
    
    # 📊 Fetch Real Statistics
    total_employees = User.query.filter_by(role='employee').count()
    
    # Calculate this month's payroll total
    current_month_payroll = db.session.query(db.func.sum(PayrollRecord.net_amount)).filter(
        PayrollRecord.month == now.month,
        PayrollRecord.year == now.year
    ).scalar() or 0.0
    
    pending_leaves = LeaveRequest.query.filter_by(status='Pending').count()
    
    # Recent Activities (Last 5 records across tables)
    # For now, we'll just pull the most recent payroll records as proxy for 'activity'
    recent_payroll = PayrollRecord.query.order_by(PayrollRecord.paid_date.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
                         user=current_user, 
                         now=now,
                         total_employees=total_employees,
                         total_payroll=current_month_payroll,
                         pending_leaves=pending_leaves,
                         recent_activities=recent_payroll)

# --- Admin Routes ---
@app.route('/employees', methods=['GET', 'POST'])
@role_required('admin', 'hr')
def view_employees():
    if request.method == 'POST' and current_user.role == 'admin':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        dept_id = request.form.get('dept_id')
        
        try:
            # Create user in Supabase Auth
            # Note: This uses standard signUp. For admin-only creation without logout, 
            # you usually use service_role, but for now we follow the user's Step 9 pattern.
            auth_res = app.supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {"name": name}
                }
            })
            
            if auth_res.user:
                # The trigger handle_new_user() in Postgres will auto-insert into public.users
                # We just need to find it and update its role (or set role in metadata if trigger supports it)
                # For now, we wait for trigger and then update the role if it's not default.
                import time
                time.sleep(1) # Give trigger a moment
                user = User.query.filter_by(email=email).first()
                if user:
                    user.role = role
                    db.session.commit()

                    profile = EmployeeProfile(user_id=user.id, dept_id=dept_id, job_title=f"{role.capitalize()} Staff")
                    db.session.add(profile)
                    
                    salary = SalaryStructure(profile_id=profile.id, base_salary=50000)
                    db.session.add(salary)
                    db.session.commit()
                    
                    flash(f"Employee {name} added successfully!", "success")
                else:
                    flash("User created in Auth but local record sync failed.", "warning")
            return redirect(url_for('view_employees'))
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")

    employees = User.query.all()
    departments = Department.query.all()
    return render_template('employees.html', employees=employees, departments=departments)

# --- HR Routes ---
@app.route('/attendance', methods=['GET', 'POST'])
@role_required('hr', 'admin', 'employee')
def view_attendance():
    if request.method == 'POST':
        try:
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
        except Exception as e:
            flash(f"Error processing request: {str(e)}", "danger")
        return redirect(url_for('view_attendance'))

    if current_user.role in ['admin', 'hr']:
        pending_leaves = LeaveRequest.query.filter_by(status='Pending').all()
    else:
        pending_leaves = []
        
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
    
    # Calculate Stats for the top cards
    from datetime import datetime
    now = datetime.now()
    total_payout = db.session.query(db.func.sum(PayrollRecord.net_amount)).filter(
        PayrollRecord.month == now.month,
        PayrollRecord.year == now.year
    ).scalar() or 0.0
    
    # Mocking tax/bonus for now as they aren't explicit columns, 
    # but could be derived from SalaryStructure if needed.
    tax_est = total_payout * 0.15 
    bonuses_est = total_payout * 0.05

    return render_template('payroll.html', 
                         records=records, 
                         total_payout=total_payout,
                         tax_est=tax_est,
                         bonuses_est=bonuses_est)

# --- AI API ---
@app.route('/api/ai/analyze', methods=['GET', 'POST'])
@login_required
def ai_analyze():
    try:
        user_prompt = None
        if request.method == 'POST':
            user_prompt = request.json.get('prompt')
            
        insight = analyze_payroll_data(db.session, user_prompt)
        return {"insight": insight}
    except Exception as e:
        return {"insight": f"Analysis Error: {str(e)}"}, 500

# --- Payroll Documents ---
@app.route('/payroll/download/<id>')
@login_required
def download_payslip(id):
    record = PayrollRecord.query.get(id)
    if not record:
        flash("Record not found", "danger")
        return redirect(url_for('dashboard'))
    
    # RLS Check: Employees can only download their OWN payslips
    if current_user.role == 'employee' and record.user_id != current_user.id:
        flash("Access Denied", "danger")
        return redirect(url_for('dashboard'))

    pdf_bytes = generate_payslip_pdf(record)
    
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'Payslip_{record.month}_{record.year}.pdf'
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
