import re
import os

app_path = "c:/Users/Anitr/OneDrive/Desktop/SAS/app.py"

with open(app_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add Babel imports and initialization
setup_code = """app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')

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
    return dict(lang=session.get('lang', 'en'))"""

content = content.replace("app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')", setup_code)

# 2. Update ROLES
roles_old = """ROLES = {
    'admin': {'label': 'Admin', 'level': 3},
    'department_head': {'label': 'Department Head', 'level': 2},
    'teacher': {'label': 'Teacher', 'level': 1}
}"""
roles_new = """ROLES = {
    'admin': {'label': _l('Admin'), 'level': 3},
    'department_head': {'label': _l('Department Head'), 'level': 2},
    'teacher': {'label': _l('Teacher'), 'level': 1}
}"""
content = content.replace(roles_old, roles_new)

# 3. Replace simple string literals in flash() and errors.append()
content = re.sub(r"flash\('([^']+)'", r"flash(_('\1')", content)
content = re.sub(r"errors\.append\('([^']+)'\)", r"errors.append(_('\1'))", content)

# 4. Handle some f-strings in flash dynamically, e.g. flash(f'...' )
# Note: gettext doesn't play perfectly with f-strings at extraction, but since it's just a few we'll fix them manually or use .format()
content = re.sub(r"flash\(f'([^']+)'", r"flash(_('\1')", content)

with open(app_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated app.py")
