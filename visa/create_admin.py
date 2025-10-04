#!/usr/bin/env python3
"""
سكريبت لإنشاء مستخدم الأدمن
"""
import os
import sys
from datetime import datetime

# إضافة مسار المشروع
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User

def create_admin_user():
    """إنشاء مستخدم الأدمن"""
    with app.app_context():
        # التحقق من وجود الأدمن
        admin_user = User.query.filter_by(username='Admin').first()
        
        if admin_user:
            print("✅ مستخدم الأدمن موجود بالفعل!")
            print(f"   اسم المستخدم: {admin_user.username}")
            print(f"   كلمة المرور: Admin2025")
            print(f"   نوع المستخدم: {admin_user.role}")
            print(f"   الحالة: {'نشط' if admin_user.is_active else 'غير نشط'}")
        else:
            # إنشاء مستخدم الأدمن
            admin = User(
                employee_name='مدير النظام',
                username='Admin',
                password='Admin2025',
                role='admin',
                is_active=True
            )
            
            db.session.add(admin)
            db.session.commit()
            
            print("✅ تم إنشاء مستخدم الأدمن بنجاح!")
            print("   اسم المستخدم: Admin")
            print("   كلمة المرور: Admin2025")
            print("   نوع المستخدم: admin")
            print("   الحالة: نشط")

if __name__ == "__main__":
    create_admin_user()
