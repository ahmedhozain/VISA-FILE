#!/usr/bin/env python3
"""
سكريبت لإعداد المستخدم المدير في قاعدة البيانات
"""
import os
import sys
from dotenv import load_dotenv

# إضافة مسار المشروع
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User

def setup_admin_user():
    """إعداد المستخدم المدير"""
    with app.app_context():
        try:
            # التحقق من وجود المستخدم المدير
            admin_user = User.query.filter_by(username='admin').first()
            
            if admin_user:
                print(f"✅ المستخدم المدير موجود بالفعل:")
                print(f"   - اسم المستخدم: {admin_user.username}")
                print(f"   - اسم الموظف: {admin_user.employee_name}")
                print(f"   - الدور: {admin_user.role}")
                print(f"   - نشط: {admin_user.is_active}")
                
                # التأكد من أن الدور هو admin
                if admin_user.role != 'admin':
                    admin_user.role = 'admin'
                    db.session.commit()
                    print("✅ تم تحديث دور المستخدم إلى admin")
            else:
                print("❌ المستخدم المدير غير موجود، سيتم إنشاؤه...")
                
                # إنشاء المستخدم المدير الجديد
                admin_user = User(
                    employee_name='مدير النظام',
                    username='admin',
                    password='admin123',  # كلمة مرور بسيطة للبداية
                    role='admin',
                    is_active=True
                )
                
                db.session.add(admin_user)
                db.session.commit()
                
                print("✅ تم إنشاء المستخدم المدير بنجاح:")
                print(f"   - اسم المستخدم: admin")
                print(f"   - كلمة المرور: admin123")
                print(f"   - الدور: admin")
                
        except Exception as e:
            print(f"❌ خطأ في إعداد المستخدم المدير: {e}")
            db.session.rollback()

def list_all_users():
    """عرض جميع المستخدمين"""
    with app.app_context():
        try:
            users = User.query.all()
            if users:
                print(f"\n📋 جميع المستخدمين ({len(users)} مستخدم):")
                print("-" * 60)
                for user in users:
                    status = "نشط" if user.is_active else "غير نشط"
                    print(f"ID: {user.id} | المستخدم: {user.username} | الموظف: {user.employee_name} | الدور: {user.role} | الحالة: {status}")
            else:
                print("❌ لا توجد مستخدمين في قاعدة البيانات")
        except Exception as e:
            print(f"❌ خطأ في عرض المستخدمين: {e}")

if __name__ == "__main__":
    load_dotenv()
    
    print("🔧 إعداد المستخدم المدير...")
    print("=" * 50)
    
    setup_admin_user()
    list_all_users()
    
    print("\n" + "=" * 50)
    print("🎉 تم الانتهاء من الإعداد!")
    print("💡 يمكنك الآن تسجيل الدخول باستخدام:")
    print("   - اسم المستخدم: admin")
    print("   - كلمة المرور: admin123")
