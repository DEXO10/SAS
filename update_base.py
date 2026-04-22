import os
import re

tpl_dir = "c:/Users/Anitr/OneDrive/Desktop/SAS/templates"

def replace_file(filename, replacements):
    path = os.path.join(tpl_dir, filename)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for old, new in replacements:
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
        
# 1. Base.html
base_reps = [
    ('<html lang="en">', '<html lang="{{ lang }}" dir="{{ \'rtl\' if lang == \'ar\' else \'ltr\' }}">'),
    ('Student Attendance System', "{{ _('Student Attendance System') }}"),
    ('<span class="brand-text">Student Attendance</span>', '<span class="brand-text">{{ _(\'Student Attendance\') }}</span>'),
    ('<span class="nav-text">Dashboard</span>', '<span class="nav-text">{{ _(\'Dashboard\') }}</span>'),
    ('<span class="nav-text">Students</span>', '<span class="nav-text">{{ _(\'Students\') }}</span>'),
    ('<span class="nav-text">Courses</span>', '<span class="nav-text">{{ _(\'Courses\') }}</span>'),
    ('<span class="nav-text">Reports</span>', '<span class="nav-text">{{ _(\'Reports\') }}</span>'),
    ('<span class="nav-text">Settings</span>', '<span class="nav-text">{{ _(\'Settings\') }}</span>'),
    ('<span class="nav-text">Logout</span>', '<span class="nav-text">{{ _(\'Logout\') }}</span>'),
]
replace_file("base.html", base_reps)

# Add Toggle Button to Base topbar
with open(os.path.join(tpl_dir, "base.html"), "r", encoding="utf-8") as f:
    base_content = f.read()
    
toggle_html = """                <div class="topbar-actions" style="margin-left:auto; display:flex; gap:16px; align-items:center;">
                    {% if lang == 'en' %}
                        <a href="{{ url_for('setlang', lang='ar') }}" class="btn btn-secondary" style="text-decoration:none; padding:4px 8px; border-radius:4px; font-weight:bold;">عربي</a>
                    {% else %}
                        <a href="{{ url_for('setlang', lang='en') }}" class="btn btn-secondary" style="text-decoration:none; padding:4px 8px; border-radius:4px; font-weight:bold;">EN</a>
                    {% endif %}
                </div>"""
if "topbar-actions" not in base_content:
    base_content = base_content.replace(
        '<div class="topbar-title">{% block page_title %}{% endblock %}</div>',
        '<div class="topbar-title">{% block page_title %}{% endblock %}</div>\n' + toggle_html
    )
with open(os.path.join(tpl_dir, "base.html"), "w", encoding="utf-8") as f:
    f.write(base_content)

print("Updated base.html")
