# Student Attendance System

A simple web-based attendance tracking system for lecturers. This is a minimal MVP built for a graduation project.

## Features

- **Lecturer Login**: Simple authentication with hardcoded credentials
- **Course Management**: Add and view courses
- **Student Management**: Add students to courses
- **Attendance Tracking**: Mark attendance (Present, Absent, Late)
- **Reports**: View attendance records and summaries

## Technology Stack

- **Backend**: Python + Flask
- **Database**: SQLite
- **Frontend**: Plain HTML + Basic CSS
- **No external frameworks or libraries**

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

3. Open your browser and go to: `http://localhost:5000`

## Default Credentials

- **Username**: admin
- **Password**: password123

## Usage

1. **Login** with the default credentials
2. **Add a Course** using the form on the dashboard
3. **Click on a course** to manage it
4. **Add Students** to the course
5. **Start Attendance** to create a new session
6. **Mark Attendance** for each student
7. **View Reports** to see attendance summaries

## Database Structure

The system uses SQLite with the following tables:

- **courses**: Stores course information
- **students**: Stores student information linked to courses
- **sessions**: Stores attendance session dates
- **attendance**: Stores individual attendance records

## File Structure

```
SAS/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── templates/           # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── course_detail.html
│   ├── mark_attendance.html
│   ├── reports.html
│   └── session_report.html
└── static/
    └── style.css         # Basic CSS styling
```

## Notes

- This is a minimal MVP for educational purposes
- The database is automatically created when you run the app
- All data is stored locally in `attendance.db`
- No mobile support or advanced features included
- Designed to demonstrate basic CRUD operations and simple authentication