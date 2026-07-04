from calendar import monthrange
from datetime import date, datetime
from pathlib import Path

import pytz
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from sqlalchemy import func

from models import Attendance, LeaveRequest, Profile, User, UserQuery, db, get_ist_time


BASE_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "database_store"
DATABASE_PATH = DATABASE_DIR / "alignhr.sqlite3"


def create_app():
    DATABASE_DIR.mkdir(exist_ok=True)
    ensure_gitignore_entry("database_store/")

    app = Flask(__name__)
    app.config["SECRET_KEY"] = "replace-this-with-a-secure-env-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH.as_posix()}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["APP_TIMEZONE"] = pytz.timezone("Asia/Kolkata").zone

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.login_message_category = "warning"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_now():
        return {"now": get_ist_time()}

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))

        if request.method == "POST":
            action = request.form.get("action", "login")
            if action == "register":
                return register_employee()

            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()
            if not user or not user.check_password(password):
                flash("Invalid email or password.", "danger")
                return redirect(url_for("login"))

            login_user(user)
            flash(f"Welcome back, {user.profile.full_name if user.profile else user.email}.", "success")
            return redirect(url_for("index"))

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been signed out.", "info")
        return redirect(url_for("login"))

    @app.route("/submit-query", methods=["POST"])
    def submit_query():
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        contact_number = request.form.get("contact_number", "").strip()
        query_description = request.form.get("query_description", "").strip()

        if not all([full_name, email, contact_number, query_description]):
            flash("Please complete every query field before sending your message.", "danger")
            return redirect(url_for("index"))

        query = UserQuery(
            user_id=current_user.id if current_user.is_authenticated else None,
            full_name=full_name,
            email=email,
            contact_number=contact_number,
            query_description=query_description,
        )
        db.session.add(query)
        db.session.commit()
        flash("Your query has been captured successfully. Our team will review it shortly.", "success")
        return redirect(url_for("index"))

    @app.route("/employee")
    @login_required
    def employee_dashboard():
        if current_user.is_admin:
            return redirect(url_for("admin_dashboard"))

        today_ist = get_ist_time().date()
        today_record = Attendance.query.filter_by(user_id=current_user.id, date=today_ist).first()
        attendance = Attendance.query.filter_by(user_id=current_user.id).order_by(Attendance.date.desc()).limit(45).all()
        leaves = LeaveRequest.query.filter_by(user_id=current_user.id).order_by(LeaveRequest.created_at.desc()).all()

        status_counts = {
            status: count
            for status, count in db.session.query(Attendance.status, func.count(Attendance.id))
            .filter(Attendance.user_id == current_user.id)
            .group_by(Attendance.status)
            .all()
        }
        leave_counts = {
            status: count
            for status, count in db.session.query(LeaveRequest.status, func.count(LeaveRequest.id))
            .filter(LeaveRequest.user_id == current_user.id)
            .group_by(LeaveRequest.status)
            .all()
        }

        return render_template(
            "emp_dashboard.html",
            today_record=today_record,
            attendance=attendance,
            leaves=leaves,
            status_counts=status_counts,
            leave_counts=leave_counts,
            calendar_days=build_calendar_payload(current_user.id),
        )

    @app.route("/admin")
    @login_required
    @admin_required
    def admin_dashboard():
        users = User.query.order_by(User.created_at.desc()).all()
        today_ist = get_ist_time().date()
        today_logs = (
            Attendance.query.filter_by(date=today_ist)
            .join(User)
            .order_by(Attendance.check_in.desc().nullslast())
            .all()
        )
        pending_leaves = LeaveRequest.query.filter_by(status="Pending").order_by(LeaveRequest.created_at.asc()).all()
        all_leaves = LeaveRequest.query.order_by(LeaveRequest.created_at.desc()).limit(25).all()
        public_queries = UserQuery.query.order_by(UserQuery.created_at.desc()).all()
        metrics = {
            "employees": User.query.filter(User.role == "employee").count(),
            "admins": User.query.filter(User.role.in_(["admin", "hr"])).count(),
            "present_today": Attendance.query.filter_by(date=today_ist, status="Present").count(),
            "pending_leaves": LeaveRequest.query.filter_by(status="Pending").count(),
            "pending_queries": UserQuery.query.filter_by(status="Pending").count(),
        }
        return render_template(
            "admin_dashboard.html",
            users=users,
            today_logs=today_logs,
            pending_leaves=pending_leaves,
            all_leaves=all_leaves,
            public_queries=public_queries,
            metrics=metrics,
        )

    @app.route("/profile/update", methods=["POST"])
    @login_required
    def update_own_profile():
        profile = current_user.profile
        profile.full_name = request.form.get("full_name", profile.full_name).strip() or profile.full_name
        profile.phone = request.form.get("phone", "").strip()
        profile.address = request.form.get("address", "").strip()
        profile.profile_pic = request.form.get("profile_pic", "").strip()
        db.session.commit()
        flash("Profile updated. Administrative payroll fields remain protected.", "success")
        return redirect(url_for("employee_dashboard"))

    @app.route("/admin/profile/<int:user_id>/update", methods=["POST"])
    @login_required
    @admin_required
    def admin_update_profile(user_id):
        user = db.session.get(User, user_id) or abort(404)
        profile = user.profile
        profile.full_name = request.form.get("full_name", profile.full_name).strip() or profile.full_name
        profile.phone = request.form.get("phone", "").strip()
        profile.address = request.form.get("address", "").strip()
        profile.job_title = request.form.get("job_title", "").strip()
        profile.salary_structure = request.form.get("salary_structure", "").strip()
        user.role = request.form.get("role", user.role)
        db.session.commit()
        flash("Employee profile and payroll matrix updated.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/query/<int:query_id>/resolve", methods=["POST"])
    @login_required
    @admin_required
    def resolve_query(query_id):
        query = db.session.get(UserQuery, query_id) or abort(404)
        query.status = "Resolved"
        db.session.commit()
        flash("Query marked as resolved.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/attendance/toggle", methods=["POST"])
    @login_required
    def attendance_toggle():
        if current_user.is_admin:
            abort(403)

        payload = request.get_json(silent=True) or {}
        desired_status = payload.get("status", "Present")
        if desired_status not in {"Present", "Absent", "Half-day", "Leave"}:
            return jsonify({"ok": False, "message": "Invalid attendance status."}), 400

        now_ist = get_ist_time()
        today_ist = now_ist.date()

        approved_leave_today = LeaveRequest.query.filter(
            LeaveRequest.user_id == current_user.id,
            LeaveRequest.status == "Approved",
            LeaveRequest.start_date <= today_ist,
            LeaveRequest.end_date >= today_ist,
        ).first()

        record = Attendance.query.filter_by(user_id=current_user.id, date=today_ist).first()

        if record and record.status == "Absent":
            return jsonify(
                {
                    "ok": False,
                    "disabled": True,
                    "status": "Absent",
                    "message": "Status: Absent (Check-in Disabled)",
                    "check_in": None,
                    "check_out": None,
                }
            ), 403

        if desired_status == "Absent":
            if not record:
                record = Attendance(user_id=current_user.id, date=today_ist)
                db.session.add(record)
            record.check_in = None
            record.check_out = None
            record.status = "Absent"
            db.session.commit()
            return jsonify(
                {
                    "ok": True,
                    "action": "disabled",
                    "disabled": True,
                    "status": record.status,
                    "message": "Status: Absent (Check-in Disabled)",
                    "check_in": None,
                    "check_out": None,
                }
            )

        if not record:
            record = Attendance(
                user_id=current_user.id,
                date=today_ist,
                check_in=now_ist,
                status="Leave" if approved_leave_today or desired_status == "Leave" else "Present",
            )
            db.session.add(record)
            action = "checked_in"
        elif record.check_in and not record.check_out:
            elapsed_hours = (now_ist - record.check_in).total_seconds() / 3600
            if now_ist <= record.check_in:
                return jsonify({"ok": False, "message": "Check-out must be after check-in."}), 400

            if approved_leave_today or desired_status == "Leave" or record.status == "Leave":
                final_status = "Leave"
            elif elapsed_hours < 4:
                return jsonify(
                    {
                        "ok": False,
                        "message": "Minimum 4 hours required before checkout. Please continue working or select Leave/Absent.",
                    }
                ), 400
            elif elapsed_hours < 8:
                final_status = "Half-day"
            else:
                final_status = "Present"

            record.check_out = now_ist
            record.status = final_status
            action = "checked_out"
        else:
            record.check_in = now_ist
            record.check_out = None
            record.status = "Leave" if approved_leave_today or desired_status == "Leave" else "Present"
            action = "checked_in"

        db.session.commit()
        return jsonify(
            {
                "ok": True,
                "action": action,
                "disabled": False,
                "status": record.status,
                "check_in": record.check_in.strftime("%H:%M") if record.check_in else None,
                "check_out": record.check_out.strftime("%H:%M") if record.check_out else None,
            }
        )

    @app.route("/leave/apply", methods=["POST"])
    @login_required
    def leave_apply():
        if current_user.is_admin:
            abort(403)

        leave_type = request.form.get("leave_type", "Casual Leave").strip()
        start_date = parse_date(request.form.get("start_date"))
        end_date = parse_date(request.form.get("end_date"))
        remarks = request.form.get("remarks", "").strip()
        if not start_date or not end_date or end_date < start_date:
            flash("Please select a valid leave date range.", "danger")
            return redirect(url_for("employee_dashboard"))

        leave = LeaveRequest(
            user_id=current_user.id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            remarks=remarks,
            status="Pending",
        )
        db.session.add(leave)
        db.session.commit()
        flash("Leave request submitted for approval.", "success")
        return redirect(url_for("employee_dashboard"))

    @app.route("/leave/approve/<int:leave_id>", methods=["POST"])
    @login_required
    @admin_required
    def leave_approve(leave_id):
        return decide_leave(leave_id, "Approved")

    @app.route("/leave/reject/<int:leave_id>", methods=["POST"])
    @login_required
    @admin_required
    def leave_reject(leave_id):
        return decide_leave(leave_id, "Rejected")

    return app


