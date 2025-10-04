#!/usr/bin/env python3
"""
سكريبت لإنشاء جداول قاعدة البيانات
"""
import os
import sys
from datetime import datetime

# إضافة مسار المشروع
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User

def create_tables():
    """إنشاء جميع الجداول في قاعدة البيانات"""
    with app.app_context():
        try:
            # إنشاء جميع الجداول
            db.create_all()
            print("✅ تم إنشاء جميع الجداول بنجاح!")
            print("   - جدول المستخدمين (user)")
            print("   - جدول العملاء (client)")
            print("   - جدول الدفعات (payment)")
            print("   - جدول المستندات (document)")
            print("   - جدول المتابعات (followup)")
            
            # التحقق من وجود الأدمن
            admin_user = User.query.filter_by(username='Admin').first()
            
            if not admin_user:
                # إنشاء مستخدم الأدمن
                admin = User(
                    username='Admin',
                    password='Admin2025',
                    role='admin',
                    is_active=True
                )
                
                db.session.add(admin)
                db.session.commit()
                
                print("✅ تم إنشاء مستخدم الأدمن!")
                print("   اسم المستخدم: Admin")
                print("   كلمة المرور: Admin2025")
            else:
                print("✅ مستخدم الأدمن موجود بالفعل!")
                
        except Exception as e:
            print(f"❌ خطأ في إنشاء الجداول: {e}")

if __name__ == "__main__":
    create_tables()
