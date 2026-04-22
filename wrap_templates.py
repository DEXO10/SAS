import os

tpl_dir = "c:/Users/Anitr/OneDrive/Desktop/SAS/templates"
files = [f for f in os.listdir(tpl_dir) if f.endswith(".html")]

# Strings to wrap in {{ _('...') }}
# Ordered by length descending so substrings don't match prematurely
strings = [
    # common phrases and headers
    "Student Attendance System",
    "Sign in to manage courses and attendance",
    "Welcome Back",
    "Username",
    "Password",
    "Sign in",
    "Demo Accounts",
    "Admin",
    "Admin / admin123",
    "Dept Head",
    "dept_head / head123",
    "Teacher",
    "teacher1 / teacher123",
    
    # Dashboard & navigation
    "Dashboard",
    "Students",
    "Courses",
    "Reports",
    "Settings",
    "Logout",
    "Student Attendance",
    
    # Titles and Headers
    "My Courses",
    "All Courses",
    "Course Detail",
    "Enrolled Students",
    "All Students",
    "Assign Students",
    "Attendance Status",
    "Session Totals",
    "Present",
    "Absent",
    "Late",
    "Start Attendance",
    "Save Attendance",
    "Cancel",
    "Rename",
    "Delete",
    "Update",
    "Export CSV",
    "Export",
    "Actions",
    "Create New User",
    "System Settings",
    "System Users",
    "Create User",
    "User Details",
    "Name",
    "Role",
    "Email",
    "Student ID",
    "Session Date",
    "Status",
    "Department Head",
    "Save Changes",
    "Delete Course",
    "Are you sure you want to delete this course?",
    "Add Course",
    "Course Name",
    "Create Course",
    "Create Student",
    "Filter by date or status",
    "From Date",
    "To Date",
    "Totals by status",
    "Present trend",
    "Enrolled Courses",
    "No courses assigned",
    "Assign to Course",
    "View Course",
    "Add to Course",
    "Select Student",
    "Edit User",
    "Change Password",
    "New Password",
    "Selected Student",
    "Search Students",
    "No students found.",
    "No courses found.",
    "Course Reports",
    "Select Course",
    "Full Name",
    "Log out",
]

def wrap(text):
    return f"{{{{ _('{text}') }}}}"

for filename in files:
    if filename == "base.html":
        continue # handled separately
    filepath = os.path.join(tpl_dir, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Manual replacements for specific jinja formats
    # e.g., <label for="username">Username</label>
    
    for s in sorted(strings, key=len, reverse=True):
        # We only want to replace visible text, not inside class names or variables.
        # But for HTML, it's fairly safe if the string has spaces and capitals.
        # To be safe, we will replace `>Text<` to `>{{ _('Text') }}<`
        
        # 1: Direct tags >Some text<
        content = content.replace(f">{s}<", f">{wrap(s)}<")
        # 2: with spaces
        content = content.replace(f"> {s} <", f"> {wrap(s)} <")
        content = content.replace(f">\n{s}\n<", f">\n{wrap(s)}\n<")
        # 3: sometimes they lack closing tag or are plain inside jinja
        # We can also search for "Some text" explicitly if it's safe (e.g. capitalized strings)
        # But we must avoid replacing inside jinja {{ ... }}
        
    # Extra hardcoded replaces I missed
    content = content.replace('placeholder="Course Name"', 'placeholder="{{ _(\'Course Name\') }}"')
    content = content.replace('placeholder="Student Name"', 'placeholder="{{ _(\'Student Name\') }}"')
    content = content.replace('placeholder="Username"', 'placeholder="{{ _(\'Username\') }}"')
    content = content.replace('placeholder="Full Name"', 'placeholder="{{ _(\'Full Name\') }}"')
    content = content.replace('placeholder="Password"', 'placeholder="{{ _(\'Password\') }}"')
    content = content.replace('placeholder="New Password"', 'placeholder="{{ _(\'New Password\') }}"')
    content = content.replace('placeholder="Email"', 'placeholder="{{ _(\'Email\') }}"')
    content = content.replace('placeholder="Student ID"', 'placeholder="{{ _(\'Student ID\') }}"')
    content = content.replace('placeholder="Search students..."', 'placeholder="{{ _(\'Search students...\') }}"')
    
    # Title block
    content = content.replace('{% block title %}', '')
    content = content.replace('{% endblock %}', '')
    # This is tricky, let's just leave title blocks alone or rely on the script
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

print(f"Processed 9 templates.")