def admin_required(view):
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    wrapped.__name__ = view.__name__
    return wrapped


def register_employee():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "employee")
    full_name = request.form.get("full_name", "New Employee").strip() or "New Employee"

    if role not in {"employee", "hr"}:
        role = "employee"
    if not email or len(password) < 6:
        flash("Email and a 6+ character password are required.", "danger")
        return redirect(url_for("login"))
    if User.query.filter_by(email=email).first():
        flash("An account already exists for that email.", "danger")
        return redirect(url_for("login"))

    employee_id = User.generate_employee_id()
    user = User(employee_id=employee_id, email=email, role=role)
    user.set_password(password)
    user.profile = Profile(full_name=full_name, job_title="HR Officer" if role == "hr" else "Employee")
    db.session.add(user)
    db.session.commit()
    flash(
        f"Account created successfully! Your Auto-Generated Employee ID is: {user.employee_id}",
        "success",
    )
    return redirect(url_for("login"))


def decide_leave(leave_id, status):
    leave = db.session.get(LeaveRequest, leave_id) or abort(404)
    leave.status = status
    leave.admin_comment = request.form.get("admin_comment", "").strip()
    db.session.commit()
    flash(f"Leave request {status.lower()}.", "success")
    return redirect(url_for("admin_dashboard"))


