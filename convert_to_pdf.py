import re
from pathlib import Path
from fpdf import FPDF

md_file = Path(__file__).parent / "PRESENTATION.md"
pdf_file = Path(__file__).parent / "PRESENTATION.pdf"

md_content = md_file.read_text(encoding="utf-8")

def clean_text(text):
    replacements = {
        "\u251c": "|",
        "\u2500": "-",
        "\u2514": "`",
        "\u2502": "|",
        "\u2022": "-",
        "\u2014": "--",
        "\u2013": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2192": "->",
        "\u2190": "<-",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, "Student Attendance Tracking System - Graduation Project", align="R")
        self.ln(3)
        self.set_draw_color(200, 200, 200)
        self.line(10, 12, 200, 12)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def add_h1(self, text):
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(30, 64, 175)
        self.ln(4)
        self.cell(0, 12, clean_text(text), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(30, 64, 175)
        self.set_line_width(0.8)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def add_h2(self, text):
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(30, 64, 175)
        self.ln(3)
        self.cell(0, 10, clean_text(text), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(229, 231, 235)
        self.set_line_width(0.4)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def add_h3(self, text):
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(55, 65, 81)
        self.ln(2)
        self.cell(0, 8, clean_text(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def add_paragraph(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(26, 26, 26)
        self.multi_cell(0, 5.5, clean_text(text))
        self.ln(2)

    def add_bold_paragraph(self, text):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(26, 26, 26)
        self.multi_cell(0, 5.5, clean_text(text))
        self.ln(2)

    def add_bullet(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(26, 26, 26)
        self.cell(8, 5.5, "-")
        self.multi_cell(0, 5.5, clean_text(text))
        self.ln(1)

    def add_numbered(self, num, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(26, 26, 26)
        self.cell(10, 5.5, f"{num}.")
        self.multi_cell(0, 5.5, clean_text(text))
        self.ln(1)

    def add_code_block(self, code):
        self.set_fill_color(30, 41, 59)
        self.set_text_color(226, 232, 240)
        self.set_font("Courier", "", 8)
        lines = clean_text(code).strip().split("\n")
        self.ln(2)
        for line in lines:
            line = line.replace("\t", "    ")
            if len(line) > 90:
                self.multi_cell(0, 4.5, line, fill=True)
            else:
                self.cell(0, 4.5, line, new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(3)
        self.set_text_color(26, 26, 26)

    def add_table(self, headers, rows):
        col_width = 180 / len(headers)
        self.set_fill_color(243, 244, 246)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(26, 26, 26)
        for header in headers:
            self.cell(col_width, 7, clean_text(header), border=1, fill=True)
        self.ln()
        
        self.set_font("Helvetica", "", 8.5)
        for i, row in enumerate(rows):
            if i % 2 == 1:
                self.set_fill_color(249, 250, 251)
            else:
                self.set_fill_color(255, 255, 255)
            max_height = 6
            for cell in row:
                self.cell(col_width, max_height, clean_text(str(cell)[:40]), border=1, fill=True)
            self.ln()
        self.ln(3)

    def add_hr(self):
        self.ln(4)
        self.set_draw_color(229, 231, 235)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

pdf = PDF()
pdf.alias_nb_pages()
pdf.set_auto_page_break(auto=True, margin=20)
pdf.add_page()

lines = md_content.split("\n")
i = 0
in_code_block = False
code_content = []
in_table = False
table_headers = []
table_rows = []
list_items = []
numbered_items = []

def flush_list():
    global list_items, numbered_items
    for item in list_items:
        pdf.add_bullet(item)
    list_items = []
    for num, item in numbered_items:
        pdf.add_numbered(num, item)
    numbered_items = []

while i < len(lines):
    line = lines[i]
    
    if line.startswith("```"):
        if in_code_block:
            pdf.add_code_block("\n".join(code_content))
            code_content = []
            in_code_block = False
        else:
            flush_list()
            in_code_block = True
        i += 1
        continue
    
    if in_code_block:
        code_content.append(line)
        i += 1
        continue
    
    if line.startswith("# "):
        flush_list()
        pdf.add_h1(line[2:].strip())
    elif line.startswith("## "):
        flush_list()
        pdf.add_h2(line[3:].strip())
    elif line.startswith("### "):
        flush_list()
        pdf.add_h3(line[4:].strip())
    elif line.startswith("---"):
        flush_list()
        pdf.add_hr()
    elif line.startswith("|") and "---" not in line:
        in_table = True
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if not table_headers:
            table_headers = cells
        else:
            table_rows.append(cells)
    elif line.startswith("|") and "---" in line:
        pass
    else:
        if in_table and table_headers:
            pdf.add_table(table_headers, table_rows)
            table_headers = []
            table_rows = []
            in_table = False
        
        stripped = line.strip()
        if stripped.startswith("- "):
            list_items.append(stripped[2:].strip())
        elif re.match(r"^\d+\.\s", stripped):
            match = re.match(r"^(\d+)\.\s(.*)", stripped)
            if match:
                numbered_items.append((match.group(1), match.group(2)))
        elif stripped:
            flush_list()
            if stripped.startswith("**") and stripped.endswith("**"):
                pdf.add_bold_paragraph(stripped.strip("*"))
            else:
                pdf.add_paragraph(stripped)
        else:
            flush_list()
    
    i += 1

if in_table and table_headers:
    pdf.add_table(table_headers, table_rows)

flush_list()

pdf.output(str(pdf_file))
print(f"PDF created: {pdf_file}")
