import os
import re

tpl_dir = "c:/Users/Anitr/OneDrive/Desktop/SAS/templates"
files = [f for f in os.listdir(tpl_dir) if f.endswith(".html") and f != "base.html"]

for filename in files:
    filepath = os.path.join(tpl_dir, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # The problem: {% block title %}Text\n{% block page_title %}...
    # We need to close {% block title %} at the end of the line
    
    # 1. find {% block title %} line, and make sure it has {% endblock %} on the same line if it doesn't
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if '{% block title %}' in line and '{% endblock %}' not in line:
            lines[i] = line + '{% endblock %}'
            
    content = '\n'.join(lines)
        
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

print("Repaired title blocks")
