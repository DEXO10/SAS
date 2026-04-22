from flask import Flask, render_template, request, redirect, url_for, session, Response, flash
import sqlite3
from datetime import datetime
import csv
import io
import hashlib
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')

from flask_babel import Babel, gettext as _, lazy_gettext as _l

def get_locale():
    return session.get('lang', 'en')

babel = Babel(app, locale_selector=get_locale)

@app.route('/setlang/<lang>')
def setlang(lang):
    if lang in ['en', 'ar']:
        session['lang'] = lang
    return redirect(request.referrer or url_for('dashboard'))

@app.context_processor
def inject_lang():
    return dict(lang=session.get('lang', 'en'))

ROLES = {
    'admin': {'label': _l('Admin'), 'level': 3},
    'department_head': {'label': _l('Department Head'), 'level': 2},
    'teacher': {'label': _l('Teacher'), 'level': 1}
}


def get_db_connection():
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def _table_columns(conn, table_name):
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {r['name'] for r in rows}


def hash_password(password):
    salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + pwd_hash.hex()

def verify_password(password, stored_hash):
    salt = bytes.fromhex(stored_hash[:32])
    stored_pwd_hash = stored_hash[32:]
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return pwd_hash.hex() == stored_pwd_hash

def log_audit(conn, user_id, action, target_type, target_id=None, details=None):
    try:
        conn.execute(
            'INSERT INTO audit_logs (user_id, action, target_type, target_id, details) VALUES (?, ?, ?, ?, ?)',
            (user_id, action, target_type, target_id, details)
        )
    except Exception:
        pass

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Departments Table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            head_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (head_id) REFERENCES users (id)
        )
        """
    )

    # 2. Stages Table (belongs to a department)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS stages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments (id),
            UNIQUE(name, department_id)
        )
        """
    )

    # 3. Semesters Table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS semesters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL, -- e.g. "2025-2026 First Semester"
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # 4. Stage-Semester Activation Table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS stage_semesters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stage_id INTEGER NOT NULL,
            semester_id INTEGER NOT NULL,
            is_active BOOLEAN DEFAULT 0,
            FOREIGN KEY (stage_id) REFERENCES stages (id),
            FOREIGN KEY (semester_id) REFERENCES semesters (id),
            UNIQUE(stage_id, semester_id)
        )
        """
    )

    # 5. Users Table (now linked to department)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'department_head', 'teacher')),
            department_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments (id)
        )
        """
    )

    # 6. Courses Table (linked to stage, semester, and teacher)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name TEXT NOT NULL,
            teacher_id INTEGER,
            stage_id INTEGER NOT NULL,
            semester_id INTEGER NOT NULL,
            FOREIGN KEY (teacher_id) REFERENCES users (id),
            FOREIGN KEY (stage_id) REFERENCES stages (id),
            FOREIGN KEY (semester_id) REFERENCES semesters (id)
        )
        """
    )

    # 7. Students Table (linked to stage)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            stage_id INTEGER NOT NULL,
            student_uid TEXT UNIQUE,
            email TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (stage_id) REFERENCES stages (id)
        )
        """
    )

    # 8. Sessions Table (multiple per day allowed)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            session_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses (id)
        )
        """
    )

    # 9. Attendance Table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Present', 'Absent', 'Late')),
            UNIQUE(session_id, student_id),
            FOREIGN KEY (session_id) REFERENCES sessions (id),
            FOREIGN KEY (student_id) REFERENCES students (id)
        )
        """
    )

    # 10. Enrollments Table (linking students to courses)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            UNIQUE(student_id, course_id),
            FOREIGN KEY (student_id) REFERENCES students (id),
            FOREIGN KEY (course_id) REFERENCES courses (id)
        )
        """
    )

    # Migration: Add department_id to users if not exists
    cols = _table_columns(conn, 'users')
    if 'department_id' not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN department_id INTEGER")
    
    # Audit Logs
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id INTEGER,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )

    # Initial Mock Data if DB is empty
    users_count = cursor.execute("SELECT COUNT(*) as count FROM users").fetchone()['count']
    if users_count == 0:
        # Create Departments
        cursor.execute("INSERT INTO departments (name) VALUES ('Computer Science')")
        cursor.execute("INSERT INTO departments (name) VALUES ('Software Engineering')")
        cs_dept_id = 1
        se_dept_id = 2

        # Create Semesters
        cursor.execute("INSERT INTO semesters (name) VALUES ('2025-2026 First Semester')")
        cursor.execute("INSERT INTO semesters (name) VALUES ('2025-2026 Second Semester')")
        sem1_id = 1

        # Create Stages
        cursor.execute("INSERT INTO stages (name, department_id) VALUES ('Stage 1', ?)", (cs_dept_id,))
        cursor.execute("INSERT INTO stages (name, department_id) VALUES ('Stage 2', ?)", (cs_dept_id,))
        stage1_cs_id = 1

        # Activate Semester for Stage 1 CS
        cursor.execute("INSERT INTO stage_semesters (stage_id, semester_id, is_active) VALUES (?, ?, 1)", (stage1_cs_id, sem1_id))

        # Create Admin
        admin_hash = hash_password('admin123')
        cursor.execute(
            "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
            ('admin', admin_hash, 'Dr. Sarah Admin', 'admin')
        )

        # Create Department Head
        dept_head_hash = hash_password('head123')
        cursor.execute(
            "INSERT INTO users (username, password_hash, full_name, role, department_id) VALUES (?, ?, ?, ?, ?)",
            ('dept_head', dept_head_hash, 'Prof. John Head', 'department_head', cs_dept_id)
        )
        cursor.execute("UPDATE departments SET head_id = (SELECT id FROM users WHERE username='dept_head') WHERE id=?", (cs_dept_id,))

        # Create Lecturers
        teacher_hash = hash_password('teacher123')
        cursor.execute(
            "INSERT INTO users (username, password_hash, full_name, role, department_id) VALUES (?, ?, ?, ?, ?)",
            ('teacher1', teacher_hash, 'Dr. Alice Smith', 'teacher', cs_dept_id)
        )
        teacher1_id = cursor.lastrowid

        # Create Courses
        cursor.execute(
            "INSERT INTO courses (course_name, teacher_id, stage_id, semester_id) VALUES (?, ?, ?, ?)",
            ('CS101: Intro to Programming', teacher1_id, stage1_cs_id, sem1_id)
        )
        cs101_id = cursor.lastrowid

        # Create Students for Stage 1 CS
        cursor.execute(
            "INSERT INTO students (name, stage_id, student_uid, email) VALUES (?, ?, ?, ?)",
            ('Ahmed Hassan', stage1_cs_id, 'STU001', 'ahmed@university.edu')
        )
        cursor.execute(
            "INSERT INTO students (name, stage_id, student_uid, email) VALUES (?, ?, ?, ?)",
            ('Fatima Ali', stage1_cs_id, 'STU002', 'fatima@university.edu')
        )
        
        # Enroll students in the course
        cursor.execute("INSERT INTO enrollments (student_id, course_id) VALUES (1, ?)", (cs101_id,))
        cursor.execute("INSERT INTO enrollments (student_id, course_id) VALUES (2, ?)", (cs101_id,))

    conn.commit()
    conn.close()



def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date().isoformat()
    except Exception:
        return None


def _enrolled_students(conn, course_id):
    return conn.execute(
        """
        SELECT st.id, st.name, st.student_uid, st.email
        FROM students st
        JOIN enrollments e ON e.student_id = st.id
        WHERE e.course_id = ?
        ORDER BY st.name
        """,
        (course_id,),
    ).fetchall()


def _status_totals(conn, course_id, from_date, to_date, status):
    params = [course_id]
    where = ["s.course_id = ?"]
    if from_date:
        where.append("s.session_date >= ?")
        params.append(from_date)
    if to_date:
        where.append("s.session_date <= ?")
        params.append(to_date)
    if status:
        where.append("a.status = ?")
        params.append(status)

    rows = conn.execute(
        f"""
        SELECT a.status, COUNT(*) AS count
        FROM attendance a
        JOIN sessions s ON s.id = a.session_id
        WHERE {' AND '.join(where)}
        GROUP BY a.status
        """,
        params,
    ).fetchall()
    out = {'Present': 0, 'Absent': 0, 'Late': 0}
    for r in rows:
        out[r['status']] = r['count']
    return out


def _trend_points(conn, course_id, from_date, to_date):
    params = [course_id]
    where = ["s.course_id = ?"]
    if from_date:
        where.append("s.session_date >= ?")
        params.append(from_date)
    if to_date:
        where.append("s.session_date <= ?")
        params.append(to_date)

    rows = conn.execute(
        f"""
        SELECT s.session_date AS d,
               SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count
        FROM sessions s
        LEFT JOIN attendance a ON a.session_id = s.id
        WHERE {' AND '.join(where)}
        GROUP BY s.id
        ORDER BY s.session_date
        """,
        params,
    ).fetchall()
    return [(r['d'], int(r['present_count'] or 0)) for r in rows]


def _svg_bar(title, data):
    items = [('Present', data.get('Present', 0), '#16A34A'), ('Absent', data.get('Absent', 0), '#DC2626'), ('Late', data.get('Late', 0), '#F59E0B')]
    max_v = max([v for _, v, _ in items] + [1])
    w, h = 520, 260
    pad_l, pad_r, pad_t, pad_b = 48, 16, 70, 34
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b
    bar_w = int(chart_w / 5)
    gap = int((chart_w - bar_w * 3) / 2)
    parts = [f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="{title}">']
    parts.append(f'<text x="{pad_l}" y="24" class="chart-title">{title}</text>')
    parts.append(f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{w - pad_r}" y2="{pad_t + chart_h}" class="chart-axis" />')
    x = pad_l
    for label, value, color in items:
        bh = int((value / max_v) * chart_h)
        y = pad_t + chart_h - bh
        parts.append(f'<g class="bar" tabindex="0" aria-label="{label} {value}">')
        parts.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" rx="8" fill="{color}"><title>{label}: {value}</title></rect>')
        parts.append(f'<text x="{x + bar_w/2}" y="{pad_t + chart_h + 22}" text-anchor="middle" class="chart-label">{label}</text>')
        parts.append(f'<text x="{x + bar_w/2}" y="{y - 10}" text-anchor="middle" class="chart-value">{value}</text>')
        parts.append('</g>')
        x += bar_w + gap
    parts.append('</svg>')
    return ''.join(parts)


def _svg_line(title, points):
    w, h = 520, 180
    pad_l, pad_r, pad_t, pad_b = 48, 16, 24, 34
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b
    if not points:
        return f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="{title}"><text x="{pad_l}" y="18" class="chart-title">{title}</text><text x="{pad_l}" y="{pad_t + 40}" class="chart-muted">No data</text></svg>'
    max_v = max([v for _, v in points] + [1])
    step = chart_w / max(len(points) - 1, 1)
    coords = []
    for i, (_, v) in enumerate(points):
        x = pad_l + step * i
        y = pad_t + chart_h - (v / max_v) * chart_h
        coords.append((x, y, v))
    poly = ' '.join([f'{x:.1f},{y:.1f}' for x, y, _ in coords])
    parts = [f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="{title}">']
    parts.append(f'<text x="{pad_l}" y="18" class="chart-title">{title}</text>')
    parts.append(f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{w - pad_r}" y2="{pad_t + chart_h}" class="chart-axis" />')
    parts.append(f'<polyline fill="none" stroke="#2563EB" stroke-width="3" points="{poly}" />')
    for x, y, v in coords:
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#2563EB"><title>{v}</title></circle>')
    parts.append('</svg>')
    return ''.join(parts)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and verify_password(password, user['password_hash']):
            session['logged_in'] = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session['department_id'] = user['department_id']
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error=_('Invalid credentials'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(min_role):
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session:
                return redirect(url_for('login'))
            user_role = session.get('role', '')
            if ROLES.get(user_role, {}).get('level', 0) < ROLES.get(min_role, {}).get('level', 0):
                flash(_('You do not have permission to access this page.'), 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
@login_required
def dashboard():
    conn = get_db_connection()
    user_role = session.get('role', 'teacher')
    user_id = session.get('user_id')
    user_dept_id = session.get('department_id')
    stage_filter = request.args.get('stage_id')
    
    # 1. Base query parts
    params = []
    where_clauses = []
    
    if user_role == 'teacher':
        query = """
            SELECT c.*, s.name as stage_name, sem.name as semester_name,
                   (SELECT COUNT(*) FROM enrollments e WHERE e.course_id = c.id) as student_count,
                   (SELECT COUNT(*) FROM sessions sess WHERE sess.course_id = c.id) as session_count
            FROM courses c
            JOIN stages s ON c.stage_id = s.id
            JOIN semesters sem ON c.semester_id = sem.id
            JOIN stage_semesters ss ON (ss.stage_id = c.stage_id AND ss.semester_id = c.semester_id)
            WHERE c.teacher_id = ? AND ss.is_active = 1 AND s.department_id = ?
        """
        params.extend([user_id, user_dept_id])
        if stage_filter:
            query += " AND c.stage_id = ?"
            params.append(stage_filter)
        query += " ORDER BY c.course_name"
        courses_raw = conn.execute(query, params).fetchall()
        
        # Calculate attendance metrics for each course
        courses = []
        for c in courses_raw:
            course_dict = dict(c)
            # Attendance metrics
            att_stats = conn.execute("""
                SELECT status, COUNT(*) as count 
                FROM attendance a
                JOIN sessions s ON a.session_id = s.id
                WHERE s.course_id = ?
                GROUP BY status
            """, (c['id'],)).fetchall()
            
            stats = {row['status']: row['count'] for row in att_stats}
            total = sum(stats.values()) or 1
            course_dict['presence_rate'] = round((stats.get('Present', 0) / total) * 100, 1)
            course_dict['absence_rate'] = round((stats.get('Absent', 0) / total) * 100, 1)
            courses.append(course_dict)

    elif user_role == 'department_head':
        # Detailed metrics for Dept Head
        dept_stats = {
            'total_stages': conn.execute("SELECT COUNT(*) FROM stages WHERE department_id = ?", (user_dept_id,)).fetchone()[0],
            'total_teachers': conn.execute("SELECT COUNT(*) FROM users WHERE role = 'teacher' AND department_id = ?", (user_dept_id,)).fetchone()[0],
            'total_courses': conn.execute("SELECT COUNT(*) FROM courses c JOIN stages s ON c.stage_id = s.id WHERE s.department_id = ?", (user_dept_id,)).fetchone()[0],
            'active_semester': conn.execute("""
                SELECT sem.name 
                FROM stage_semesters ss 
                JOIN semesters sem ON ss.semester_id = sem.id 
                JOIN stages s ON ss.stage_id = s.id
                WHERE s.department_id = ? AND ss.is_active = 1 
                LIMIT 1
            """, (user_dept_id,)).fetchone()
        }
        
        query = """
            SELECT c.*, s.name as stage_name, sem.name as semester_name, u.full_name as teacher_name
            FROM courses c
            JOIN stages s ON c.stage_id = s.id
            JOIN semesters sem ON c.semester_id = sem.id
            LEFT JOIN users u ON c.teacher_id = u.id
            WHERE s.department_id = ?
        """
        params.append(user_dept_id)
        if stage_filter:
            query += " AND c.stage_id = ?"
            params.append(stage_filter)
        query += " ORDER BY c.course_name"
        courses = conn.execute(query, params).fetchall()
        
    else: # Admin
        query = """
            SELECT c.*, s.name as stage_name, sem.name as semester_name, u.full_name as teacher_name, d.name as dept_name
            FROM courses c
            JOIN stages s ON c.stage_id = s.id
            JOIN semesters sem ON c.semester_id = sem.id
            JOIN departments d ON s.department_id = d.id
            LEFT JOIN users u ON c.teacher_id = u.id
        """
        if stage_filter:
            query += " WHERE c.stage_id = ?"
            params.append(stage_filter)
        query += " ORDER BY c.course_name"
        courses = conn.execute(query, params).fetchall()
    
    # Get all stages for filtering (Scoped by department for Dept Head/Teacher)
    if user_role == 'admin':
        all_stages = conn.execute('SELECT s.*, d.name as dept_name FROM stages s JOIN departments d ON s.department_id = d.id ORDER BY s.name').fetchall()
    else:
        all_stages = conn.execute('SELECT * FROM stages WHERE department_id = ? ORDER BY name', (user_dept_id,)).fetchall()
        
    semesters = conn.execute('SELECT * FROM semesters ORDER BY name').fetchall()
    teachers = []
    if user_role == 'admin':
        teachers = conn.execute("SELECT id, full_name FROM users WHERE role='teacher' ORDER BY full_name").fetchall()
    elif user_role == 'department_head':
        teachers = conn.execute("SELECT id, full_name FROM users WHERE role='teacher' AND department_id=? ORDER BY full_name", (user_dept_id,)).fetchall()

    conn.close()
    
    template = 'dashboard_teacher.html' if user_role == 'teacher' else \
               'dashboard_dept_head.html' if user_role == 'department_head' else \
               'dashboard.html'
               
    return render_template(template, 
                         courses=courses, 
                         stages=all_stages, 
                         semesters=semesters, 
                         teachers=teachers,
                         current_stage=stage_filter,
                         dept_stats=dept_stats if user_role == 'department_head' else None)


@app.route('/courses')
@login_required
def courses_list():
    conn = get_db_connection()
    user_role = session.get('role', 'teacher')
    user_id = session.get('user_id')
    user_dept_id = session.get('department_id')
    stage_filter = request.args.get('stage_id')
    
    params = []
    if user_role == 'teacher':
        query = """
            SELECT c.*, s.name as stage_name, sem.name as semester_name
            FROM courses c
            JOIN stages s ON c.stage_id = s.id
            JOIN semesters sem ON c.semester_id = sem.id
            JOIN stage_semesters ss ON (ss.stage_id = c.stage_id AND ss.semester_id = c.semester_id)
            WHERE c.teacher_id = ? AND ss.is_active = 1 AND s.department_id = ?
        """
        params.extend([user_id, user_dept_id])
        if stage_filter:
            query += " AND c.stage_id = ?"
            params.append(stage_filter)
        query += " ORDER BY c.course_name"
    elif user_role == 'department_head':
        query = """
            SELECT c.*, s.name as stage_name, sem.name as semester_name, u.full_name as teacher_name
            FROM courses c
            JOIN stages s ON c.stage_id = s.id
            JOIN semesters sem ON c.semester_id = sem.id
            LEFT JOIN users u ON c.teacher_id = u.id
            WHERE s.department_id = ?
        """
        params.append(user_dept_id)
        if stage_filter:
            query += " AND c.stage_id = ?"
            params.append(stage_filter)
        query += " ORDER BY c.course_name"
    else: # Admin
        query = """
            SELECT c.*, s.name as stage_name, sem.name as semester_name, u.full_name as teacher_name, d.name as dept_name
            FROM courses c
            JOIN stages s ON c.stage_id = s.id
            JOIN semesters sem ON c.semester_id = sem.id
            JOIN departments d ON s.department_id = d.id
            LEFT JOIN users u ON c.teacher_id = u.id
        """
        if stage_filter:
            query += " WHERE c.stage_id = ?"
            params.append(stage_filter)
        query += " ORDER BY c.course_name"
        
    courses = conn.execute(query, params).fetchall()
    
    # Get all stages for filtering
    if user_role == 'admin':
        all_stages = conn.execute('SELECT s.*, d.name as dept_name FROM stages s JOIN departments d ON s.department_id = d.id ORDER BY s.name').fetchall()
    else:
        all_stages = conn.execute('SELECT * FROM stages WHERE department_id = ? ORDER BY name', (user_dept_id,)).fetchall()
        
    semesters = conn.execute('SELECT * FROM semesters ORDER BY name').fetchall()
    teachers = []
    if user_role == 'admin':
        teachers = conn.execute("SELECT id, full_name FROM users WHERE role='teacher' ORDER BY full_name").fetchall()
    elif user_role == 'department_head':
        teachers = conn.execute("SELECT id, full_name FROM users WHERE role='teacher' AND department_id=? ORDER BY full_name", (user_dept_id,)).fetchall()

    conn.close()
    return render_template('courses.html', 
                         courses=courses, 
                         stages=all_stages, 
                         semesters=semesters, 
                         teachers=teachers,
                         current_stage=stage_filter)


@app.route('/reports')
@login_required
def reports_home():
    conn = get_db_connection()
    user_role = session.get('role', 'teacher')
    user_id = session.get('user_id')
    user_dept_id = session.get('department_id')
    
    if user_role == 'teacher':
        courses = conn.execute(
            """
            SELECT c.* 
            FROM courses c
            JOIN stages s ON c.stage_id = s.id
            JOIN stage_semesters ss ON (ss.stage_id = c.stage_id AND ss.semester_id = c.semester_id)
            WHERE c.teacher_id = ? AND ss.is_active = 1 AND s.department_id = ?
            ORDER BY c.course_name
            """, 
            (user_id, user_dept_id)
        ).fetchall()
    elif user_role == 'department_head':
        courses = conn.execute(
            """
            SELECT c.* 
            FROM courses c
            JOIN stages s ON c.stage_id = s.id
            WHERE s.department_id = ?
            ORDER BY c.course_name
            """,
            (user_dept_id,)
        ).fetchall()
    else:
        courses = conn.execute('SELECT * FROM courses ORDER BY course_name').fetchall()
    
    conn.close()
    return render_template('reports_home.html', courses=courses)
@app.route('/settings', methods=['GET', 'POST'])
@role_required('department_head')
def settings():
    conn = get_db_connection()
    user_role = session.get('role')
    user_dept_id = session.get('department_id')
    
    # Admin sees all, Dept Head sees their department's users
    if user_role == 'admin':
        users = conn.execute('SELECT u.*, d.name as dept_name FROM users u LEFT JOIN departments d ON u.department_id = d.id ORDER BY u.username').fetchall()
        depts = conn.execute('SELECT * FROM departments ORDER BY name').fetchall()
        stages = conn.execute('SELECT s.*, d.name as dept_name FROM stages s JOIN departments d ON s.department_id = d.id ORDER BY s.name').fetchall()
        semesters = conn.execute('SELECT * FROM semesters ORDER BY name').fetchall()
        active_sems = conn.execute(
            """
            SELECT ss.*, s.name as stage_name, sem.name as semester_name, d.name as dept_name
            FROM stage_semesters ss
            JOIN stages s ON ss.stage_id = s.id
            JOIN semesters sem ON ss.semester_id = sem.id
            JOIN departments d ON s.department_id = d.id
            """
        ).fetchall()
    else:
        users = conn.execute('SELECT u.*, d.name as dept_name FROM users u LEFT JOIN departments d ON u.department_id = d.id WHERE u.department_id = ? ORDER BY u.username', (user_dept_id,)).fetchall()
        depts = conn.execute('SELECT * FROM departments WHERE id = ?', (user_dept_id,)).fetchall()
        stages = conn.execute('SELECT s.*, d.name as dept_name FROM stages s JOIN departments d ON s.department_id = d.id WHERE s.department_id = ? ORDER BY s.name', (user_dept_id,)).fetchall()
        semesters = conn.execute('SELECT * FROM semesters ORDER BY name').fetchall()
        active_sems = conn.execute(
            """
            SELECT ss.*, s.name as stage_name, sem.name as semester_name, d.name as dept_name
            FROM stage_semesters ss
            JOIN stages s ON ss.stage_id = s.id
            JOIN semesters sem ON ss.semester_id = sem.id
            JOIN departments d ON s.department_id = d.id
            WHERE s.department_id = ?
            """,
            (user_dept_id,)
        ).fetchall()
    
    if request.method == 'POST':
        action = request.form.get('action')
        user_id = session.get('user_id')
        
        if action == 'create_user':
            if user_role != 'admin':
                flash(_('Only admins can manage users.'), 'error')
            else:
                username = (request.form.get('username') or '').strip()
                password = (request.form.get('password') or '').strip()
                full_name = (request.form.get('full_name') or '').strip()
                role = (request.form.get('role') or '').strip()
                dept_id = request.form.get('department_id')
                
                errors = []
                if not username:
                    errors.append(_('Username is required.'))
                if not password or len(password) < 6:
                    errors.append(_('Password must be at least 6 characters.'))
                if not full_name:
                    errors.append(_('Full name is required.'))
                if role not in ROLES:
                    errors.append(_('Invalid role selected.'))
                
                if errors:
                    for error in errors:
                        flash(error, 'error')
                else:
                    password_hash = hash_password(password)
                    try:
                        cursor = conn.cursor()
                        cursor.execute(
                            'INSERT INTO users (username, password_hash, full_name, role, department_id) VALUES (?, ?, ?, ?, ?)',
                            (username, password_hash, full_name, role, dept_id)
                        )
                        new_user_id = cursor.lastrowid
                        log_audit(conn, session.get('user_id'), 'create', 'user', new_user_id, f'Created user: {username} ({role})')
                        conn.commit()
                        flash(_('User "{username}" created successfully!').format(username=username), 'success')
                    except sqlite3.IntegrityError:
                        conn.rollback()
                        flash(_('Username already exists.'), 'error')
                    except Exception:
                        conn.rollback()
                        flash(_('An error occurred while creating the user.'), 'error')
        
        elif action == 'create_department':
            if user_role != 'admin':
                flash(_('Only admins can manage departments.'), 'error')
            else:
                name = (request.form.get('name') or '').strip()
                if name:
                    try:
                        conn.execute('INSERT INTO departments (name) VALUES (?)', (name,))
                        conn.commit()
                        flash(_('Department created successfully!'), 'success')
                    except Exception:
                        flash(_('Error creating department.'), 'error')

        elif action == 'edit_department':
            if user_role != 'admin':
                flash(_('Only admins can manage departments.'), 'error')
            else:
                dept_id = request.form.get('department_id')
                new_name = (request.form.get('name') or '').strip()
                new_head_id = request.form.get('head_id')
                if not new_name:
                    flash(_('Department name is required.'), 'error')
                else:
                    try:
                        # If head_id is empty string, set to NULL
                        if not new_head_id:
                            new_head_id = None
                        conn.execute('UPDATE departments SET name = ?, head_id = ? WHERE id = ?', (new_name, new_head_id, dept_id))
                        # Also update the user's role to department_head if they were assigned as head
                        if new_head_id:
                            conn.execute('UPDATE users SET role = "department_head", department_id = ? WHERE id = ?', (dept_id, new_head_id))
                        conn.commit()
                        flash(_('Department updated successfully!'), 'success')
                    except Exception:
                        conn.rollback()
                        flash(_('Error updating department.'), 'error')

        elif action == 'delete_department':
            if user_role != 'admin':
                flash(_('Only admins can manage departments.'), 'error')
            else:
                dept_id = request.form.get('department_id')
                try:
                    # Check if department has stages
                    has_stages = conn.execute('SELECT id FROM stages WHERE department_id = ?', (dept_id,)).fetchone()
                    if has_stages:
                        flash(_('Cannot delete department with active stages. Delete the stages first.'), 'error')
                    else:
                        # 1. Unset department head and users from this department
                        conn.execute('UPDATE departments SET head_id = NULL WHERE id = ?', (dept_id,))
                        conn.execute('UPDATE users SET department_id = NULL WHERE department_id = ?', (dept_id,))
                        
                        # 2. Finally delete the department
                        conn.execute('DELETE FROM departments WHERE id = ?', (dept_id,))
                        conn.commit()
                        flash(_('Department deleted successfully!'), 'success')
                except Exception:
                    conn.rollback()
                    flash(_('Error deleting department. Ensure it has no dependent records.'), 'error')

        elif action == 'create_stage':
            name = (request.form.get('name') or '').strip()
            dept_id = request.form.get('department_id')
            if user_role == 'department_head':
                dept_id = user_dept_id
            
            if name and dept_id:
                try:
                    conn.execute('INSERT INTO stages (name, department_id) VALUES (?, ?)', (name, dept_id))
                    conn.commit()
                    flash(_('Stage created successfully!'), 'success')
                except Exception:
                    flash(_('Error creating stage.'), 'error')

        elif action == 'edit_stage':
            stage_id = request.form.get('stage_id')
            name = (request.form.get('name') or '').strip()

            if not stage_id or not name:
                flash(_('Stage name is required.'), 'error')
            else:
                try:
                    stage_id = int(stage_id)
                    stage = conn.execute('SELECT id, name, department_id FROM stages WHERE id = ?', (stage_id,)).fetchone()
                    if not stage:
                        flash(_('Stage not found.'), 'error')
                    elif user_role == 'department_head' and stage['department_id'] != user_dept_id:
                        flash(_('Unauthorized.'), 'error')
                    else:
                        conn.execute('UPDATE stages SET name = ? WHERE id = ?', (name, stage_id))
                        log_audit(conn, session.get('user_id'), 'update', 'stage', stage_id, f'Updated stage: "{stage["name"]}" -> "{name}"')
                        conn.commit()
                        flash(_('Stage updated successfully!'), 'success')
                except (ValueError, TypeError):
                    flash(_('Invalid stage ID.'), 'error')
                except Exception:
                    conn.rollback()
                    flash(_('Error updating stage.'), 'error')

        elif action == 'delete_stage':
            stage_id = request.form.get('stage_id')

            if not stage_id:
                flash(_('Invalid stage ID.'), 'error')
            else:
                try:
                    stage_id = int(stage_id)
                    stage = conn.execute('SELECT id, name, department_id FROM stages WHERE id = ?', (stage_id,)).fetchone()
                    if not stage:
                        flash(_('Stage not found.'), 'error')
                    elif user_role == 'department_head' and stage['department_id'] != user_dept_id:
                        flash(_('Unauthorized.'), 'error')
                    else:
                        # Remove activation mappings first; related courses/students will still protect integrity.
                        conn.execute('DELETE FROM stage_semesters WHERE stage_id = ?', (stage_id,))
                        conn.execute('DELETE FROM stages WHERE id = ?', (stage_id,))
                        log_audit(conn, session.get('user_id'), 'delete', 'stage', stage_id, f'Deleted stage: {stage["name"]}')
                        conn.commit()
                        flash(_('Stage "{name}" deleted successfully.').format(name=stage['name']), 'success')
                except sqlite3.IntegrityError:
                    conn.rollback()
                    flash(_('Cannot delete this stage because it is linked to courses or students.'), 'error')
                except (ValueError, TypeError):
                    flash(_('Invalid stage ID.'), 'error')
                except Exception:
                    conn.rollback()
                    flash(_('Error deleting stage.'), 'error')

        elif action == 'create_semester':
            if user_role != 'admin':
                flash(_('Only admins can create semesters.'), 'error')
            else:
                name = (request.form.get('name') or '').strip()
                if name:
                    try:
                        conn.execute('INSERT INTO semesters (name) VALUES (?)', (name,))
                        conn.commit()
                        flash(_('Semester created successfully!'), 'success')
                    except Exception:
                        flash(_('Error creating semester.'), 'error')

        elif action == 'activate_semester':
            stage_id = request.form.get('stage_id')
            sem_id = request.form.get('semester_id')
            
            # Security check for Dept Head
            if user_role == 'department_head':
                stage = conn.execute('SELECT department_id FROM stages WHERE id = ?', (stage_id,)).fetchone()
                if not stage or stage['department_id'] != user_dept_id:
                    flash(_('Unauthorized.'), 'error')
                    return redirect(url_for('settings'))

            try:
                # Deactivate others for this stage
                conn.execute('UPDATE stage_semesters SET is_active = 0 WHERE stage_id = ?', (stage_id,))
                # Upsert active one
                existing = conn.execute('SELECT id FROM stage_semesters WHERE stage_id = ? AND semester_id = ?', (stage_id, sem_id)).fetchone()
                if existing:
                    conn.execute('UPDATE stage_semesters SET is_active = 1 WHERE id = ?', (existing['id'],))
                else:
                    conn.execute('INSERT INTO stage_semesters (stage_id, semester_id, is_active) VALUES (?, ?, 1)', (stage_id, sem_id))
                conn.commit()
                flash(_('Semester activated for stage.'), 'success')
            except Exception:
                flash(_('Error activating semester.'), 'error')

        
        elif action == 'delete_user':
            if user_role != 'admin':
                flash(_('Only admins can manage users.'), 'error')
            else:
                target_user_id = request.form.get('user_id')
                try:
                    target_user_id = int(target_user_id)
                    current_user_id = session.get('user_id')
                    if target_user_id == current_user_id:
                        flash(_('You cannot delete your own account.'), 'error')
                    else:
                        target_user = conn.execute('SELECT username, role FROM users WHERE id = ?', (target_user_id,)).fetchone()
                        if target_user:
                            # 1. Unset department head references
                            conn.execute('UPDATE departments SET head_id = NULL WHERE head_id = ?', (target_user_id,))
                            # 2. Unset course teacher references
                            conn.execute('UPDATE courses SET teacher_id = NULL WHERE teacher_id = ?', (target_user_id,))
                            # 3. Finally delete the user
                            conn.execute('DELETE FROM users WHERE id = ?', (target_user_id,))
                            log_audit(conn, session.get('user_id'), 'delete', 'user', target_user_id, f'Deleted user: {target_user["username"]} ({target_user["role"]})')
                            conn.commit()
                            flash(_('User "{username}" deleted successfully!').format(username=target_user["username"]), 'success')
                        else:
                            flash(_('User not found.'), 'error')
                except (ValueError, TypeError):
                    flash(_('Invalid user ID.'), 'error')
                except Exception:
                    conn.rollback()
                    flash(_('An error occurred while deleting the user.'), 'error')
        
        elif action == 'edit_user':
            if user_role != 'admin':
                flash(_('Only admins can manage users.'), 'error')
            else:
                target_user_id = request.form.get('user_id')
                new_full_name = (request.form.get('full_name') or '').strip()
                new_role = (request.form.get('role') or '').strip()
                
                if not new_full_name:
                    flash(_('Full name is required.'), 'error')
                elif new_role not in ROLES:
                    flash(_('Invalid role selected.'), 'error')
                else:
                    try:
                        target_user_id = int(target_user_id)
                        old_user = conn.execute('SELECT username, full_name, role FROM users WHERE id = ?', (target_user_id,)).fetchone()
                        if old_user:
                            conn.execute(
                                'UPDATE users SET full_name = ?, role = ? WHERE id = ?',
                                (new_full_name, new_role, target_user_id)
                            )
                            log_audit(conn, session.get('user_id'), 'update', 'user', target_user_id, 
                                     f'Updated user: {old_user["username"]} - name: "{old_user["full_name"]}" -> "{new_full_name}", role: "{old_user["role"]}" -> "{new_role}"')
                            conn.commit()
                            flash(_('User "{username}" updated successfully!').format(username=old_user["username"]), 'success')
                        else:
                            flash(_('User not found.'), 'error')
                    except (ValueError, TypeError):
                        flash(_('Invalid user ID.'), 'error')
                    except Exception:
                        conn.rollback()
                        flash(_('An error occurred while updating the user.'), 'error')
        
        elif action == 'change_password':
            if user_role != 'admin':
                flash(_('Only admins can manage users.'), 'error')
            else:
                target_user_id = request.form.get('user_id')
                new_password = (request.form.get('new_password') or '').strip()
                
                if not new_password or len(new_password) < 6:
                    flash(_('Password must be at least 6 characters.'), 'error')
                else:
                    try:
                        target_user_id = int(target_user_id)
                        target_user = conn.execute('SELECT username FROM users WHERE id = ?', (target_user_id,)).fetchone()
                        if target_user:
                            password_hash = hash_password(new_password)
                            conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, target_user_id))
                            log_audit(conn, session.get('user_id'), 'update', 'user_password', target_user_id, f'Changed password for user: {target_user["username"]}')
                            conn.commit()
                            flash(_('Password for "{username}" changed successfully!').format(username=target_user["username"]), 'success')
                        else:
                            flash(_('User not found.'), 'error')
                    except (ValueError, TypeError):
                        flash(_('Invalid user ID.'), 'error')
                    except Exception:
                        conn.rollback()
                        flash(_('An error occurred while changing the password.'), 'error')
        
        conn.close()
        return redirect(url_for('settings'))
    
    conn.close()
    return render_template(
        'settings.html', 
        users=users, 
        depts=depts, 
        stages=stages, 
        semesters=semesters, 
        active_sems=active_sems, 
        roles=ROLES
    )

@app.route('/course/<int:course_id>')
@login_required
def course_detail(course_id):
    conn = get_db_connection()
    course = conn.execute(
        """
        SELECT c.*, s.name as stage_name, sem.name as semester_name, d.name as dept_name
        FROM courses c
        JOIN stages s ON c.stage_id = s.id
        JOIN semesters sem ON c.semester_id = sem.id
        JOIN departments d ON s.department_id = d.id
        WHERE c.id = ?
        """, 
        (course_id,)
    ).fetchone()
    
    if not course:
        conn.close()
        return redirect(url_for('dashboard'))
    
    # Permission check for Lecturers
    user_role = session.get('role')
    user_id = session.get('user_id')
    user_dept_id = session.get('department_id')
    if user_role == 'teacher' and course['teacher_id'] != user_id:
        conn.close()
        flash(_('Unauthorized.'), 'error')
        return redirect(url_for('dashboard'))
    
    students = _enrolled_students(conn, course_id)
    # Get students from the same stage who are not yet enrolled
    all_students = conn.execute(
        'SELECT id, name, student_uid, email FROM students WHERE stage_id = ? ORDER BY name', 
        (course['stage_id'],)
    ).fetchall()
    
    # Get all teachers for assignment (Admin/Dept Head only)
    teachers = []
    stages = []
    if user_role in ['admin', 'department_head']:
        if user_role == 'admin':
            teachers = conn.execute("SELECT id, full_name FROM users WHERE role='teacher'").fetchall()
            stages = conn.execute(
                """
                SELECT s.id, s.name, d.name as dept_name
                FROM stages s
                JOIN departments d ON s.department_id = d.id
                ORDER BY d.name, s.name
                """
            ).fetchall()
        else:
            teachers = conn.execute("SELECT id, full_name FROM users WHERE role='teacher' AND department_id=?", (user_dept_id,)).fetchall()
            stages = conn.execute(
                """
                SELECT s.id, s.name, d.name as dept_name
                FROM stages s
                JOIN departments d ON s.department_id = d.id
                WHERE s.department_id = ?
                ORDER BY s.name
                """,
                (user_dept_id,)
            ).fetchall()

    conn.close()
    return render_template('course_detail.html', course=course, students=students, all_students=all_students, teachers=teachers, stages=stages)

@app.route('/add_course', methods=['POST'])
@role_required('department_head')
def add_course():
    course_name = (request.form.get('course_name') or '').strip()
    teacher_id = request.form.get('teacher_id')
    stage_id = request.form.get('stage_id')
    semester_id = request.form.get('semester_id')
    
    if course_name and stage_id and semester_id:
        conn = get_db_connection()
        user_role = session.get('role')
        user_dept_id = session.get('department_id')
        
        # Security check for Dept Head
        if user_role == 'department_head':
            stage = conn.execute('SELECT department_id FROM stages WHERE id = ?', (stage_id,)).fetchone()
            if not stage or stage['department_id'] != user_dept_id:
                conn.close()
                flash(_('Unauthorized.'), 'error')
                return redirect(url_for('dashboard'))

        try:
            conn.execute(
                'INSERT INTO courses (course_name, teacher_id, stage_id, semester_id) VALUES (?, ?, ?, ?)',
                (course_name, teacher_id, stage_id, semester_id)
            )
            log_audit(conn, session.get('user_id'), 'create', 'course', None, f'Created course: {course_name}')
            conn.commit()
            flash(_('Course created successfully.'), 'success')
        except Exception:
            flash(_('Error creating course.'), 'error')
        conn.close()
    return redirect(url_for('dashboard'))

@app.route('/rename_course/<int:course_id>', methods=['POST'])
@role_required('department_head')
def rename_course(course_id):
    new_name = (request.form.get('course_name') or '').strip()
    teacher_id = request.form.get('teacher_id')
    stage_id = request.form.get('stage_id')
    
    if not new_name:
        flash(_('Course name cannot be empty.'), 'error')
        return redirect(url_for('course_detail', course_id=course_id))

    if not stage_id:
        flash(_('Stage is required.'), 'error')
        return redirect(url_for('course_detail', course_id=course_id))
    
    conn = get_db_connection()
    course = conn.execute(
        """
        SELECT c.*, s.department_id 
        FROM courses c 
        JOIN stages s ON c.stage_id = s.id 
        WHERE c.id = ?
        """, (course_id,)).fetchone()
    
    if course:
        # Security check for Dept Head
        user_role = session.get('role')
        user_dept_id = session.get('department_id')
        if user_role == 'department_head' and course['department_id'] != user_dept_id:
            conn.close()
            flash(_('Unauthorized.'), 'error')
            return redirect(url_for('dashboard'))

        stage = conn.execute('SELECT id, department_id, name FROM stages WHERE id = ?', (stage_id,)).fetchone()
        if not stage:
            conn.close()
            flash(_('Invalid stage selected.'), 'error')
            return redirect(url_for('course_detail', course_id=course_id))

        if user_role == 'department_head' and stage['department_id'] != user_dept_id:
            conn.close()
            flash(_('Unauthorized.'), 'error')
            return redirect(url_for('dashboard'))

        old_name = course['course_name']
        conn.execute(
            'UPDATE courses SET course_name = ?, teacher_id = ?, stage_id = ? WHERE id = ?',
            (new_name, teacher_id, int(stage_id), course_id)
        )
        log_audit(conn, session.get('user_id'), 'update', 'course', course_id, f'Updated course: "{old_name}" -> "{new_name}"')
        conn.commit()
    conn.close()
    return redirect(url_for('course_detail', course_id=course_id))

@app.route('/delete_course/<int:course_id>', methods=['POST'])
@role_required('department_head')
def delete_course(course_id):
    conn = get_db_connection()
    course = conn.execute(
        """
        SELECT c.*, s.department_id 
        FROM courses c 
        JOIN stages s ON c.stage_id = s.id 
        WHERE c.id = ?
        """, (course_id,)).fetchone()
    
    if course:
        # Security check for Dept Head
        user_role = session.get('role')
        user_dept_id = session.get('department_id')
        if user_role == 'department_head' and course['department_id'] != user_dept_id:
            conn.close()
            flash(_('Unauthorized.'), 'error')
            return redirect(url_for('dashboard'))

        conn.execute('DELETE FROM attendance WHERE session_id IN (SELECT id FROM sessions WHERE course_id = ?)', (course_id,))
        conn.execute('DELETE FROM sessions WHERE course_id = ?', (course_id,))
        conn.execute('DELETE FROM enrollments WHERE course_id = ?', (course_id,))
        conn.execute('DELETE FROM courses WHERE id = ?', (course_id,))
        log_audit(conn, session.get('user_id'), 'delete', 'course', course_id, f'Deleted course: {course["course_name"]}')
        conn.commit()
        flash(_('Course "{name}" deleted successfully.').format(name=course["course_name"]), 'success')
    conn.close()
    return redirect(url_for('courses_list'))

@app.route('/add_student/<int:course_id>', methods=['POST'])
@role_required('department_head')
def add_student(course_id):
    student_ids = request.form.getlist('student_ids')
    conn = get_db_connection()
    if student_ids:
        for sid in student_ids:
            try:
                conn.execute('INSERT OR IGNORE INTO enrollments (student_id, course_id) VALUES (?, ?)', (int(sid), course_id))
            except Exception:
                pass
        conn.commit()
    conn.close()
    return redirect(url_for('course_detail', course_id=course_id))


@app.route('/students')
@app.route('/students')
@role_required('department_head')
def students_registry():
    q = (request.args.get('q') or '').strip()
    stage_filter = request.args.get('stage')
    sort_by = request.args.get('sort', 'name')
    order = request.args.get('order', 'asc')
    selected = request.args.get('selected')
    
    conn = get_db_connection()
    user_role = session.get('role')
    user_dept_id = session.get('department_id')
    
    # Filter stages by department for Dept Head
    if user_role == 'admin':
        stages = conn.execute('SELECT s.*, d.name as dept_name FROM stages s JOIN departments d ON s.department_id = d.id ORDER BY s.name').fetchall()
    else:
        stages = conn.execute('SELECT s.*, d.name as dept_name FROM stages s JOIN departments d ON s.department_id = d.id WHERE s.department_id = ? ORDER BY s.name', (user_dept_id,)).fetchall()

    # Base query
    query = 'SELECT st.*, s.name as stage_name FROM students st JOIN stages s ON st.stage_id = s.id'
    params = []
    conditions = []

    # Role-based restriction
    if user_role != 'admin':
        conditions.append('s.department_id = ?')
        params.append(user_dept_id)

    # Search filter
    if q:
        like = f"%{q}%"
        conditions.append('(st.name LIKE ? OR st.student_uid LIKE ?)')
        params.extend([like, like])

    # Stage filter
    if stage_filter:
        conditions.append('st.stage_id = ?')
        params.append(stage_filter)

    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)

    # Sorting
    allowed_sort = {'name': 'st.name', 'stage': 's.name'}
    sort_col = allowed_sort.get(sort_by, 'st.name')
    sort_order = 'DESC' if order == 'desc' else 'ASC'
    query += f' ORDER BY {sort_col} {sort_order}'

    students = conn.execute(query, params).fetchall()

    selected_student = None
    if selected:
        try:
            sid = int(selected)
            if user_role == 'admin':
                selected_student = conn.execute('SELECT * FROM students WHERE id = ?', (sid,)).fetchone()
            else:
                selected_student = conn.execute(
                    '''
                    SELECT st.*
                    FROM students st
                    JOIN stages s ON st.stage_id = s.id
                    WHERE st.id = ? AND s.department_id = ?
                    ''',
                    (sid, user_dept_id)
                ).fetchone()
        except Exception:
            pass

    conn.close()
    return render_template('students.html', 
                          students=students, 
                          stages=stages, 
                          q=q, 
                          stage_filter=stage_filter,
                          sort_by=sort_by,
                          order=order,
                          selected_student=selected_student)


@app.route('/students/create', methods=['POST'])
@role_required('department_head')
def create_student():
    name = (request.form.get('name') or '').strip()
    email = (request.form.get('email') or '').strip()
    stage_id = request.form.get('stage_id')

    if not name or not stage_id:
        flash(_('Name and Stage are required.'), 'error')
        return redirect(url_for('students_registry'))

    conn = get_db_connection()
    # Security check for Dept Head
    user_role = session.get('role')
    user_dept_id = session.get('department_id')
    if user_role == 'department_head':
        stage = conn.execute('SELECT department_id FROM stages WHERE id = ?', (stage_id,)).fetchone()
        if not stage or stage['department_id'] != user_dept_id:
            conn.close()
            flash(_('Unauthorized.'), 'error')
            return redirect(url_for('students_registry'))

    try:
        # Auto-generate Student ID: YYYY-STAGE-XXXX
        year = datetime.now().year
        stage_name = conn.execute('SELECT name FROM stages WHERE id = ?', (stage_id,)).fetchone()['name']
        # Extract stage number if possible (e.g., "Stage 1" -> "S1")
        stage_code = "".join([c for c in stage_name if c.isalnum()])
        
        prefix = f"{year}-{stage_code}-"
        last_id = conn.execute(
            "SELECT student_uid FROM students WHERE student_uid LIKE ? ORDER BY student_uid DESC LIMIT 1",
            (prefix + '%',)
        ).fetchone()
        
        if last_id:
            last_num = int(last_id['student_uid'].split('-')[-1])
            new_num = str(last_num + 1).zfill(4)
        else:
            new_num = "0001"
            
        student_uid = f"{prefix}{new_num}"

        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO students (name, stage_id, student_uid, email) VALUES (?, ?, ?, ?)',
            (name, stage_id, student_uid, email)
        )
        student_id = cursor.lastrowid
        log_audit(conn, session.get('user_id'), 'create', 'student', student_id, f'Created student: {name} ({student_uid})')
        conn.commit()
        flash(_('Student created successfully! ID: {uid}').format(uid=student_uid), 'success')
    except sqlite3.IntegrityError:
        flash(_('Student ID or Email already exists.'), 'error')
    except Exception as e:
        flash(_('Error creating student: {e}').format(e=str(e)), 'error')
    
    conn.close()
    return redirect(url_for('students_registry'))


@app.route('/students/update/<int:student_id>', methods=['POST'])
@role_required('department_head')
def update_student(student_id):
    name = (request.form.get('name') or '').strip()
    email = (request.form.get('email') or '').strip()
    stage_id = request.form.get('stage_id')

    if not name or not stage_id:
        flash(_('Name and Stage are required.'), 'error')
        return redirect(url_for('students_registry', selected=student_id))

    conn = get_db_connection()
    user_role = session.get('role')
    user_dept_id = session.get('department_id')

    student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
    if not student:
        conn.close()
        flash(_('Student not found.'), 'error')
        return redirect(url_for('students_registry'))

    # Security check for Dept Head: both existing and target stages must belong to the same department.
    if user_role == 'department_head':
        old_stage = conn.execute('SELECT department_id FROM stages WHERE id = ?', (student['stage_id'],)).fetchone()
        new_stage = conn.execute('SELECT department_id FROM stages WHERE id = ?', (stage_id,)).fetchone()
        if not old_stage or not new_stage or old_stage['department_id'] != user_dept_id or new_stage['department_id'] != user_dept_id:
            conn.close()
            flash(_('Unauthorized.'), 'error')
            return redirect(url_for('students_registry'))

    try:
        conn.execute(
            'UPDATE students SET name = ?, email = ?, stage_id = ? WHERE id = ?',
            (name, email, stage_id, student_id)
        )
        log_audit(conn, session.get('user_id'), 'update', 'student', student_id, f'Updated student: {student["name"]} -> {name}')
        conn.commit()
        flash(_('Student updated successfully.'), 'success')
    except sqlite3.IntegrityError:
        conn.rollback()
        flash(_('Student ID or Email already exists.'), 'error')
    except Exception as e:
        conn.rollback()
        flash(_('Error updating student: {e}').format(e=str(e)), 'error')

    conn.close()
    return redirect(url_for('students_registry', selected=student_id))


@app.route('/students/delete/<int:student_id>', methods=['POST'])
@role_required('department_head')
def delete_student(student_id):
    conn = get_db_connection()
    user_role = session.get('role')
    user_dept_id = session.get('department_id')

    student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
    if not student:
        conn.close()
        flash(_('Student not found.'), 'error')
        return redirect(url_for('students_registry'))

    # Security check for Dept Head
    if user_role == 'department_head':
        stage = conn.execute('SELECT department_id FROM stages WHERE id = ?', (student['stage_id'],)).fetchone()
        if not stage or stage['department_id'] != user_dept_id:
            conn.close()
            flash(_('Unauthorized.'), 'error')
            return redirect(url_for('students_registry'))

    try:
        conn.execute('DELETE FROM attendance WHERE student_id = ?', (student_id,))
        conn.execute('DELETE FROM enrollments WHERE student_id = ?', (student_id,))
        conn.execute('DELETE FROM students WHERE id = ?', (student_id,))
        log_audit(conn, session.get('user_id'), 'delete', 'student', student_id, f'Deleted student: {student["name"]}')
        conn.commit()
        flash(_('Student "{name}" deleted successfully.').format(name=student['name']), 'success')
    except Exception as e:
        conn.rollback()
        flash(_('Error deleting student: {e}').format(e=str(e)), 'error')

    conn.close()
    return redirect(url_for('students_registry'))


@app.route('/students/assign', methods=['POST'])
@role_required('department_head')
def assign_student_courses():
    student_id = request.form.get('student_id')
    course_ids = request.form.getlist('course_ids')
    try:
        student_id = int(student_id)
    except Exception:
        flash(_('Invalid student ID.'), 'error')
        return redirect(url_for('students_registry'))

    clean_course_ids = []
    for cid in course_ids:
        try:
            clean_course_ids.append(int(cid))
        except Exception:
            pass

    conn = get_db_connection()
    conn.execute('DELETE FROM enrollments WHERE student_id = ?', (student_id,))
    for cid in clean_course_ids:
        conn.execute('INSERT OR IGNORE INTO enrollments (student_id, course_id) VALUES (?, ?)', (student_id, cid))
    log_audit(conn, session.get('user_id'), 'update', 'student_enrollment', student_id, f'Assigned courses: {clean_course_ids}')
    conn.commit()
    conn.close()
    return redirect(url_for('students_registry', selected=student_id))

@app.route('/start_attendance/<int:course_id>')
@login_required
def start_attendance(course_id):
    # Always create a new session
    today = datetime.now().date().isoformat()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db_connection()
    
    cursor = conn.cursor()
    cursor.execute('INSERT INTO sessions (course_id, session_date, created_at) VALUES (?, ?, ?)', 
                  (course_id, today, now))
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return redirect(url_for('mark_attendance', session_id=session_id))

@app.route('/attendance/<int:session_id>')
@login_required
def mark_attendance(session_id):
    conn = get_db_connection()
    session_row = conn.execute(
        """
        SELECT s.*, c.course_name, c.teacher_id
        FROM sessions s
        JOIN courses c ON s.course_id = c.id
        WHERE s.id = ?
        """,
        (session_id,),
    ).fetchone()
    
    if not session_row:
        conn.close()
        return redirect(url_for('dashboard'))
    
    # Permission check
    if session.get('role') == 'teacher' and session_row['teacher_id'] != session.get('user_id'):
        conn.close()
        flash(_('Unauthorized.'), 'error')
        return redirect(url_for('dashboard'))

    students = conn.execute(
        """
        SELECT st.id, st.name, a.status
        FROM students st
        JOIN enrollments e ON e.student_id = st.id
        LEFT JOIN attendance a ON a.student_id = st.id AND a.session_id = ?
        WHERE e.course_id = ?
        ORDER BY st.name
        """,
        (session_id, session_row['course_id']),
    ).fetchall()
    
    conn.close()
    return render_template('mark_attendance.html', session=session_row, students=students)

@app.route('/save_attendance/<int:session_id>', methods=['POST'])
@login_required
def save_attendance(session_id):
    conn = get_db_connection()
    session_row = conn.execute('SELECT course_id, teacher_id FROM sessions s JOIN courses c ON s.course_id=c.id WHERE s.id = ?', (session_id,)).fetchone()
    
    if not session_row:
        conn.close()
        return redirect(url_for('dashboard'))
    
    # Permission check
    if session.get('role') == 'teacher' and session_row['teacher_id'] != session.get('user_id'):
        conn.close()
        flash(_('Unauthorized.'), 'error')
        return redirect(url_for('dashboard'))

    course_id = session_row['course_id']
    students = _enrolled_students(conn, course_id)

    for student in students:
        student_id = student['id']
        status = request.form.get(f'status_{student_id}', 'Absent')
        conn.execute(
            'INSERT INTO attendance (session_id, student_id, status) VALUES (?, ?, ?) ON CONFLICT(session_id, student_id) DO UPDATE SET status=excluded.status',
            (session_id, student_id, status)
        )

    conn.commit()
    conn.close()
    return redirect(url_for('reports', course_id=course_id))

@app.route('/delete_session/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    conn = get_db_connection()
    session_row = conn.execute(
        'SELECT s.course_id, c.teacher_id FROM sessions s JOIN courses c ON s.course_id = c.id WHERE s.id = ?',
        (session_id,),
    ).fetchone()

    if not session_row:
        conn.close()
        flash(_('Session not found.'), 'error')
        return redirect(url_for('dashboard'))

    if session.get('role') == 'teacher' and session_row['teacher_id'] != session.get('user_id'):
        conn.close()
        flash(_('Unauthorized.'), 'error')
        return redirect(url_for('dashboard'))

    conn.execute('DELETE FROM attendance WHERE session_id = ?', (session_id,))
    conn.execute('DELETE FROM sessions WHERE id = ?', (session_id,))
    conn.commit()
    conn.close()

    flash(_('Session deleted successfully.'), 'success')
    return redirect(url_for('reports', course_id=session_row['course_id']))

@app.route('/reports/<int:course_id>')
@login_required
def reports(course_id):
    from_date = _parse_date(request.args.get('from'))
    to_date = _parse_date(request.args.get('to'))
    status_filter = (request.args.get('status') or '').strip()

    conn = get_db_connection()
    course = conn.execute(
        """
        SELECT c.*, s.name as stage_name, sem.name as semester_name, d.name as dept_name
        FROM courses c
        JOIN stages s ON c.stage_id = s.id
        JOIN semesters sem ON c.semester_id = sem.id
        JOIN departments d ON s.department_id = d.id
        WHERE c.id = ?
        """, 
        (course_id,)
    ).fetchone()
    
    if not course:
        conn.close()
        return redirect(url_for('dashboard'))
    
    # Permission check
    if session.get('role') == 'teacher' and course['teacher_id'] != session.get('user_id'):
        conn.close()
        flash(_('Unauthorized.'), 'error')
        return redirect(url_for('dashboard'))

    # Build session query with filters
    session_params = [course_id]
    session_where = ["course_id = ?"]
    if from_date:
        session_where.append("session_date >= ?")
        session_params.append(from_date)
    if to_date:
        session_where.append("session_date <= ?")
        session_params.append(to_date)
    
    sessions = conn.execute(
        f"SELECT * FROM sessions WHERE {' AND '.join(session_where)} ORDER BY session_date ASC, created_at ASC",
        session_params
    ).fetchall()
    
    session_ids = [s['id'] for s in sessions]
    
    # Get students
    all_enrolled = _enrolled_students(conn, course_id)
    
    # If status filter is applied, we only show students who have that status in the filtered sessions
    if status_filter and session_ids:
        placeholders = ', '.join(['?'] * len(session_ids))
        query = f"""
            SELECT DISTINCT student_id 
            FROM attendance 
            WHERE session_id IN ({placeholders}) AND status = ?
        """
        filtered_student_ids = [r['student_id'] for r in conn.execute(query, session_ids + [status_filter]).fetchall()]
        students = [s for s in all_enrolled if s['id'] in filtered_student_ids]
    else:
        students = all_enrolled
    
    # Build attendance matrix
    matrix = []
    for student in students:
        row = {'id': student['id'], 'name': student['name'], 'statuses': [], 'present_count': 0, 'absent_count': 0, 'late_count': 0}
        for s in sessions:
            att = conn.execute('SELECT status FROM attendance WHERE session_id = ? AND student_id = ?', (s['id'], student['id'])).fetchone()
            status = att['status'] if att else None
            
            if status == 'Present': row['present_count'] += 1
            elif status == 'Absent': row['absent_count'] += 1
            elif status == 'Late': row['late_count'] += 1

            # If status filter is applied, only show the symbol if it matches the filter
            display_status = status
            if status_filter and status != status_filter:
                display_status = None

            # Map status to symbols
            symbol = ''
            if display_status == 'Present': symbol = '✓'
            elif display_status == 'Absent': symbol = '✗'
            elif display_status == 'Late': symbol = '-'
            
            row['statuses'].append({'session_id': s['id'], 'symbol': symbol, 'status': status})
        
        # Calculate percentages
        total_sessions = len(sessions)
        if total_sessions > 0:
            row['presence_rate'] = round(((row['present_count'] + row['late_count']) / total_sessions) * 100, 1)
            row['absence_rate'] = round((row['absent_count'] / total_sessions) * 100, 1)
        else:
            row['presence_rate'] = 0
            row['absence_rate'] = 0
            
        matrix.append(row)

    totals = _status_totals(conn, course_id, from_date, to_date, status_filter)
    status_chart = _svg_bar('Totals by status', totals)

    export_args = []
    if from_date:
        export_args.append(f"from={from_date}")
    if to_date:
        export_args.append(f"to={to_date}")
    if status_filter:
        export_args.append(f"status={status_filter}")
    export_query = ('?' + '&'.join(export_args)) if export_args else ''

    conn.close()
    return render_template(
        'reports.html',
        course=course,
        sessions=sessions,
        matrix=matrix,
        status_chart=status_chart,
        from_date=from_date or '',
        to_date=to_date or '',
        status=status_filter,
        export_query=export_query
    )

@app.route('/edit_attendance', methods=['POST'])
@login_required
def edit_attendance():
    session_id = request.form.get('session_id')
    student_id = request.form.get('student_id')
    new_status = request.form.get('status')
    
    conn = get_db_connection()
    # Permission check: Teacher must own the course
    course = conn.execute('SELECT teacher_id, course_id FROM sessions s JOIN courses c ON s.course_id=c.id WHERE s.id = ?', (session_id,)).fetchone()
    if not course or (session.get('role') == 'teacher' and course['teacher_id'] != session.get('user_id')):
        conn.close()
        return _('Unauthorized'), 403
    
    conn.execute(
        'INSERT INTO attendance (session_id, student_id, status) VALUES (?, ?, ?) ON CONFLICT(session_id, student_id) DO UPDATE SET status=excluded.status',
        (session_id, student_id, new_status)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('reports', course_id=course['course_id']))

@app.route('/course/<int:course_id>/download_students')
@login_required
def download_students(course_id):
    conn = get_db_connection()
    course = conn.execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
    if not course:
        conn.close()
        return redirect(url_for('dashboard'))
    
    # Permission check
    if session.get('role') == 'teacher' and course['teacher_id'] != session.get('user_id'):
        conn.close()
        flash(_('Unauthorized.'), 'error')
        return redirect(url_for('dashboard'))

    students = _enrolled_students(conn, course_id)
    conn.close()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['Student ID', 'Student Name', 'Email'])
    for s in students:
        w.writerow([s['student_uid'] or '', s['name'], s['email'] or ''])

    out = buf.getvalue()
    filename = f"students_{course['course_name'].replace(' ', '_')}.csv"
    return Response(
        out,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )

@app.route('/reports/session/<int:session_id>')
@login_required
def session_report(session_id):
    conn = get_db_connection()
    
    session_row = conn.execute(
        """
        SELECT s.*, c.course_name, c.teacher_id
        FROM sessions s
        JOIN courses c ON s.course_id = c.id
        WHERE s.id = ?
        """,
        (session_id,),
    ).fetchone()
    
    if not session_row:
        conn.close()
        return redirect(url_for('dashboard'))
    
    # Permission check for Teachers
    user_role = session.get('role')
    user_id = session.get('user_id')
    if user_role == 'teacher' and session_row['teacher_id'] != user_id:
        log_audit(conn, user_id, 'unauthorized_access', 'session_report', session_id, 'Teacher tried to access unauthorized session report')
        conn.commit()
        conn.close()
        flash(_('Unauthorized.'), 'error')
        return redirect(url_for('dashboard'))
    
    # Get attendance records with student names
    attendance_records = conn.execute(
        """
        SELECT st.name, st.student_uid, st.email, a.status
        FROM attendance a
        JOIN students st ON a.student_id = st.id
        WHERE a.session_id = ?
        ORDER BY st.name
        """,
        (session_id,),
    ).fetchall()
    
    # Calculate totals
    totals_rows = conn.execute(
        """
        SELECT status, COUNT(*) as count
        FROM attendance
        WHERE session_id = ?
        GROUP BY status
        """,
        (session_id,),
    ).fetchall()

    totals = {'Present': 0, 'Absent': 0, 'Late': 0}
    for r in totals_rows:
        totals[r['status']] = r['count']
    status_chart = _svg_bar('Session totals', totals)
    
    conn.close()

    return render_template(
        'session_report.html',
        session=session_row,
        attendance_records=attendance_records,
        totals=totals,
        status_chart=status_chart,
    )


@app.route('/export/course/<int:course_id>.csv')
@login_required
def export_course_csv(course_id):
    from_date = _parse_date(request.args.get('from'))
    to_date = _parse_date(request.args.get('to'))
    status = (request.args.get('status') or '').strip()
    if status not in ('Present', 'Absent', 'Late'):
        status = ''

    conn = get_db_connection()
    # Permission check for Teachers
    course = conn.execute('SELECT teacher_id FROM courses WHERE id = ?', (course_id,)).fetchone()
    user_role = session.get('role')
    user_id = session.get('user_id')
    if user_role == 'teacher' and course['teacher_id'] != user_id:
        log_audit(conn, user_id, 'unauthorized_access', 'export_course_csv', course_id, 'Teacher tried to export unauthorized course csv')
        conn.commit()
        conn.close()
        flash(_('Unauthorized.'), 'error')
        return redirect(url_for('dashboard'))

    params = [course_id]
    where = ["s.course_id = ?"]
    if from_date:
        where.append("s.session_date >= ?")
        params.append(from_date)
    if to_date:
        where.append("s.session_date <= ?")
        params.append(to_date)
    if status:
        where.append("a.status = ?")
        params.append(status)

    rows = conn.execute(
        f"""
        SELECT s.session_date, st.student_uid, st.name, st.email, a.status
        FROM attendance a
        JOIN sessions s ON s.id = a.session_id
        JOIN students st ON st.id = a.student_id
        WHERE {' AND '.join(where)}
        ORDER BY s.session_date DESC, st.name
        """,
        params,
    ).fetchall()
    conn.close()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['Session Date', 'Student ID', 'Student Name', 'Email', 'Status'])
    for r in rows:
        w.writerow([r['session_date'], r['student_uid'] or '', r['name'], r['email'] or '', r['status']])

    out = buf.getvalue()
    filename = f"course_{course_id}_report.csv"
    return Response(
        out,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


@app.route('/export/session/<int:session_id>.csv')
@login_required
def export_session_csv(session_id):
    conn = get_db_connection()
    session_row = conn.execute(
        """
        SELECT s.session_date, s.course_id, c.course_name, c.teacher_id
        FROM sessions s
        JOIN courses c ON c.id = s.course_id
        WHERE s.id = ?
        """,
        (session_id,),
    ).fetchone()
    if not session_row:
        conn.close()
        return redirect(url_for('dashboard'))

    # Permission check for Teachers
    user_role = session.get('role')
    user_id = session.get('user_id')
    if user_role == 'teacher' and session_row['teacher_id'] != user_id:
        log_audit(conn, user_id, 'unauthorized_access', 'export_session_csv', session_id, 'Teacher tried to export unauthorized session csv')
        conn.commit()
        conn.close()
        flash(_('Unauthorized.'), 'error')
        return redirect(url_for('dashboard'))

    rows = conn.execute(
        """
        SELECT st.student_uid, st.name, st.email, a.status
        FROM attendance a
        JOIN students st ON st.id = a.student_id
        WHERE a.session_id = ?
        ORDER BY st.name
        """,
        (session_id,),
    ).fetchall()
    conn.close()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['Student ID', 'Student Name', 'Email', 'Status'])
    for r in rows:
        w.writerow([r['student_uid'] or '', r['name'], r['email'] or '', r['status']])

    out = buf.getvalue()
    filename = f"session_{session_id}_{session_row['session_date']}.csv"
    return Response(
        out,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
