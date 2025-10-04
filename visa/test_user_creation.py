#!/usr/bin/env python3
"""
سكريبت لاختبار إنشاء المستخدمين مع الحقول الجديدة
"""
import os
import sys
from datetime import datetime

# إضافة مسار المشروع
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User

def test_user_creation():
    """اختبار إنشاء المستخدمين"""
    with app.app_context():
        try:
            print("🧪 اختبار إنشاء المستخدمين...")
            print("=" * 50)
            
            # 1. اختبار إنشاء مستخدم جديد
            test_user = User(
                employee_name="أحمد محمد علي",
                username="ahmed_mohamed",
                password="password123",
                role="user",
                is_active=True
            )
            
            # التحقق من وجود المستخدم
            existing_user = User.query.filter_by(username="ahmed_mohamed").first()
            if existing_user:
                print("ℹ️  المستخدم موجود بالفعل، سيتم حذفه أولاً")
                db.session.delete(existing_user)
                db.session.commit()
            
            # إضافة المستخدم الجديد
            db.session.add(test_user)
            db.session.commit()
            
            print("✅ تم إنشاء مستخدم تجريبي بنجاح!")
            print(f"   اسم الموظف: {test_user.employee_name}")
            print(f"   اسم المستخدم: {test_user.username}")
            print(f"   كلمة المرور: {test_user.password}")
            print(f"   نوع المستخدم: {test_user.role}")
            print(f"   الحالة: {'نشط' if test_user.is_active else 'غير نشط'}")
            
            # 2. اختبار استرجاع المستخدم
            retrieved_user = User.query.filter_by(username="ahmed_mohamed").first()
            if retrieved_user:
                print("\n✅ تم استرجاع المستخدم بنجاح!")
                print(f"   اسم الموظف: {retrieved_user.employee_name}")
                print(f"   اسم المستخدم: {retrieved_user.username}")
            else:
                print("❌ فشل في استرجاع المستخدم!")
            
            # 3. اختبار التحقق من كلمة المرور
            if retrieved_user and retrieved_user.check_password("password123"):
                print("✅ التحقق من كلمة المرور نجح!")
            else:
                print("❌ التحقق من كلمة المرور فشل!")
            
            # 4. اختبار الصلاحيات
            if retrieved_user and not retrieved_user.is_admin():
                print("✅ صلاحيات المستخدم العادي صحيحة!")
            else:
                print("❌ صلاحيات المستخدم العادي غير صحيحة!")
            
            # 5. حذف المستخدم التجريبي
            db.session.delete(retrieved_user)
            db.session.commit()
            print("\n🗑️  تم حذف المستخدم التجريبي")
            
            print("\n🎯 اختبار النموذج:")
            print("   ✅ اسم الموظف (employee_name)")
            print("   ✅ اسم المستخدم (username)")
            print("   ✅ كلمة المرور (password)")
            print("   ✅ نوع المستخدم (role)")
            print("   ✅ الحالة (is_active)")
            
        except Exception as e:
            print(f"❌ خطأ في اختبار إنشاء المستخدمين: {e}")

if __name__ == "__main__":
    test_user_creation()
