import os
import io
import uuid
import time
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, flash, session, send_file, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from fpdf import FPDF
from openai import OpenAI
from flask_caching import Cache

# Load environment variables
load_dotenv()

# --- Database & Models ---
db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False) # admin, hr, accounting, employee
    profile = db.relationship('EmployeeProfile', backref='user', uselist=False)

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    employees = db.relationship('EmployeeProfile', backref='dept')

class EmployeeProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    dept_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    job_title = db.Column(db.String(100))
    joining_date = db.Column(db.DateTime, default=datetime.utcnow)
    contact = db.Column(db.String(20))
    address = db.Column(db.Text)
    salary_structure = db.relationship('SalaryStructure', backref='profile', uselist=False)

class SalaryStructure(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('employee_profile.id'), nullable=False)
    base_salary = db.Column(db.Float, default=0.0)
    allowances = db.Column(db.Float, default=0.0)
    deductions = db.Column(db.Float, default=0.0)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)

class LeaveRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='Pending')
    user = db.relationship('User', backref='leave_requests')

class PayrollRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    net_amount = db.Column(db.Float, nullable=False)
    paid_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Paid')
    user = db.relationship('User', backref='payroll_records', lazy=True)

# --- Business Logic: AI Engine ---
def analyze_payroll_data(db_session, user_prompt=None):
    api_key = os.environ.get("AI_API_KEY")
    total_payroll_count = db_session.query(PayrollRecord).count()
    total_users = User.query.count()
    pending_leaves = LeaveRequest.query.filter_by(status='Pending').count()
    context = f"System State: {total_users} employees, {total_payroll_count} payroll records, {pending_leaves} pending leaves."
    if not api_key:
        return f"Offline: Query '{user_prompt}' received. Workforce: {total_users}." if user_prompt else "Analysis: Payroll within normal parameters."
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an AI Payroll Consultant. Provide a single-sentence executive insight."},
                {"role": "user", "content": f"{context}\n\nQuestion/Prompt: {user_prompt or 'General status insight'}"}
            ],
            max_tokens=80
        )
        return response.choices[0].message.content
    except Exception as e: return f"AI Error: {str(e)}"

# --- Business Logic: Payslip Generation ---
class PayslipGenerator(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 20)
        self.set_text_color(99, 102, 241)
        self.cell(0, 10, 'Payroll DBMS', ln=True, align='L')
        self.set_font('helvetica', '', 10)
        self.set_text_color(100)
        self.cell(0, 5, 'Executive Financial Document', ln=True, align='L')
        self.ln(10)
    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(150)
        self.cell(0, 10, f'Page {self.page_no()} | Generated by Payroll System', align='C')

def generate_payslip_pdf(payroll_record):
    pdf = PayslipGenerator()
    pdf.add_page()
    pdf.set_fill_color(248, 250, 252)
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(0, 10, 'Employee Details', ln=True, fill=True)
    pdf.set_font('helvetica', '', 10)
    pdf.cell(95, 7, f'Name: {payroll_record.user.name}', ln=False)
    pdf.cell(95, 7, f'Email: {payroll_record.user.email}', ln=True)
    pdf.cell(95, 7, f'Month/Year: {payroll_record.month}/{payroll_record.year}', ln=False)
    job_title = payroll_record.user.profile.job_title if payroll_record.user.profile else "N/A"
    pdf.cell(95, 7, f'Designation: {job_title}', ln=True)
    pdf.ln(10)
    pdf.set_font('helvetica', 'B', 12); pdf.cell(0, 10, 'Salary Breakdown', ln=True, fill=True)
    pdf.set_font('helvetica', 'B', 10); pdf.cell(100, 10, 'Description', border=1); pdf.cell(90, 10, 'Amount (USD)', border=1, ln=True, align='R')
    pdf.set_font('helvetica', '', 10)
    ss = payroll_record.user.profile.salary_structure if payroll_record.user.profile else None
    base, allowances, deductions = (ss.base_salary, ss.allowances, ss.deductions) if ss else (0, 0, 0)
    pdf.cell(100, 10, 'Base Salary', border=1); pdf.cell(90, 10, f'${base:,.2f}', border=1, ln=True, align='R')
    pdf.cell(100, 10, 'Allowances', border=1); pdf.cell(90, 10, f'${allowances:,.2f}', border=1, ln=True, align='R')
    pdf.set_text_color(244, 63, 94); pdf.cell(100, 10, 'Deductions', border=1); pdf.cell(90, 10, f'-${deductions:,.2f}', border=1, ln=True, align='R')
    pdf.set_text_color(0); pdf.set_font('helvetica', 'B', 12); pdf.cell(100, 12, 'NET PAYABLE', border=1); pdf.cell(90, 12, f'${payroll_record.net_amount:,.2f}', border=1, ln=True, align='R')
    pdf.ln(20); pdf.set_font('helvetica', 'I', 10); pdf.multi_cell(0, 5, 'Computer-generated document. No signature required.')
    return pdf.output()

# --- App Initialization ---
app = Flask(__name__)
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Force the correct driver (psycopg2) and standardize the prefix
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
    
    # Ensure sslmode=require is present in the URL if not already specified
    if "sslmode" not in DATABASE_URL:
        DATABASE_URL += ("&" if "?" in DATABASE_URL else "?") + "sslmode=require"
    
    # Supabase connection pooler fix: keepalives and idle timeout
    DATABASE_URL = DATABASE_URL + "&keepalives=1&keepalives_idle=30"

