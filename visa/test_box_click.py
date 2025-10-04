#!/usr/bin/env python3
"""
سكريبت لاختبار الضغط على البوكس
"""
import os
import sys
from datetime import datetime

# إضافة مسار المشروع
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User

def test_box_click():
    """اختبار الضغط على البوكس"""
    with app.app_context():
        try:
            print("🔍 اختبار الضغط على البوكس...")
            print("=" * 50)
            
            # 1. التحقق من وجود الأدمن
            admin_user = User.query.filter_by(username='Admin').first()
            
            if not admin_user:
                print("❌ مستخدم الأدمن غير موجود!")
                print("   قم بتشغيل: python create_admin.py")
                return
            
            print("✅ مستخدم الأدمن موجود:")
            print(f"   اسم الموظف: {admin_user.employee_name}")
            print(f"   اسم المستخدم: {admin_user.username}")
            print(f"   كلمة المرور: {admin_user.password}")
            
            # 2. اختبار الروابط
            print("\n🔗 اختبار الروابط:")
            
            with app.test_client() as client:
                # اختبار route تسجيل الدخول
                response = client.get('/login')
                if response.status_code == 200:
                    print("✅ صفحة تسجيل الدخول تعمل")
                else:
                    print("❌ صفحة تسجيل الدخول لا تعمل")
                    return
                
                # اختبار route العملاء المستاءين
                response = client.get('/disappointed_clients')
                if response.status_code == 200:
                    print("✅ صفحة العملاء المستاءين تعمل")
                else:
                    print("❌ صفحة العملاء المستاءين لا تعمل")
                    return
            
            print("\n🎯 تدفق العمل الجديد:")
            print("1. الضغط على بوكس 'العملاء المستاءين'")
            print("2. الانتقال مباشرة إلى صفحة تسجيل الدخول")
            print("3. إدخال: Admin / Admin2025")
            print("4. الانتقال إلى صفحة العملاء المستاءين")
            print("5. الوصول إلى جميع الأقسام")
            
            print("\n✅ جميع الاختبارات نجحت!")
            
        except Exception as e:
            print(f"❌ خطأ في اختبار الضغط على البوكس: {e}")

if __name__ == "__main__":
    test_box_click()
