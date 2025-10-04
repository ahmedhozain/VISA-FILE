#!/usr/bin/env python3
"""
سكريبت لاختبار التدفق الكامل لتسجيل الدخول
"""
import os
import sys
from datetime import datetime

# إضافة مسار المشروع
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User

def test_complete_login_flow():
    """اختبار التدفق الكامل لتسجيل الدخول"""
    with app.app_context():
        try:
            print("🔍 اختبار التدفق الكامل لتسجيل الدخول...")
            print("=" * 60)
            
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
            print(f"   نوع المستخدم: {admin_user.role}")
            print(f"   الحالة: {'نشط' if admin_user.is_active else 'غير نشط'}")
            
            # 2. اختبار تسجيل الدخول
            print("\n🔐 اختبار تسجيل الدخول:")
            
            # اختبار بيانات صحيحة
            if admin_user.check_password('Admin2025'):
                print("✅ كلمة المرور صحيحة")
            else:
                print("❌ كلمة المرور غير صحيحة")
                return
            
            # اختبار بيانات خاطئة
            if not admin_user.check_password('wrong_password'):
                print("✅ رفض كلمة المرور الخاطئة")
            else:
                print("❌ قبول كلمة المرور الخاطئة")
                return
            
            # 3. التحقق من الصلاحيات
            print("\n👑 اختبار الصلاحيات:")
            if admin_user.is_admin():
                print("✅ المستخدم له صلاحيات الأدمن")
            else:
                print("❌ المستخدم ليس له صلاحيات الأدمن")
                return
            
            # 4. اختبار الروابط
            print("\n🔗 اختبار الروابط:")
            
            # اختبار route تسجيل الدخول
            with app.test_client() as client:
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
                
                # اختبار route إدارة الملفات
                response = client.get('/file_management')
                if response.status_code == 200:
                    print("✅ صفحة إدارة الملفات تعمل")
                else:
                    print("❌ صفحة إدارة الملفات لا تعمل")
                    return
                
                # اختبار route متابعة العميل
                response = client.get('/client_followup')
                if response.status_code == 200:
                    print("✅ صفحة متابعة العميل تعمل")
                else:
                    print("❌ صفحة متابعة العميل لا تعمل")
                    return
            
            print("\n🎯 تدفق العمل الكامل:")
            print("1. الضغط على 'العملاء المستاءين' في صفحة اختيار القسم")
            print("2. الانتقال إلى صفحة تسجيل الدخول")
            print("3. إدخال: Admin / Admin2025")
            print("4. الانتقال إلى صفحة العملاء المستاءين")
            print("5. الوصول إلى:")
            print("   - إدارة الملفات")
            print("   - متابعة العميل المستاء")
            print("   - الشئون القانونية")
            print("   - إدارة المستخدمين")
            
            print("\n✅ جميع الاختبارات نجحت!")
            
        except Exception as e:
            print(f"❌ خطأ في اختبار التدفق الكامل: {e}")

if __name__ == "__main__":
    test_complete_login_flow()
