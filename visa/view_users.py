#!/usr/bin/env python3
"""
سكريبت لعرض المستخدمين المخزنين في قاعدة البيانات
"""
import os
import sys
from datetime import datetime

# إضافة مسار المشروع
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User

def view_users():
    """عرض جميع المستخدمين"""
    with app.app_context():
        try:
            users = User.query.all()
            
            if not users:
                print("📭 لا توجد مستخدمين في قاعدة البيانات")
                return
            
            print("👥 المستخدمين المخزنين في قاعدة البيانات:")
            print("=" * 60)
            
            for user in users:
                status = "🟢 نشط" if user.is_active else "🔴 غير نشط"
                role_icon = "👑" if user.role == 'admin' else "👤"
                
                print(f"{role_icon} المستخدم #{user.id}")
                print(f"   اسم الموظف: {user.employee_name}")
                print(f"   اسم المستخدم: {user.username}")
                print(f"   كلمة المرور: {user.password}")
                print(f"   نوع المستخدم: {user.role}")
                print(f"   الحالة: {status}")
                print(f"   تاريخ الإنشاء: {user.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print("-" * 40)
            
            print(f"\n📊 إجمالي المستخدمين: {len(users)}")
            
        except Exception as e:
            print(f"❌ خطأ في عرض المستخدمين: {e}")

if __name__ == "__main__":
    view_users()
