# Page Design Spec (Desktop-first)

## Global Styles (applies to all pages)
- Layout system: CSS Grid for app shell (sidebar + main), Flexbox inside cards/tables.
- Tokens:
  - Background: #F7F8FA; Surface: #FFFFFF; Border: #E5E7EB
  - Text: #111827 (primary), #6B7280 (muted)
  - Accent: #2563EB; Accent hover: #1D4ED8
  - Status chips: Present #16A34A, Absent #DC2626, Late #F59E0B
  - Radius: 10px cards; 6px inputs/buttons; Shadow: subtle (0 1px 2px rgba(0,0,0,.06))
- Typography: 16px base; H1 24/28, H2 18/24; mono for CSV hint text optional.
- Buttons: primary (accent), secondary (surface+border), destructive (red). Hover = darker bg, focus ring = accent 2px.
- Links: accent + underline on hover.

## App Shell (base.html)
- Page structure: two-column grid.
  - Left: collapsible sidebar (expanded ~240px, collapsed ~72px).
  - Right: main content with page header + body.
- Sidebar components:
  - Top: brand/app name + collapse toggle.
  - Nav items: Dashboard, Student Registry, (context links like Reports shown when in course pages).
  - Active state: accent left border + slightly tinted background.
- Responsive behavior:
  - Desktop-first. Below ~900px: sidebar defaults collapsed; toggle remains accessible.
  - Optional: overlay drawer mode below ~640px (keep minimal JS).

## Page: Login (login.html)
- Meta:
  - Title: "Login"; Description: "Sign in to manage attendance".
- Layout:
  - Centered card (max-width 420px) with logo/title, form, and error banner.
- Components:
  - Text inputs: username, password; primary button: "Sign in".
  - Error state: red bordered banner under title.

## Page: Dashboard (dashboard.html)
- Meta: Title "Dashboard".
- Structure:
  - Header row: title + add course form (input + button).
  - Body: course cards in 2–3 column grid (auto-fit minmax 260px).
- Components:
  - Course card: course name, primary action "Open".

## Page: Course Details (course_detail.html)
- Meta: Title "Course".
- Structure:
  - Header: course name; actions: "Start today’s attendance", link "View reports".
  - Two sections stacked:
    1) Enrolled students table
    2) Quick add student (legacy form stays)
- Enrolled table:
  - Columns: Student name, (optional) assignment indicator, action link "Manage in registry".

## Page: Attendance Session (mark_attendance.html)
- Meta: Title "Mark Attendance".
- Structure:
  - Header: course name + session date; sticky save bar (top or bottom).
  - Table list of students.
- Components:
  - Row: student name + segmented control (Present/Absent/Late) with colored states.
  - Primary CTA: "Save".

## Page: Reports (reports.html)
- Meta: Title "Reports".
- Structure:
  - Header: course name; controls: date range (from/to) + "Apply" + "Export CSV".
  - Session list table: date, count, action "View".

## Page: Session Report (session_report.html)
- Meta: Title "Session Report".
- Structure:
  - Header: course name + date; actions: "Export CSV".
  - Top summary: three stat cards (Present/Absent/Late totals).
  - Detail table: student name, status chip.

## Page: Student Registry (new template: students.html)
- Meta: Title "Student Registry".
- Structure:
  - Header: title + create student inline (name input + button).
  - Body split (desktop):
    - Left: student list (search box + list/table)
    - Right: assignment panel for selected student
- Assignment panel:
  - Show selected student name.
  - Course checklist (or multi-select) + "Save assignments".
  - Keep actions form-based to match existing code simplicity.
