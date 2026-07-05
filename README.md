# Corepulse-HR

Corepulse-HR is a Flask-based human resources portal for managing employee attendance, leave requests, profile details, payroll-facing HR fields, and public employee queries.

## Features

- Employee and HR/admin authentication
- Auto-generated employee IDs
- Employee attendance check-in and check-out
- Attendance status tracking for Present, Absent, Half-day, and Leave
- Leave request submission, approval, and rejection
- Employee profile updates
- Admin profile and payroll field management
- Public query submission and admin resolution
- SQLite database stored locally in `database_store/`
- IST-based date and time handling

## Tech Stack

- Python
- Flask
- Flask-SQLAlchemy
- Flask-Login
- SQLite
- Tailwind CSS CDN
- Font Awesome CDN

## Project Structure

```text
Corepulse-HR/
+-- app.py
+-- models.py
+-- requirements.txt
+-- static/
|   +-- styles.css
+-- templates/
|   +-- admin_dashboard.html
|   +-- base.html
|   +-- emp_dashboard.html
|   +-- index.html
|   +-- login.html
+-- database_store/
    +-- alignhr.sqlite3
```

## Setup

1. Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the application:

```bash
python app.py
```

4. Open the app in your browser:

```text
http://127.0.0.1:5000
```

## Default Admin Login

When the app starts, it creates the SQLite database and seeds a default admin account if no admin or HR user exists.

```text
Email: admin@alignhr.com
Password: admin123
```

Change these credentials before using the app outside local development.

## Notes

- The database is created automatically at `database_store/alignhr.sqlite3`.
- `database_store/` is ignored by Git so local database files are not committed.
- The app uses the `Asia/Kolkata` timezone for attendance and date-sensitive workflows.
