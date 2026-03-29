from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import UUID
import uuid

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
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
    status = db.Column(db.String(20), nullable=False) # Present, Absent, Leave

class LeaveRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='Pending') # Pending, Approved, Rejected

class PayrollRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    net_amount = db.Column(db.Float, nullable=False)
    paid_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Paid')
