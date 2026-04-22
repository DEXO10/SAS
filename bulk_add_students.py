import sqlite3
import sys

# Ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    try:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except Exception:
        pass

def insert_students():
    conn = None
    try:
        conn = sqlite3.connect('attendance.db')
        conn.text_factory = str
        cursor = conn.cursor()
        
        # 1. Find the stage ID for "المرحلة الثالثة"
        cursor.execute("SELECT id, name FROM stages")
        rows = cursor.fetchall()
        
        stage_id = None
        target_name = "المرحلة الثالثة"
        
        for sid, sname in rows:
            if target_name in sname:
                stage_id = sid
                break
        
        if not stage_id:
            print(f"ERROR: Could not find stage '{target_name}'.")
            print("Current stages in DB:")
            for sid, sname in rows:
                print(f" - {sid}: {sname}")
            return

        print(f"Found stage '{target_name}' (ID: {stage_id})")

        # 2. Student List
        names_text = """
ابراهيم محسن جويد عظيم
احمد فراس عدنان محمد
احمد قصي جهاد زغير
اديل علاء جرجيس داود
اسدالله علاء عبد كاظم
اكرم فؤاد اكرم عبد الامير
امير عائد علي حسين
ايمن احمد عزيز منصور
ايه حبيب عبد الكاظم محمد
ايه خالد سلمان فاخر
بتول علاء محمد رضا عبد الغني
جعفر محمد حسين محمد
حازم فاضل قاسم محمد
حسين سمير اسماعيل ابراهيم
حسين شيركو حسين اسد
حسين علي عبد الجليل ريكان
حسين محمد صاحب ناصر
حيدر حسين علي جودي
حيدر صلاح مطر حمدان
حيدر ماجد خضير يوسف
ذو الفقار جاسب مختاض موزان البهادلي
رفل علاء محمد صالح
رقيه علي كاظم حسن
زيد رياض سلمان عباس
زينب سعود سلمان سعود
سجاد طارق جبار محسن
سجاد قدري عطاء كاظم
سجود صادق خالد جاسم
طيبه جواد كاظم علي
عباس احمد بيان مهدي
عباس حسين عباس حسين
عباس خالد عباس كاظم
عباس عامر محمد عزيز
عبد الله احمد محمد عبود
عبد الودود فريد رمضان احمد
علاء عبد الكريم جبار عبد
علي احمد مطشر جبر
علي اكبر عبد الرضا زيدان ثجيل
علي حسين علي حميد الدراجي
علي حسين علي دوهان
علي حسين محسن عذاب
علي سعدي مزعل لطيف
علي كاظم خلف خزيم
علي كاظم سعد خلف
علي محمد عبد الرزاق عبد
علي ميثاق جعفر محسن
علي نجم عبد خاجي
عمر سالم شاكر نصر الله
فهد قيس رحيم غازي
فينا خاي عزيز
كميل احمد محمود شايع
محمد الباقر احمد محمود شايع
محمد الباقر رافد محمد عريمش
محمد باقر ابراهيم فيصل ابراهيم
محمد رامي فرحان زاير
محمد عبد الجبار كاظم كطيش
محمد فراس محمد مكلف
محمد موسى اسماعيل عمران
مرتضى ابراهيم طاهر صحن
مسلم عقيل عبد علي انفاوه
مسلم هيثم قاسم محمد
مصطفى احمد ابراهيم صالح
مصطفى عبد الحليم احمد علي العميري
مصطفى فلاح حسن جابر
منتظر علي خيري عبد الامير
منتظر مظفر نوري عبد الحسن
مؤمل محمد عبد الحسن خلف
نرجس صبيح جبر جاسم
هاشم نبيل هادي كريم
هبه علي غازي عزيز
همام زياد خليفه جسام
"""
        names = [n.strip() for n in names_text.strip().split('\n') if n.strip()]

        # 3. Insert loop
        count = 0
        start_num = 30001
        for i, name in enumerate(names):
            num = start_num + i
            email = f"{num}@stu.edu.iq"
            uid = f"S{num}"
            
            try:
                cursor.execute(
                    "INSERT INTO students (name, stage_id, student_uid, email) VALUES (?, ?, ?, ?)",
                    (name, stage_id, uid, email)
                )
                count += 1
            except sqlite3.Error as e:
                print(f"Skipped {name}: {e}")

        conn.commit()
        print(f"Successfully added {count} students to '{target_name}'.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    insert_students()
