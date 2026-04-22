import os
import re

tpl_dir = "c:/Users/Anitr/OneDrive/Desktop/SAS/templates"
files = [f for f in os.listdir(tpl_dir) if f.endswith(".html") and f != "base.html"]

strings_to_translate = [
    "Sign in to manage courses and attendance",
    "Welcome Back",
    "Username",
    "Password",
    "Sign in",
    "Demo Accounts",
    "Admin",
    "admin / admin123",
    "Dept Head",
    "dept_head / head123",
    "Teacher",
    "teacher1 / teacher123",
    "Dashboard",
    "Students",
    "Courses",
    "Reports",
    "Settings",
    "Logout",
    "Student Attendance",
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

def wrap(m, s):
    # s is the string matched
    # meaning we reconstruct the spaces around it
    return m.group(1) + f"{{{{ _('{s}') }}}}" + m.group(3)

for filename in files:
    filepath = os.path.join(tpl_dir, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    for s in sorted(strings_to_translate, key=len, reverse=True):
        # find the exact string allowing arbitrary spaces before and after mostly around tags
        # we look for "> spaces string spaces <"
        escaped_s = re.escape(s)
        # re.sub with a function or just capturing groups
        pattern = r"(>[\s]*?)(" + escaped_s + r")([\s]*?<)"
        content = re.sub(pattern, lambda m, st=s: wrap(m, st), content)

        # sometimes it's inside quotes, e.g. placeholder="Username"
        # we will handle placeholders
        content = re.sub(r'(placeholder="[\s]*?)(' + escaped_s + r')([\s]*?")',
                         lambda m, st=s: m.group(1) + f"{{{{ _('{st}') }}}}" + m.group(3), content)
                         
        # sometimes text without tags around it, like after a div
        # we skip, the above should cover 90%
        
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

print("done flexible wrap")