def build_calendar_payload(user_id):
    today = get_ist_time().date()
    _, days_in_month = monthrange(today.year, today.month)
    attendance_by_day = {
        record.date.day: record.status
        for record in Attendance.query.filter(
            Attendance.user_id == user_id,
            func.strftime("%Y", Attendance.date) == str(today.year),
            func.strftime("%m", Attendance.date) == f"{today.month:02d}",
        ).all()
    }
    approved_leaves = LeaveRequest.query.filter(
        LeaveRequest.user_id == user_id,
        LeaveRequest.status == "Approved",
        LeaveRequest.start_date <= date(today.year, today.month, days_in_month),
        LeaveRequest.end_date >= date(today.year, today.month, 1),
    ).all()

    leave_days = set()
    for leave in approved_leaves:
        start = max(leave.start_date.day, 1) if leave.start_date.month == today.month else 1
        end = min(leave.end_date.day, days_in_month) if leave.end_date.month == today.month else days_in_month
        leave_days.update(range(start, end + 1))

    days = []
    for day in range(1, days_in_month + 1):
        status = "Leave" if day in leave_days else attendance_by_day.get(day, "Absent" if day < today.day else "")
        days.append({"day": day, "status": status})
    return days


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def ensure_gitignore_entry(entry):
    gitignore = BASE_DIR / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if entry not in existing.splitlines():
        with gitignore.open("a", encoding="utf-8") as handle:
            if existing and not existing.endswith("\n"):
                handle.write("\n")
            handle.write(f"{entry}\n")


def seed_default_admin():
    if User.query.filter(User.role.in_(["admin", "hr"])).first():
        return
    admin = User(employee_id=User.generate_employee_id(), email="admin@alignhr.com", role="admin")
    admin.set_password("admin123")
    admin.profile = Profile(
        full_name="AlignHR Administrator",
        job_title="System Administrator",
        salary_structure="Admin confidential matrix",
    )
    db.session.add(admin)
    db.session.commit()


app = create_app()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_default_admin()
    app.run(debug=True)
