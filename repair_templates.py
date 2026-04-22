import re
import os

tpl_dir = "c:/Users/Anitr/OneDrive/Desktop/SAS/templates"
files = [f for f in os.listdir(tpl_dir) if f.endswith(".html") and f != "base.html"]

for filename in files:
    filepath = os.path.join(tpl_dir, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Restore endblock at the very end of the file
    content = content.strip() + "\n{% endblock %}\n"
    
    # Restore block title
    # My faulty script removed '{% block title %}' and '{% endblock %}' entirely.
    # It left the title text naked on line 3, bordered by empty lines.
    # We find text between 'extends "base.html" %}' and '{% block content %}' and wrap it
    
    match = re.search(r'\{% extends "base.html" %\}(.*?)\{% block content %\}', content, re.DOTALL)
    if match:
        middle = match.group(1).strip()
        if middle:
            # Reconstruct the block title
            new_middle = f"\n\n{{% block title %}}{middle}{{% endblock %}}\n\n"
            content = content.replace(match.group(1), new_middle)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

print("Repaired templates")
