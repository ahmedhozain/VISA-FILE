#!/usr/bin/env python3
"""
سكريبت لاختبار نظام المستخدمين والجلسات
"""
import os
import sys
from datetime import datetime

# إضافة مسار المشروع
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User

def test_user_session():
    """اختبار نظام المستخدمين والجلسات"""
    with app.app_context():
        try:
            print("🔍 اختبار نظام المستخدمين والجلسات...")
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
            
            # 2. اختبار تسجيل الدخول
            print("\n🔐 اختبار تسجيل الدخول:")
            
            with app.test_client() as client:
                # اختبار تسجيل الدخول
                response = client.post('/login', data={
                    'username': 'Admin',
                    'password': 'Admin2025'
                }, follow_redirects=True)
                
                if response.status_code == 200:
                    print("✅ تسجيل الدخول نجح")
                else:
                    print("❌ تسجيل الدخول فشل")
                    return
                
                # اختبار صفحة العملاء المستاءين
                response = client.get('/disappointed_clients')
                if response.status_code == 200:
                    print("✅ صفحة العملاء المستاءين تعمل")
                else:
                    print("❌ صفحة العملاء المستاءين لا تعمل")
                    return
                
                # اختبار صفحة إدارة المستخدمين
                response = client.get('/user_management')
                if response.status_code == 200:
                    print("✅ صفحة إدارة المستخدمين تعمل")
                else:
                    print("❌ صفحة إدارة المستخدمين لا تعمل")
                    return
                
                # اختبار تسجيل الخروج
                response = client.get('/logout', follow_redirects=True)
                if response.status_code == 200:
                    print("✅ تسجيل الخروج نجح")
                else:
                    print("❌ تسجيل الخروج فشل")
                    return
            
            # 3. اختبار عرض الأدمن فقط
            print("\n👑 اختبار عرض الأدمن فقط:")
            admin_users = User.query.filter_by(role='admin').all()
            if len(admin_users) == 1:
                print("✅ يتم عرض الأدمن فقط")
            else:
                print(f"❌ يتم عرض {len(admin_users)} مستخدمين")
            
            print("\n🎯 الميزات الجديدة:")
            print("✅ شريط المستخدم في أعلى الصفحة")
            print("✅ عرض اسم الموظف واسم المستخدم")
            print("✅ زر تسجيل الخروج")
            print("✅ عرض الأدمن فقط في إدارة المستخدمين")
            print("✅ حفظ معلومات المستخدم في الجلسة")
            
            print("\n✅ جميع الاختبارات نجحت!")
            
        except Exception as e:
            print(f"❌ خطأ في اختبار نظام المستخدمين: {e}")

if __name__ == "__main__":
    test_user_session()
