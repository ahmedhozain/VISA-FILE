#!/usr/bin/env python3
"""
سكريبت لاختبار تدفق تسجيل الدخول
"""
import os
import sys
from datetime import datetime

# إضافة مسار المشروع
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User

def test_login_flow():
    """اختبار تدفق تسجيل الدخول"""
    with app.app_context():
        try:
            print("🔍 اختبار تدفق تسجيل الدخول...")
            print("=" * 50)
            
            # 1. التحقق من وجود الأدمن
            admin_user = User.query.filter_by(username='Admin').first()
            
            if admin_user:
                print("✅ مستخدم الأدمن موجود:")
                print(f"   اسم المستخدم: {admin_user.username}")
                print(f"   كلمة المرور: {admin_user.password}")
                print(f"   نوع المستخدم: {admin_user.role}")
                print(f"   الحالة: {'نشط' if admin_user.is_active else 'غير نشط'}")
            else:
                print("❌ مستخدم الأدمن غير موجود!")
                print("   قم بتشغيل: python create_admin.py")
                return
            
            # 2. اختبار تسجيل الدخول
            print("\n🔐 اختبار تسجيل الدخول:")
            
            # اختبار بيانات صحيحة
            if admin_user.check_password('Admin2025'):
                print("✅ كلمة المرور صحيحة")
            else:
                print("❌ كلمة المرور غير صحيحة")
            
            # اختبار بيانات خاطئة
            if not admin_user.check_password('wrong_password'):
                print("✅ رفض كلمة المرور الخاطئة")
            else:
                print("❌ قبول كلمة المرور الخاطئة")
            
            # 3. التحقق من الصلاحيات
            print("\n👑 اختبار الصلاحيات:")
            if admin_user.is_admin():
                print("✅ المستخدم له صلاحيات الأدمن")
            else:
                print("❌ المستخدم ليس له صلاحيات الأدمن")
            
            print("\n🎯 تدفق تسجيل الدخول:")
            print("1. الضغط على 'العملاء المستاءين' في صفحة اختيار القسم")
            print("2. الانتقال إلى صفحة تسجيل الدخول")
            print("3. إدخال: Admin / Admin2025")
            print("4. الانتقال إلى صفحة العملاء المستاءين")
            
        except Exception as e:
            print(f"❌ خطأ في اختبار تسجيل الدخول: {e}")

if __name__ == "__main__":
    test_login_flow()