print("USING DB:", DATABASE_URL)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "fallback_secret")

# Production-grade engine options for connection stability
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_size": 3,
    "max_overflow": 2,
    "pool_timeout": 20,
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

db.init_app(app)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
login_manager = LoginManager(app)
login_manager.login_view = 'login'

with app.app_context():
    try:
        if DATABASE_URL:
            db.session.execute(text("SELECT 1"))
    except Exception as e:
        pass

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, user_id)
    except Exception:
        return None

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                flash("Access Denied", "danger")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Routes ---
@app.errorhandler(404)
def not_found(e):
    return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('dashboard')) if current_user.is_authenticated else redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email, password = request.form.get('email'), request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user(); return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
@cache.cached(timeout=30)
def dashboard():
    now = datetime.now()
    total_employees = User.query.filter_by(role='employee').count()
    current_payroll = db.session.query(db.func.sum(PayrollRecord.net_amount)).filter(PayrollRecord.month == now.month, PayrollRecord.year == now.year).scalar() or 0.0
    pending_leaves = LeaveRequest.query.filter_by(status='Pending').count()
    recent_payroll = PayrollRecord.query.filter(PayrollRecord.paid_date != None).order_by(PayrollRecord.paid_date.desc()).limit(5).all()
    return render_template('dashboard.html', user=current_user, now=now, total_employees=total_employees, total_payroll=current_payroll, pending_leaves=pending_leaves, recent_activities=recent_payroll)

@app.route('/employees', methods=['GET', 'POST'])
@role_required('admin', 'hr')
def view_employees():
    if request.method == 'POST' and current_user.role == 'admin':
        name, email, password, role, dept_id = request.form.get('name'), request.form.get('email'), request.form.get('password'), request.form.get('role'), request.form.get('dept_id')
        try:
            hashed_password = generate_password_hash(password)
            user = User(name=name, email=email, password=hashed_password, role=role)
            db.session.add(user)
            db.session.flush() # To get user.id for profile
            
            profile = EmployeeProfile(user_id=user.id, dept_id=dept_id, job_title=f"{role.capitalize()} Staff")
            db.session.add(profile)
            db.session.flush()
            
            db.session.add(SalaryStructure(profile_id=profile.id, base_salary=50000))
            db.session.commit()
            flash(f"Added {name}", "success")
        except Exception as e: 
            db.session.rollback()
            flash(f"Error adding employee: {str(e)}", "danger")
    return render_template('employees.html', employees=User.query.all(), departments=Department.query.all())

@app.route('/attendance', methods=['GET', 'POST'])
@role_required('hr', 'admin', 'employee')
def view_attendance():
    if request.method == 'POST':
        try:
            if current_user.role == 'employee':
                start, end = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date(), datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
                db.session.add(LeaveRequest(user_id=current_user.id, start_date=start, end_date=end, reason=request.form.get('reason')))
                db.session.commit(); flash("Submitted!", "success")
            elif current_user.role in ['hr', 'admin']:
                leave = LeaveRequest.query.get(request.form.get('leave_id'))
                if leave: leave.status = request.form.get('action'); db.session.commit()
        except Exception: flash("Error processing attendance", "danger")
    pending = LeaveRequest.query.filter_by(status='Pending').all() if current_user.role in ['admin', 'hr'] else []
    return render_template('attendance.html', pending_leaves=pending, my_leaves=LeaveRequest.query.filter_by(user_id=current_user.id).all())

@app.route('/payroll', methods=['GET', 'POST'])
@role_required('accounting', 'admin')
def view_payroll():
    if request.method == 'POST':
        m, y = int(request.form.get('month')), int(request.form.get('year'))
        if not PayrollRecord.query.filter_by(month=m, year=y).first():
            for ep in EmployeeProfile.query.all():
                ss = ep.salary_structure; net = (ss.base_salary + ss.allowances) - ss.deductions
                db.session.add(PayrollRecord(user_id=ep.user_id, month=m, year=y, net_amount=net))
            db.session.commit(); flash("Processed!", "success")
    records = PayrollRecord.query.order_by(PayrollRecord.year.desc(), PayrollRecord.month.desc()).all()
    now = datetime.now()
    payout = db.session.query(db.func.sum(PayrollRecord.net_amount)).filter(PayrollRecord.month == now.month, PayrollRecord.year == now.year).scalar() or 0.0
    return render_template('payroll.html', records=records, total_payout=payout, tax_est=payout*0.15, bonuses_est=payout*0.05)

@app.route('/api/ai/analyze', methods=['GET', 'POST'])
@login_required
def ai_analyze():
    try:
        prompt = request.json.get('prompt') if request.method == 'POST' else None
        return {"insight": analyze_payroll_data(db.session, prompt)}
    except Exception as e: return {"insight": f"Error: {str(e)}"}, 500

@app.route('/payroll/download/<id>')
@login_required
def download_payslip(id):
    rec = PayrollRecord.query.get(id)
    if not rec or (current_user.role == 'employee' and rec.user_id != current_user.id): return redirect(url_for('dashboard'))
    return send_file(io.BytesIO(generate_payslip_pdf(rec)), mimetype='application/pdf', as_attachment=True, download_name=f'Payslip_{rec.month}_{rec.year}.pdf')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
