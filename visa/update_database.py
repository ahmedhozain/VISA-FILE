#!/usr/bin/env python3
"""
سكريبت لتحديث قاعدة البيانات مع حقل اسم الموظف
"""
import os
import sys
from datetime import datetime

# إضافة مسار المشروع
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User

def update_database():
    """تحديث قاعدة البيانات مع الحقول الجديدة"""
    with app.app_context():
        try:
            print("🔄 تحديث قاعدة البيانات...")
            print("=" * 50)
            
            # إنشاء جميع الجداول (سيتم تحديثها تلقائياً)
            db.create_all()
            print("✅ تم إنشاء/تحديث الجداول بنجاح!")
            
            # التحقق من المستخدمين الموجودين
            users = User.query.all()
            
            if users:
                print(f"\n👥 المستخدمين الموجودين: {len(users)}")
                
                for user in users:
                    # إذا لم يكن لديه اسم موظف، أضف اسم افتراضي
                    if not hasattr(user, 'employee_name') or not user.employee_name:
                        if user.username == 'Admin':
                            user.employee_name = 'مدير النظام'
                        else:
                            user.employee_name = f'موظف {user.username}'
                        
                        db.session.commit()
                        print(f"✅ تم تحديث المستخدم: {user.username}")
                    else:
                        print(f"ℹ️  المستخدم {user.username} محدث بالفعل")
            else:
                print("📭 لا توجد مستخدمين في قاعدة البيانات")
                print("   قم بتشغيل: python create_admin.py")
            
            print("\n🎯 الحقول الجديدة:")
            print("   ✅ اسم الموظف (employee_name)")
            print("   ✅ اسم المستخدم (username)")
            print("   ✅ كلمة المرور (password)")
            print("   ✅ نوع المستخدم (role)")
            print("   ✅ الحالة (is_active)")
            print("   ✅ تاريخ الإنشاء (created_at)")
            
        except Exception as e:
            print(f"❌ خطأ في تحديث قاعدة البيانات: {e}")

if __name__ == "__main__":
    update_database()
