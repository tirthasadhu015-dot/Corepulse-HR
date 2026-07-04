from datetime import date, datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(32), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="employee", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    profile = db.relationship(
        "Profile",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    attendance_records = db.relationship(
        "Attendance",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(Attendance.date)",
    )
    leave_requests = db.relationship(
        "LeaveRequest",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(LeaveRequest.created_at)",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role in {"admin", "hr"}


class Profile(db.Model):
    __tablename__ = "profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    full_name = db.Column(db.String(120), nullable=False, default="New Employee")
    phone = db.Column(db.String(30), nullable=True)
    address = db.Column(db.Text, nullable=True)
    job_title = db.Column(db.String(120), nullable=True)
    salary_structure = db.Column(db.String(255), nullable=True)
    profile_pic = db.Column(db.String(500), nullable=True)

    user = db.relationship("User", back_populates="profile")


class Attendance(db.Model):
    __tablename__ = "attendance"
    __table_args__ = (
        db.UniqueConstraint("user_id", "date", name="uq_attendance_user_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    check_in = db.Column(db.DateTime, nullable=True)
    check_out = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Absent", index=True)

    user = db.relationship("User", back_populates="attendance_records")


class LeaveRequest(db.Model):
    __tablename__ = "leave_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    leave_type = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    remarks = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    admin_comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = db.relationship("User", back_populates="leave_requests")
