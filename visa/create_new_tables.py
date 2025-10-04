#!/usr/bin/env python3
"""
سكريبت لإنشاء الجداول الجديدة في قاعدة البيانات
"""
import os
import sys

# إضافة مسار المشروع
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# إعداد متغيرات البيئة
os.environ['DATABASE_URL'] = 'postgresql://ahmed_uv8c_user:Ycp5PKkvYcD3MbgK630brKay8cwr3xg7@dpg-d26fk9bipnbc73b2dvk0-a.oregon-postgres.render.com/ahmed_uv8c?sslmode=require'

from app import app, db

def create_new_tables():
    """إنشاء الجداول الجديدة"""
    with app.app_context():
        try:
            print("🔧 جاري إنشاء الجداول الجديدة...")
            
            # إنشاء جميع الجداول
            db.create_all()
            
            print("✅ تم إنشاء الجداول بنجاح:")
            print("   - جدول DisappointedClient (إدارة الملفات)")
            print("   - جدول ClientFollowup (متابعة العميل المستاء)")
            print("   - جدول LegalCase (الشؤون القانونية)")
            
        except Exception as e:
            print(f"❌ خطأ في إنشاء الجداول: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    create_new_tables()
