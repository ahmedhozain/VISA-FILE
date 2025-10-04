#!/usr/bin/env python3
"""
سكريبت مبسط لإعداد المستخدم المدير
"""
import os
import sys

# إضافة مسار المشروع
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# إعداد متغيرات البيئة
os.environ['DATABASE_URL'] = 'postgresql://ahmed_uv8c_user:Ycp5PKkvYcD3MbgK630brKay8cwr3xg7@dpg-d26fk9bipnbc73b2dvk0-a.oregon-postgres.render.com/ahmed_uv8c?sslmode=require'

from app import app, db, User

def create_admin():
    """إنشاء المستخدم المدير"""
    with app.app_context():
        try:
            print("🔧 جاري إنشاء المستخدم المدير...")
            
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
                    admin_user.is_active = True
                    db.session.commit()
                    print("✅ تم تحديث دور المستخدم إلى admin")
                    
            else:
                print("❌ المستخدم المدير غير موجود، سيتم إنشاؤه...")
                
                # إنشاء المستخدم المدير الجديد
                admin_user = User(
                    employee_name='مدير النظام',
                    username='admin',
                    password='admin123',
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
            print(f"❌ خطأ في إنشاء المستخدم المدير: {e}")
            db.session.rollback()
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    create_admin()
