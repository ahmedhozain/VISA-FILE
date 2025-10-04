#!/usr/bin/env python3
"""
سكريبت لإنشاء جدول العملاء المكتملين في قاعدة البيانات
"""

from app import app, db

def create_completed_clients_table():
    """إنشاء جدول العملاء المكتملين"""
    with app.app_context():
        try:
            # إنشاء الجدول الجديد
            db.create_all()
            print("✅ تم إنشاء جدول العملاء المكتملين بنجاح!")
            
            # التحقق من وجود الجدول
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'completed_client' in tables:
                print("✅ تم التحقق من وجود الجدول في قاعدة البيانات")
            else:
                print("❌ لم يتم العثور على الجدول")
                
        except Exception as e:
            print(f"❌ خطأ في إنشاء الجدول: {e}")

if __name__ == "__main__":
    create_completed_clients_table()

