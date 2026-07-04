import re
from datetime import datetime

import pytz

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from werkzeug.security import check_password_hash, generate_password_hash


IST_TIMEZONE = pytz.timezone("Asia/Kolkata")
db = SQLAlchemy()


def get_ist_time():
    return datetime.now(IST_TIMEZONE).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(32), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="employee", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: get_ist_time())

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
    user_queries = db.relationship(
        "UserQuery",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(UserQuery.created_at)",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def generate_employee_id(connection=None):
        current_year = get_ist_time().year
        prefix = f"EMP-{current_year}-"
        pattern = re.compile(rf"^{re.escape(prefix)}(\d{{4}})$")

        if connection is not None:
            employee_ids = [
                row[0]
                for row in connection.execute(
                    db.select(User.employee_id)
                    .where(User.employee_id.like(f"{prefix}%"))
                    .order_by(User.employee_id.desc())
                ).fetchall()
            ]
        else:
            employee_ids = [
                employee_id
                for (employee_id,) in db.session.query(User.employee_id)
                .filter(User.employee_id.like(f"{prefix}%"))
                .order_by(User.employee_id.desc())
                .all()
            ]

        latest_sequence = 0
        for employee_id in employee_ids:
            match = pattern.match(employee_id)
            if match:
                latest_sequence = int(match.group(1))
                break

        return f"{prefix}{latest_sequence + 1:04d}"

    @property
    def is_admin(self):
        return self.role in {"admin", "hr"}


@event.listens_for(User, "before_insert")
def assign_employee_id(mapper, connection, target):
    if not target.employee_id:
        target.employee_id = User.generate_employee_id(connection=connection)


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
    date = db.Column(db.Date, nullable=False, default=lambda: get_ist_time().date(), index=True)
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
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: get_ist_time())
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: get_ist_time(),
        onupdate=lambda: get_ist_time(),
    )

    user = db.relationship("User", back_populates="leave_requests")


class UserQuery(db.Model):
    __tablename__ = "user_queries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    contact_number = db.Column(db.String(30), nullable=False)
    query_description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: get_ist_time())
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: get_ist_time(),
        onupdate=lambda: get_ist_time(),
    )

    user = db.relationship("User", back_populates="user_queries")
