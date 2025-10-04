import os
import json
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, send_file, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Load environment variables from a local .env if present (useful for local dev)
load_dotenv()
# Allow overriding the upload directory via environment (e.g., Render Disk mount)
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER') or os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- وثائق العميل الافتراضية ---
DOCS_REQUIRED = [
    "جواز السفر",
    "البطاقة الشخصية",
    "خطاب الدعوة",
    "القيد العائلي/الفردي",
    "كشف الحساب البنكي",
    "إثبات الوظيفة",
    "شهادة الجيش",
    "الفورم",
    "الصورة الشخصية",
    "سجل العمل لآخر 10 سنوات",
]
DOCS_OPTIONAL = [
    "شهادة التخرج",
    "شهادة التحركات",
    "عقود الملكية",
    "إثبات قيد الأولاد",
]

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-me')

# Database configuration: Prefer DATABASE_URL; fallback to provided Postgres URL
database_url = os.getenv('DATABASE_URL') or 'postgresql://ahmed_uv8c_user:Ycp5PKkvYcD3MbgK630brKay8cwr3xg7@dpg-d26fk9bipnbc73b2dvk0-a.oregon-postgres.render.com/ahmed_uv8c?sslmode=require'

# Render sometimes provides postgres://, convert to postgresql:// for SQLAlchemy
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
db = SQLAlchemy(app)

# ------------------ Models ------------------

# نموذج المستخدمين
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_name = db.Column(db.String(120), nullable=False)  # اسم الموظف
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='user')  # admin, user
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def check_password(self, password):
        return self.password == password  # في التطبيق الحقيقي، استخدم hashing
    
    def is_admin(self):
        return self.role == 'admin'
class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    visa_type = db.Column(db.String(80), nullable=False)
    total_amount = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(30), default="جاري")  # جاري/مكتمل/مرفوض/رفع مرة أخرى/لغا المعاملة
    rejection_reason = db.Column(db.String(50), nullable=True)  # رقم المرة عند الرفع مرة أخرى

    payments = db.relationship('Payment', backref='client', lazy=True, cascade="all, delete-orphan")
    documents = db.relationship('Document', backref='client', lazy=True, cascade="all, delete-orphan")
    followups = db.relationship('Followup', backref='client', lazy=True, cascade="all, delete-orphan")

    @property
    def paid_sum(self):
        return sum(p.amount for p in self.payments if p.is_paid)

    @property
    def remaining(self):
        return max(self.total_amount - self.paid_sum, 0)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    number = db.Column(db.Integer, nullable=False)  # رقم الدفعة
    amount = db.Column(db.Integer, nullable=False)
    paid_date = db.Column(db.Date, nullable=True)        # تاريخ الدفع الفعلي (لو اتدفعت)
    next_due_date = db.Column(db.Date, nullable=True)    # ميعاد الدفعة القادمة
    is_paid = db.Column(db.Boolean, default=True)        # دفعة مُسددة؟ (True) ولا مجرد جدولة قادمة؟ (False)
    payment_type = db.Column(db.String(50), nullable=True) # نوع الدفعة (مثل "دفعة" أو "رسوم سفارة")

    def status_badge(self):
        # منطق الحالة: لو مش مدفوعة وفي خلال أسبوع → "قرب الموعد"، لو عدّى الموعد → "متأخرة"
        today = date.today()
        if self.is_paid:
            return ("مدفوعة", "success")
        if self.next_due_date:
            if self.next_due_date < today:
                return ("متأخرة", "danger")
            if today <= self.next_due_date <= today + timedelta(days=7):
                return ("اقترب الموعد", "warning")
            return ("مجدولة", "secondary")
        return ("غير محدد", "secondary")

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    required = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(20), default="ناقصة")  # ناقصة/مكتملة
    file_path = db.Column(db.String(300), nullable=True)
    uploaded_at = db.Column(db.DateTime, nullable=True)
    # تخزين الملف داخل قاعدة البيانات (Postgres)
    file_bytes = db.Column(db.LargeBinary, nullable=True)
    file_name = db.Column(db.String(300), nullable=True)
    file_mime = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    
    # حقول المواعيد الجديدة
    deadline_start = db.Column(db.Date, nullable=True)  # بداية المدة
    deadline_end = db.Column(db.Date, nullable=True)    # نهاية المدة
    deadline_warning_days = db.Column(db.Integer, default=7)  # عدد أيام التنبيه المبكر
    
    def get_deadline_status(self):
        """يرجع حالة الموعد النهائي للورقة"""
        if not self.deadline_end:
            return ("بدون موعد نهائي", "secondary")
        
        today = date.today()
        days_until_deadline = (self.deadline_end - today).days
        
        if days_until_deadline < 0:
            return ("انتهت المدة", "danger")
        elif days_until_deadline <= self.deadline_warning_days:
            return ("قرب انتهاء المدة", "warning")
        elif today >= self.deadline_start:
            return ("في المدة المحددة", "info")
        else:
            return ("قبل بداية المدة", "secondary")
    
    def get_deadline_progress(self):
        """يرجع نسبة تقدم المدة (0-100)"""
        if not self.deadline_start or not self.deadline_end:
            return 0
        
        today = date.today()
        total_days = (self.deadline_end - self.deadline_start).days
        
        if total_days <= 0:
            return 100
        
        if today < self.deadline_start:
            return 0
        elif today > self.deadline_end:
            return 100
        else:
            elapsed_days = (today - self.deadline_start).days
            return min(100, max(0, (elapsed_days / total_days) * 100))

class Followup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=False)

# نموذج إدارة الملفات - العملاء المستاءين
class DisappointedClient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    contract_date = db.Column(db.Date, nullable=False)
    paid_amount = db.Column(db.Float, nullable=False)
    fingerprint_date = db.Column(db.Date, nullable=True)
    rejection_date = db.Column(db.Date, nullable=True)
    client_complaint = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default="جاري")  # جاري/تم الحل/مرفوض
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(120), nullable=True)  # اسم الموظف الذي أضاف السجل

# نموذج متابعة العميل المستاء
class ClientFollowup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('disappointed_client.id'), nullable=True)  # ربط مع العميل المستاء
    form_received_date = db.Column(db.Date, nullable=False)
    client_call_date = db.Column(db.Date, nullable=False)
    call_details = db.Column(db.Text, nullable=False)
    client_complaint = db.Column(db.Text, nullable=False)
    new_agreement = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default="جاري")  # جاري/تم/مرفوض
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(120), nullable=True)

# نموذج الشؤون القانونية
class LegalCase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    followup_id = db.Column(db.Integer, db.ForeignKey('client_followup.id'), nullable=True)  # ربط مع المتابعة
    form_received_date = db.Column(db.Date, nullable=False)
    call_date = db.Column(db.Date, nullable=False)
    call_details = db.Column(db.Text, nullable=False)
    last_agreement = db.Column(db.Text, nullable=False)
    case_type = db.Column(db.String(50), default="قضية عامة")  # نوع القضية
    status = db.Column(db.String(30), default="قيد النظر")  # قيد النظر/في المحكمة/تم الحل
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(120), nullable=True)

# نموذج العملاء المكتملين
class CompletedClient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_client_id = db.Column(db.Integer, nullable=True)  # ID العميل الأصلي من إدارة الملفات
    client_name = db.Column(db.String(120), nullable=False)
    client_phone = db.Column(db.String(50), nullable=False)
    completion_type = db.Column(db.String(50), nullable=False)  # إدارة ملفات/متابعة عميل/شؤون قانونية
    completion_date = db.Column(db.Date, nullable=False)
    completion_details = db.Column(db.Text, nullable=False)
    original_data = db.Column(db.Text, nullable=True)  # JSON string للبيانات الأصلية
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(120), nullable=True)

# نموذج العملاء المكتملين بواسطة الملفات والمتابعة (في انتظار الشئون القانونية)
class PendingLegalClient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(120), nullable=False)
    client_phone = db.Column(db.String(50), nullable=False)
    contract_date = db.Column(db.Date, nullable=True)
    paid_amount = db.Column(db.Float, nullable=True)
    fingerprint_date = db.Column(db.Date, nullable=True)
    rejection_date = db.Column(db.Date, nullable=True)
    client_complaint = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=True)
    
    # بيانات المتابعة
    form_received_date = db.Column(db.Date, nullable=True)
    client_call_date = db.Column(db.Date, nullable=True)
    call_details = db.Column(db.Text, nullable=True)
    followup_complaint = db.Column(db.Text, nullable=True)
    new_agreement = db.Column(db.Text, nullable=True)
    followup_status = db.Column(db.String(50), nullable=True)
    
    completion_date = db.Column(db.Date, nullable=False)
    completion_details = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(120), nullable=True)

# نموذج العملاء المكتملين بالكامل (جميع المراحل)
class FullyCompletedClient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(120), nullable=False)
    client_phone = db.Column(db.String(50), nullable=False)
    
    # بيانات إدارة الملفات
    contract_date = db.Column(db.Date, nullable=True)
    paid_amount = db.Column(db.Float, nullable=True)
    fingerprint_date = db.Column(db.Date, nullable=True)
    rejection_date = db.Column(db.Date, nullable=True)
    client_complaint = db.Column(db.Text, nullable=True)
    file_status = db.Column(db.String(50), nullable=True)
    file_created_by = db.Column(db.String(120), nullable=True)
    
    # بيانات المتابعة
    form_received_date = db.Column(db.Date, nullable=True)
    client_call_date = db.Column(db.Date, nullable=True)
    call_details = db.Column(db.Text, nullable=True)
    followup_complaint = db.Column(db.Text, nullable=True)
    new_agreement = db.Column(db.Text, nullable=True)
    followup_status = db.Column(db.String(50), nullable=True)
    followup_created_by = db.Column(db.String(120), nullable=True)
    
    # بيانات الشئون القانونية
    legal_form_received_date = db.Column(db.Date, nullable=True)
    legal_call_date = db.Column(db.Date, nullable=True)
    legal_call_details = db.Column(db.Text, nullable=True)
    last_agreement = db.Column(db.Text, nullable=True)
    case_type = db.Column(db.String(50), nullable=True)
    legal_status = db.Column(db.String(50), nullable=True)
    legal_created_by = db.Column(db.String(120), nullable=True)
    
    completion_date = db.Column(db.Date, nullable=False)
    completion_details = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(120), nullable=True)



# ------------------ Helpers ------------------
def seed_documents_for_client(client_id: int):
    # يضيف الوثائق الافتراضية بحالة "ناقصة" عند إنشاء العميل لأول مرة
    docs = []
    for n in DOCS_REQUIRED:
        docs.append(Document(client_id=client_id, name=n, required=True, status="ناقصة"))
    for n in DOCS_OPTIONAL:
        docs.append(Document(client_id=client_id, name=n, required=False, status="ناقصة"))
    db.session.add_all(docs)
    db.session.commit()

def next_payment_number(client: Client) -> int:
    if not client.payments:
        return 1
    return max(p.number for p in client.payments) + 1

def payment_alerts(client: Client):
    """يرجع قائمة تنبيهات تخص الدفعات: اقترب الموعد خلال أسبوع، ومتأخرة."""
    alerts = []
    today = date.today()
    for p in client.payments:
        if not p.is_paid and p.next_due_date:
            days = (p.next_due_date - today).days
            if days < 0:
                alerts.append(f"تنبيه: الدفعة رقم {p.number} متأخرة منذ {abs(days)} يوم.")
            elif 0 <= days <= 7:
                alerts.append(f"تنبيه: باقي {days} يوم على الدفعة رقم {p.number}.")
    return alerts

def document_alert(client: Client):
    """ملخص الأوراق الإجبارية الناقصة."""
    missing = [d.name for d in client.documents if d.required and d.status != "مكتملة"]
    return missing

def document_deadline_alerts(client: Client):
    """يرجع تنبيهات مواعيد الأوراق"""
    alerts = []
    today = date.today()
    
    for doc in client.documents:
        if doc.status != "مكتملة" and doc.deadline_end:
            days_until_deadline = (doc.deadline_end - today).days
            
            if days_until_deadline < 0:
                # انتهت المدة
                alerts.append({
                    'type': 'danger',
                    'message': f"⚠️ انتهت مدة {doc.name} منذ {abs(days_until_deadline)} يوم",
                    'document': doc,
                    'days': days_until_deadline
                })
            elif days_until_deadline <= doc.deadline_warning_days:
                # قرب انتهاء المدة
                alerts.append({
                    'type': 'warning',
                    'message': f"⏰ باقي {days_until_deadline} يوم على انتهاء مدة {doc.name}",
                    'document': doc,
                    'days': days_until_deadline
                })
            elif today >= doc.deadline_start:
                # في المدة المحددة
                alerts.append({
                    'type': 'info',
                    'message': f"📅 {doc.name} في المدة المحددة (تبقى {days_until_deadline} يوم)",
                    'document': doc,
                    'days': days_until_deadline
                })
    
    # ترتيب التنبيهات حسب الأولوية (انتهت المدة أولاً، ثم قرب الانتهاء)
    alerts.sort(key=lambda x: (x['type'] == 'danger', x['days']))
    return alerts

# ------------------ Routes ------------------
@app.route("/")
def index():
    """الصفحة الرئيسية - اختيار القسم"""
    # إحصائيات سريعة للصفحة الرئيسية
    total_clients = Client.query.count()
    completed_clients = Client.query.filter_by(status="مكتمل").count()
    in_progress_clients = Client.query.filter_by(status="جاري").count()
    
    return render_template("choose_section.html",
                         total_clients=total_clients,
                         completed_clients=completed_clients,
                         in_progress_clients=in_progress_clients)

@app.route("/choose_section")
def choose_section():
    """صفحة اختيار القسم"""
    # إحصائيات سريعة للصفحة الرئيسية
    total_clients = Client.query.count()
    completed_clients = Client.query.filter_by(status="مكتمل").count()
    in_progress_clients = Client.query.filter_by(status="جاري").count()
    
    return render_template("choose_section.html",
                         total_clients=total_clients,
                         completed_clients=completed_clients,
                         in_progress_clients=in_progress_clients)

@app.route("/disappointed_clients")
def disappointed_clients():
    """صفحة العملاء المستاءين"""
    # التحقق من تسجيل الدخول
    if not session.get('user_id'):
        flash("يجب تسجيل الدخول أولاً", "error")
        return redirect(url_for('login'))
    
    # جلب البيانات من الجداول الثلاثة
    disappointed_clients = DisappointedClient.query.order_by(DisappointedClient.created_at.desc()).limit(5).all()
    client_followups = ClientFollowup.query.order_by(ClientFollowup.created_at.desc()).limit(5).all()
    legal_cases = LegalCase.query.order_by(LegalCase.created_at.desc()).limit(5).all()
    
    # جلب العملاء المكتملين
    completed_clients = CompletedClient.query.order_by(CompletedClient.created_at.desc()).limit(10).all()
    
    # جلب العملاء في انتظار الشئون القانونية
    pending_legal_clients = PendingLegalClient.query.order_by(PendingLegalClient.created_at.desc()).limit(10).all()
    
    # جلب آخر 5 عملاء مكتملين بالكامل
    fully_completed_clients = FullyCompletedClient.query.order_by(FullyCompletedClient.created_at.desc()).limit(5).all()
    
    return render_template("disappointed_clients.html",
                         disappointed_clients=disappointed_clients,
                         client_followups=client_followups,
                         legal_cases=legal_cases,
                         completed_clients=completed_clients,
                         pending_legal_clients=pending_legal_clients,
                         fully_completed_clients=fully_completed_clients)

@app.route("/file_management")
def file_management():
    """صفحة إدارة الملفات للعملاء المستاءين"""
    # جلب قائمة العملاء الحاليين
    current_clients = DisappointedClient.query.order_by(DisappointedClient.created_at.desc()).all()
    return render_template("file_management.html", current_clients=current_clients)

@app.route("/add_disappointed_client", methods=["POST"])
def add_disappointed_client():
    """إضافة عميل مستاء جديد"""
    try:
        client_name = request.form.get("client_name", "").strip()
        phone = request.form.get("phone", "").strip()
        contract_date_str = request.form.get("contract_date", "").strip()
        paid_amount = float(request.form.get("paid_amount", "0") or "0")
        fingerprint_date_str = request.form.get("fingerprint_date", "").strip()
        rejection_date_str = request.form.get("rejection_date", "").strip()
        client_complaint = request.form.get("client_complaint", "").strip()
        
        if not client_name or not phone or not contract_date_str or not client_complaint:
            flash("من فضلك املأ جميع الحقول المطلوبة.", "danger")
            return redirect(url_for('file_management'))
        
        # تحويل التواريخ
        contract_date = datetime.strptime(contract_date_str, "%Y-%m-%d").date()
        fingerprint_date = datetime.strptime(fingerprint_date_str, "%Y-%m-%d").date() if fingerprint_date_str else None
        rejection_date = datetime.strptime(rejection_date_str, "%Y-%m-%d").date() if rejection_date_str else None
        
        # إنشاء العميل المستاء الجديد
        disappointed_client = DisappointedClient(
            client_name=client_name,
            phone=phone,
            contract_date=contract_date,
            paid_amount=paid_amount,
            fingerprint_date=fingerprint_date,
            rejection_date=rejection_date,
            client_complaint=client_complaint,
            created_by=session.get('employee_name', 'غير محدد')
        )
        
        db.session.add(disappointed_client)
        db.session.commit()
        
        flash("تم إضافة العميل المستاء بنجاح!", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"خطأ في إضافة العميل المستاء: {str(e)}", "danger")
    
    return redirect(url_for('disappointed_clients'))

@app.route("/client_followup")
def client_followup():
    """صفحة متابعة العميل المستاء"""
    # جلب قائمة المتابعات الحالية مع أسماء العملاء
    current_followups = ClientFollowup.query.order_by(ClientFollowup.created_at.desc()).all()
    
    # جلب أسماء العملاء للمتابعات المرتبطة
    for followup in current_followups:
        if followup.client_id:
            client = DisappointedClient.query.get(followup.client_id)
            followup.client_name = client.client_name if client else "عميل محذوف"
        else:
            followup.client_name = "غير مرتبط"
    
    return render_template("client_followup.html", current_followups=current_followups)

@app.route("/client_followup/<int:client_id>")
def client_followup_with_data(client_id):
    """صفحة متابعة العميل المستاء مع بيانات العميل"""
    # جلب بيانات العميل من جدول إدارة الملفات
    client = DisappointedClient.query.get_or_404(client_id)
    
    # جلب قائمة المتابعات الحالية لهذا العميل
    current_followups = ClientFollowup.query.filter_by(client_id=client_id).order_by(ClientFollowup.created_at.desc()).all()
    
    return render_template("client_followup.html", 
                         client=client, 
                         current_followups=current_followups,
                         show_client_data=True)

@app.route("/add_client_followup", methods=["POST"])
def add_client_followup():
    """إضافة متابعة عميل مستاء"""
    try:
        client_id = request.form.get("client_id")  # العميل المرتبط (اختياري)
        form_received_date_str = request.form.get("form_received_date", "").strip()
        client_call_date_str = request.form.get("client_call_date", "").strip()
        call_details = request.form.get("call_details", "").strip()
        client_complaint = request.form.get("client_complaint", "").strip()
        new_agreement = request.form.get("new_agreement", "").strip()
        
        if not form_received_date_str or not client_call_date_str or not call_details or not client_complaint or not new_agreement:
            flash("من فضلك املأ جميع الحقول المطلوبة.", "danger")
            if client_id:
                return redirect(url_for('client_followup_with_data', client_id=client_id))
            return redirect(url_for('client_followup'))
        
        # تحويل التواريخ
        form_received_date = datetime.strptime(form_received_date_str, "%Y-%m-%d").date()
        client_call_date = datetime.strptime(client_call_date_str, "%Y-%m-%d").date()
        
        # إنشاء المتابعة الجديدة
        followup = ClientFollowup(
            client_id=int(client_id) if client_id else None,
            form_received_date=form_received_date,
            client_call_date=client_call_date,
            call_details=call_details,
            client_complaint=client_complaint,
            new_agreement=new_agreement,
            created_by=session.get('employee_name', 'غير محدد')
        )
        
        db.session.add(followup)
        db.session.commit()
        
        flash("تم إضافة المتابعة بنجاح!", "success")
        
        # إعادة التوجيه حسب السياق
        if client_id:
            return redirect(url_for('client_profile', client_id=client_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f"خطأ في إضافة المتابعة: {str(e)}", "danger")
        if client_id:
            return redirect(url_for('client_profile', client_id=client_id))
    
    return redirect(url_for('disappointed_clients'))

@app.route("/legal_affairs")
def legal_affairs():
    """صفحة الشئون القانونية"""
    # جلب قائمة القضايا الحالية
    current_cases = LegalCase.query.order_by(LegalCase.created_at.desc()).all()
    return render_template("legal_affairs.html", current_cases=current_cases)

@app.route("/legal_affairs/<int:followup_id>")
def legal_affairs_with_client(followup_id):
    """صفحة الشئون القانونية مع بيانات العميل من إدارة الملفات ومتابعة العميل المستاء"""
    # جلب المتابعة
    followup = ClientFollowup.query.get_or_404(followup_id)
    
    # جلب بيانات العميل من إدارة الملفات إذا كان مرتبط
    file_client = None
    if followup.client_id:
        file_client = DisappointedClient.query.get(followup.client_id)
    
    return render_template("legal_affairs.html", 
                         followup=followup,
                         file_client=file_client,
                         show_client_data=True)

@app.route("/add_legal_case", methods=["POST"])
def add_legal_case():
    """إضافة قضية قانونية"""
    try:
        followup_id = request.form.get("followup_id")  # المتابعة المرتبطة (اختياري)
        form_received_date_str = request.form.get("form_received_date", "").strip()
        call_date_str = request.form.get("call_date", "").strip()
        call_details = request.form.get("call_details", "").strip()
        last_agreement = request.form.get("last_agreement", "").strip()
        
        if not form_received_date_str or not call_date_str or not call_details or not last_agreement:
            flash("من فضلك املأ جميع الحقول المطلوبة.", "danger")
            if followup_id:
                return redirect(url_for('legal_affairs_with_client', followup_id=followup_id))
            return redirect(url_for('legal_affairs'))
        
        # تحويل التواريخ
        form_received_date = datetime.strptime(form_received_date_str, "%Y-%m-%d").date()
        call_date = datetime.strptime(call_date_str, "%Y-%m-%d").date()
        
        # جلب بيانات المتابعة والعميل
        followup = None
        file_client = None
        
        if followup_id:
            followup = ClientFollowup.query.get(followup_id)
            if followup and followup.client_id:
                file_client = DisappointedClient.query.get(followup.client_id)
        
        # إنشاء سجل العميل المكتمل بالكامل
        fully_completed_client = FullyCompletedClient(
            client_name=file_client.client_name if file_client else "غير محدد",
            client_phone=file_client.phone if file_client else "غير محدد",
            
            # بيانات إدارة الملفات
            contract_date=file_client.contract_date if file_client else None,
            paid_amount=file_client.paid_amount if file_client else None,
            fingerprint_date=file_client.fingerprint_date if file_client else None,
            rejection_date=file_client.rejection_date if file_client else None,
            client_complaint=file_client.client_complaint if file_client else None,
            file_status=file_client.status if file_client else None,
            file_created_by=file_client.created_by if file_client else None,
            
            # بيانات المتابعة
            form_received_date=followup.form_received_date if followup else None,
            client_call_date=followup.client_call_date if followup else None,
            call_details=followup.call_details if followup else None,
            followup_complaint=followup.client_complaint if followup else None,
            new_agreement=followup.new_agreement if followup else None,
            followup_status=followup.status if followup else None,
            followup_created_by=followup.created_by if followup else None,
            
            # بيانات الشئون القانونية
            legal_form_received_date=form_received_date,
            legal_call_date=call_date,
            legal_call_details=call_details,
            last_agreement=last_agreement,
            case_type="قضية عامة",
            legal_status="قيد النظر",
            legal_created_by=session.get('employee_name', 'غير محدد'),
            
            completion_date=datetime.now().date(),
            completion_details=f"تم إكمال جميع المراحل للعميل {file_client.client_name if file_client else 'غير محدد'}",
            created_by=session.get('employee_name', 'غير محدد')
        )
        
        db.session.add(fully_completed_client)
        
        # حذف البيانات الأصلية
        if file_client:
            db.session.delete(file_client)
        if followup:
            db.session.delete(followup)
        
        db.session.commit()
        
        flash("تم إكمال جميع المراحل وإضافة العميل إلى قائمة العملاء المكتملين بالكامل!", "success")
        
        # إعادة التوجيه للصفحة الرئيسية بعد الحفظ
        return redirect(url_for('disappointed_clients'))
        
    except Exception as e:
        db.session.rollback()
        flash(f"خطأ في إضافة القضية القانونية: {str(e)}", "danger")
    
    return redirect(url_for('disappointed_clients'))

# Route لإضافة عميل مكتمل من إدارة الملفات
@app.route("/complete_file_management/<int:client_id>", methods=["POST"])
def complete_file_management(client_id):
    """إنهاء عميل من إدارة الملفات"""
    if not session.get('user_id'):
        flash("يجب تسجيل الدخول أولاً", "error")
        return redirect(url_for('login'))
    
    try:
        # جلب العميل من قاعدة البيانات
        client = DisappointedClient.query.get_or_404(client_id)
        
        # إنشاء سجل العميل المكتمل بالكامل (من إدارة الملفات فقط)
        fully_completed_client = FullyCompletedClient(
            client_name=client.client_name,
            client_phone=client.phone,
            
            # بيانات إدارة الملفات
            contract_date=client.contract_date,
            paid_amount=client.paid_amount,
            fingerprint_date=client.fingerprint_date,
            rejection_date=client.rejection_date,
            client_complaint=client.client_complaint,
            file_status=client.status,
            file_created_by=client.created_by,
            
            # بيانات المتابعة (فارغة)
            form_received_date=None,
            client_call_date=None,
            call_details=None,
            followup_complaint=None,
            new_agreement=None,
            followup_status=None,
            followup_created_by=None,
            
            # بيانات الشئون القانونية (فارغة)
            legal_form_received_date=None,
            legal_call_date=None,
            legal_call_details=None,
            last_agreement=None,
            case_type=None,
            legal_status=None,
            legal_created_by=None,
            
            completion_date=datetime.now().date(),
            completion_details=f"تم الانتهاء من إدارة ملفات العميل {client.client_name}",
            created_by=session.get('employee_name', 'غير محدد')
        )
        
        db.session.add(fully_completed_client)
        db.session.delete(client)  # حذف العميل من الجدول الأصلي
        db.session.commit()
        
        flash("تم إضافة العميل إلى قائمة العملاء المكتملين!", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"حدث خطأ: {str(e)}", "error")
    
    return redirect(url_for('disappointed_clients'))

# Route لإضافة عميل مكتمل من متابعة العميل
@app.route("/complete_client_followup/<int:followup_id>", methods=["POST"])
def complete_client_followup(followup_id):
    """إنهاء متابعة عميل مستاء"""
    if not session.get('user_id'):
        flash("يجب تسجيل الدخول أولاً", "error")
        return redirect(url_for('login'))
    
    try:
        # جلب المتابعة من قاعدة البيانات
        followup = ClientFollowup.query.get_or_404(followup_id)
        
        # جلب بيانات العميل الأصلي إذا كان مرتبط
        original_client_data = None
        client_name = "عميل متابعة"
        client_phone = "غير محدد"
        
        if followup.client_id:
            # جلب العميل الأصلي من جدول إدارة الملفات
            original_client = DisappointedClient.query.get(followup.client_id)
            if original_client:
                client_name = original_client.client_name
                client_phone = original_client.phone
                original_client_data = {
                    'file_management_data': {
                        'client_name': original_client.client_name,
                        'phone': original_client.phone,
                        'contract_date': original_client.contract_date.isoformat() if original_client.contract_date else None,
                        'paid_amount': original_client.paid_amount,
                        'fingerprint_date': original_client.fingerprint_date.isoformat() if original_client.fingerprint_date else None,
                        'rejection_date': original_client.rejection_date.isoformat() if original_client.rejection_date else None,
                        'client_complaint': original_client.client_complaint,
                        'status': original_client.status,
                        'created_by': original_client.created_by,
                        'created_at': original_client.created_at.isoformat() if original_client.created_at else None
                    },
                    'followup_data': {
                        'form_received_date': followup.form_received_date.isoformat() if followup.form_received_date else None,
                        'client_call_date': followup.client_call_date.isoformat() if followup.client_call_date else None,
                        'call_details': followup.call_details,
                        'client_complaint': followup.client_complaint,
                        'new_agreement': followup.new_agreement,
                        'status': followup.status,
                        'created_by': followup.created_by,
                        'created_at': followup.created_at.isoformat() if followup.created_at else None
                    }
                }
                
                # حذف العميل من جدول إدارة الملفات أيضاً
                db.session.delete(original_client)
        
        # إنشاء سجل جديد في جدول العملاء المكتملين بالكامل (إدارة الملفات + المتابعة)
        fully_completed_client = FullyCompletedClient(
            client_name=client_name,
            client_phone=client_phone,
            
            # بيانات إدارة الملفات
            contract_date=original_client.contract_date if original_client else None,
            paid_amount=original_client.paid_amount if original_client else None,
            fingerprint_date=original_client.fingerprint_date if original_client else None,
            rejection_date=original_client.rejection_date if original_client else None,
            client_complaint=original_client.client_complaint if original_client else None,
            file_status=original_client.status if original_client else None,
            file_created_by=original_client.created_by if original_client else None,
            
            # بيانات المتابعة
            form_received_date=followup.form_received_date,
            client_call_date=followup.client_call_date,
            call_details=followup.call_details,
            followup_complaint=followup.client_complaint,
            new_agreement=followup.new_agreement,
            followup_status=followup.status,
            followup_created_by=followup.created_by,
            
            # بيانات الشئون القانونية (فارغة)
            legal_form_received_date=None,
            legal_call_date=None,
            legal_call_details=None,
            last_agreement=None,
            case_type=None,
            legal_status=None,
            legal_created_by=None,
            
            completion_date=datetime.now().date(),
            completion_details=f"تم الانتهاء من إدارة الملفات ومتابعة العميل {client_name}",
            created_by=session.get('employee_name', 'غير محدد')
        )
        
        db.session.add(fully_completed_client)
        db.session.delete(followup)  # حذف المتابعة من الجدول الأصلي
        db.session.commit()
        
        flash("تم إضافة العميل إلى قائمة العملاء المكتملين بالكامل!", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"حدث خطأ: {str(e)}", "error")
    
    return redirect(url_for('disappointed_clients'))

# Route لإضافة عميل مكتمل من الشؤون القانونية
@app.route("/complete_legal_case/<int:case_id>", methods=["POST"])
def complete_legal_case(case_id):
    """إنهاء قضية قانونية"""
    if not session.get('user_id'):
        flash("يجب تسجيل الدخول أولاً", "error")
        return redirect(url_for('login'))
    
    try:
        # جلب القضية من قاعدة البيانات
        case = LegalCase.query.get_or_404(case_id)
        
        # البحث عن المتابعة المرتبطة بهذه القضية (إذا كانت موجودة)
        followup = None
        file_client = None
        
        # محاولة العثور على المتابعة المرتبطة
        if hasattr(case, 'followup_id') and case.followup_id:
            followup = ClientFollowup.query.get(case.followup_id)
            if followup and followup.client_id:
                file_client = DisappointedClient.query.get(followup.client_id)
        
        # إنشاء بيانات العميل المكتمل
        client_name = "عميل قضية قانونية"
        client_phone = "غير محدد"
        original_data = {
            'legal_data': {
                'form_received_date': case.form_received_date.isoformat() if case.form_received_date else None,
                'call_date': case.call_date.isoformat() if case.call_date else None,
                'call_details': case.call_details,
                'last_agreement': case.last_agreement,
                'case_type': case.case_type,
                'status': case.status,
                'created_by': case.created_by,
                'created_at': case.created_at.isoformat() if case.created_at else None
            }
        }
        
        # إضافة بيانات المتابعة إذا كانت موجودة
        if followup:
            original_data['followup_data'] = {
                'form_received_date': followup.form_received_date.isoformat() if followup.form_received_date else None,
                'client_call_date': followup.client_call_date.isoformat() if followup.client_call_date else None,
                'call_details': followup.call_details,
                'client_complaint': followup.client_complaint,
                'new_agreement': followup.new_agreement,
                'status': followup.status,
                'created_by': followup.created_by,
                'created_at': followup.created_at.isoformat() if followup.created_at else None
            }
        
        # إضافة بيانات إدارة الملفات إذا كانت موجودة
        original_client_id = None
        if file_client:
            client_name = file_client.client_name
            client_phone = file_client.phone
            original_client_id = file_client.id  # حفظ ID قبل الحذف
            original_data['file_management_data'] = {
                'client_name': file_client.client_name,
                'phone': file_client.phone,
                'contract_date': file_client.contract_date.isoformat() if file_client.contract_date else None,
                'paid_amount': file_client.paid_amount,
                'fingerprint_date': file_client.fingerprint_date.isoformat() if file_client.fingerprint_date else None,
                'rejection_date': file_client.rejection_date.isoformat() if file_client.rejection_date else None,
                'client_complaint': file_client.client_complaint,
                'status': file_client.status,
                'created_by': file_client.created_by,
                'created_at': file_client.created_at.isoformat() if file_client.created_at else None
            }
            
            # حذف العميل من جدول إدارة الملفات
            db.session.delete(file_client)
        
        # حذف المتابعة إذا كانت موجودة
        if followup:
            db.session.delete(followup)
        
        # البحث عن سجل موجود في جدول العملاء المكتملين
        existing_completed = CompletedClient.query.filter_by(
            original_client_id=original_client_id
        ).first()
        
        if existing_completed:
            # تحديث السجل الموجود
            existing_completed.completion_type = "شؤون قانونية"
            existing_completed.completion_date = datetime.now().date()
            existing_completed.completion_details = f"تم الانتهاء من القضية القانونية {client_name}"
            existing_completed.original_data = json.dumps(original_data, ensure_ascii=False)
        else:
            # إنشاء سجل جديد إذا لم يوجد
            completed_client = CompletedClient(
                original_client_id=original_client_id,
                client_name=client_name,
                client_phone=client_phone,
                completion_type="شؤون قانونية",
                completion_date=datetime.now().date(),
                completion_details=f"تم الانتهاء من القضية القانونية {client_name}",
                original_data=json.dumps(original_data, ensure_ascii=False),
                created_by=session.get('employee_name', 'غير محدد')
            )
            db.session.add(completed_client)
        db.session.delete(case)  # حذف القضية من الجدول الأصلي
        db.session.commit()
        
        flash("تم إضافة العميل والقضية القانونية إلى قائمة العملاء المكتملين!", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"حدث خطأ: {str(e)}", "error")
    
    return redirect(url_for('disappointed_clients'))

@app.route("/completed_client_details/<int:client_id>")
def completed_client_details(client_id):
    """عرض تفاصيل العميل المكتمل"""
    # جلب بيانات العميل المكتمل
    completed_client = CompletedClient.query.get_or_404(client_id)
    
    # تحليل البيانات الأصلية
    original_data = None
    if completed_client.original_data:
        try:
            original_data = json.loads(completed_client.original_data)
        except Exception as e:
            # Error parsing original_data - skip debug to avoid encoding issues
            original_data = None
    
    # إذا لم تكن البيانات منظمة، نحاول عرض البيانات القديمة
    if not original_data:
        # محاولة عرض البيانات القديمة
        all_data = {
            'file_management_data': None,
            'followup_data': None,
            'legal_data': None
        }
        
        # البحث عن العملاء المرتبطين بنفس الاسم والهاتف للبيانات القديمة
        if completed_client.client_name and completed_client.client_phone:
            related_old_clients = CompletedClient.query.filter(
                CompletedClient.client_name == completed_client.client_name,
                CompletedClient.client_phone == completed_client.client_phone,
                CompletedClient.id != client_id
            ).all()
            
            # جمع البيانات من جميع العملاء المرتبطين
            for old_client in related_old_clients:
                if old_client.original_data:
                    try:
                        old_data = json.loads(old_client.original_data)
                        
                        # إذا كان نوع الإنجاز "إدارة ملفات"
                        if old_client.completion_type == "إدارة ملفات" and not all_data['file_management_data']:
                            all_data['file_management_data'] = {
                                'client_name': old_client.client_name,
                                'phone': old_client.client_phone,
                                'contract_date': old_data.get('contract_date'),
                                'paid_amount': old_data.get('paid_amount'),
                                'fingerprint_date': old_data.get('fingerprint_date'),
                                'rejection_date': old_data.get('rejection_date'),
                                'client_complaint': old_data.get('client_complaint'),
                                'status': old_data.get('status'),
                                'created_by': old_client.created_by,
                                'created_at': old_client.created_at.isoformat() if old_client.created_at else None
                            }
                        
                        # إذا كان نوع الإنجاز "متابعة عميل مستاء"
                        elif old_client.completion_type == "متابعة عميل مستاء" and not all_data['followup_data']:
                            if 'followup_data' in old_data:
                                all_data['followup_data'] = old_data['followup_data']
                            elif 'file_management_data' in old_data:
                                all_data['file_management_data'] = old_data['file_management_data']
                                all_data['followup_data'] = old_data.get('followup_data')
                        
                        # إذا كان نوع الإنجاز "شؤون قانونية"
                        elif old_client.completion_type == "شؤون قانونية" and not all_data['legal_data']:
                            if 'legal_data' in old_data:
                                all_data['legal_data'] = old_data['legal_data']
                            if 'followup_data' in old_data and not all_data['followup_data']:
                                all_data['followup_data'] = old_data['followup_data']
                            if 'file_management_data' in old_data and not all_data['file_management_data']:
                                all_data['file_management_data'] = old_data['file_management_data']
                    except:
                        continue
        
        # إذا لم نجد بيانات مرتبطة، نحاول استخراج البيانات من العميل الحالي
        if not any([all_data['file_management_data'], all_data['followup_data'], all_data['legal_data']]):
            try:
                old_data = json.loads(completed_client.original_data) if completed_client.original_data else {}
                
                # إذا كان نوع الإنجاز "إدارة ملفات"
                if completed_client.completion_type == "إدارة ملفات":
                    all_data['file_management_data'] = {
                        'client_name': completed_client.client_name,
                        'phone': completed_client.client_phone,
                        'contract_date': old_data.get('contract_date'),
                        'paid_amount': old_data.get('paid_amount'),
                        'fingerprint_date': old_data.get('fingerprint_date'),
                        'rejection_date': old_data.get('rejection_date'),
                        'client_complaint': old_data.get('client_complaint'),
                        'status': old_data.get('status'),
                        'created_by': completed_client.created_by,
                        'created_at': completed_client.created_at.isoformat() if completed_client.created_at else None
                    }
                
                # إذا كان نوع الإنجاز "متابعة عميل مستاء"
                elif completed_client.completion_type == "متابعة عميل مستاء":
                    if 'followup_data' in old_data:
                        all_data['followup_data'] = old_data['followup_data']
                    elif 'file_management_data' in old_data:
                        all_data['file_management_data'] = old_data['file_management_data']
                        all_data['followup_data'] = old_data.get('followup_data')
                
                # إذا كان نوع الإنجاز "شؤون قانونية"
                elif completed_client.completion_type == "شؤون قانونية":
                    if 'legal_data' in old_data:
                        all_data['legal_data'] = old_data['legal_data']
                    if 'followup_data' in old_data:
                        all_data['followup_data'] = old_data['followup_data']
                    if 'file_management_data' in old_data:
                        all_data['file_management_data'] = old_data['file_management_data']
            except:
                pass
    else:
        # البيانات الجديدة المنظمة
        all_data = {
            'file_management_data': original_data.get('file_management_data'),
            'followup_data': original_data.get('followup_data'),
            'legal_data': original_data.get('legal_data')
        }
        
        # جلب جميع العملاء المكتملين المرتبطين بنفس العميل الأصلي أو بنفس اسم العميل
        related_clients = []
        if completed_client.original_client_id:
            # البحث بنفس original_client_id
            related_clients.extend(CompletedClient.query.filter_by(
                original_client_id=completed_client.original_client_id
            ).filter(CompletedClient.id != client_id).all())
        
        # البحث أيضاً بنفس اسم العميل وهاتف العميل للعملاء الذين لا يملكون original_client_id
        if completed_client.client_name and completed_client.client_phone:
            same_name_clients = CompletedClient.query.filter(
                CompletedClient.client_name == completed_client.client_name,
                CompletedClient.client_phone == completed_client.client_phone,
                CompletedClient.id != client_id,
                CompletedClient.original_client_id.is_(None)  # فقط العملاء الذين لا يملكون original_client_id
            ).all()
            related_clients.extend(same_name_clients)
        
        # إضافة بيانات من العملاء المرتبطين
        for related_client in related_clients:
            if related_client.original_data:
                try:
                    related_data = json.loads(related_client.original_data)
                    if 'file_management_data' in related_data and not all_data['file_management_data']:
                        all_data['file_management_data'] = related_data['file_management_data']
                    if 'followup_data' in related_data and not all_data['followup_data']:
                        all_data['followup_data'] = related_data['followup_data']
                    if 'legal_data' in related_data and not all_data['legal_data']:
                        all_data['legal_data'] = related_data['legal_data']
                except:
                    continue
    
    # Debug info
    print(f"Debug - Client ID: {client_id}")
    print(f"Debug - Has file_data: {bool(all_data.get('file_management_data'))}")
    print(f"Debug - Has followup_data: {bool(all_data.get('followup_data'))}")
    print(f"Debug - Has legal_data: {bool(all_data.get('legal_data'))}")
    print(f"Debug - Original client ID: {completed_client.original_client_id}")
    
    try:
        return render_template("completed_client_details.html", 
                             client=completed_client,
                             original_data=all_data,
                             related_clients=[])
    except Exception as e:
        # في حالة حدوث خطأ في العرض، نعيد البيانات الأساسية فقط
        basic_data = {
            'file_management_data': None,
            'followup_data': None,
            'legal_data': None
        }
        return render_template("completed_client_details.html", 
                             client=completed_client,
                             original_data=basic_data,
                             related_clients=[])

@app.route("/pending_legal_client_details/<int:client_id>")
def pending_legal_client_details(client_id):
    """عرض تفاصيل العميل في انتظار الشئون القانونية"""
    pending_client = PendingLegalClient.query.get_or_404(client_id)
    
    return render_template("pending_legal_client_details.html", client=pending_client)

@app.route("/fully_completed_client_details/<int:client_id>")
def fully_completed_client_details(client_id):
    """عرض تفاصيل العميل المكتمل بالكامل"""
    fully_client = FullyCompletedClient.query.get_or_404(client_id)
    
    return render_template("fully_completed_client_details.html", client=fully_client)

@app.route("/all_fully_completed_clients")
def all_fully_completed_clients():
    """عرض جميع العملاء المكتملين بالكامل"""
    # جلب جميع العملاء المكتملين بالكامل
    all_clients = FullyCompletedClient.query.order_by(FullyCompletedClient.created_at.desc()).all()
    
    return render_template("all_fully_completed_clients.html", clients=all_clients)

@app.route("/client_profile/<int:client_id>")
def client_profile(client_id):
    """عرض بروفايل العميل الكامل - من إدارة الملفات ومتابعة العميل المستاء"""
    # جلب بيانات العميل من إدارة الملفات
    file_client = DisappointedClient.query.get_or_404(client_id)
    
    # جلب جميع المتابعات المرتبطة بهذا العميل
    followups = ClientFollowup.query.filter_by(client_id=client_id).order_by(ClientFollowup.created_at.desc()).all()
    
    return render_template("client_profile.html", 
                         file_client=file_client,
                         followups=followups,
                         total_followups=len(followups))

# ------------------ Authentication Routes ------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    """صفحة تسجيل الدخول"""
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password) and user.is_active:
            # حفظ معلومات المستخدم في session
            session['user_id'] = user.id
            session['username'] = user.username
            session['employee_name'] = user.employee_name
            session['role'] = user.role
            flash(f"مرحباً {user.employee_name}!", "success")
            return redirect(url_for('disappointed_clients'))
        else:
            flash("اسم المستخدم أو كلمة المرور غير صحيحة!", "danger")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    """تسجيل الخروج"""
    session.clear()
    flash("تم تسجيل الخروج بنجاح!", "info")
    return redirect(url_for('choose_section'))

@app.route("/user_management")
def user_management():
    """صفحة إدارة المستخدمين"""
    # عرض جميع المستخدمين
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("user_management.html", users=users)

@app.route("/add_user", methods=["POST"])
def add_user():
    """إضافة مستخدم جديد"""
    employee_name = request.form.get('employee_name')
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role')
    is_active = request.form.get('is_active') == 'true'
    
    # التحقق من وجود المستخدم
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash("اسم المستخدم موجود بالفعل!", "danger")
        return redirect(url_for('user_management'))
    
    # إنشاء مستخدم جديد
    new_user = User(
        employee_name=employee_name,
        username=username,
        password=password,  # في التطبيق الحقيقي، استخدم hashing
        role=role,
        is_active=is_active
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    flash("تم إضافة المستخدم بنجاح!", "success")
    return redirect(url_for('user_management'))

@app.route("/toggle_user_status/<int:user_id>", methods=["POST"])
def toggle_user_status(user_id):
    """تبديل حالة المستخدم"""
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    
    status = "تفعيل" if user.is_active else "إلغاء تفعيل"
    flash(f"تم {status} المستخدم بنجاح!", "success")
    return redirect(url_for('user_management'))

@app.route("/delete_user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    """حذف مستخدم"""
    user = User.query.get_or_404(user_id)
    
    # منع حذف الأدمن
    if user.role == 'admin':
        flash("لا يمكن حذف المستخدم المدير!", "danger")
        return redirect(url_for('user_management'))
    
    db.session.delete(user)
    db.session.commit()
    
    flash("تم حذف المستخدم بنجاح!", "success")
    return redirect(url_for('user_management'))

@app.route("/dashboard")
def dashboard():
    # البحث عن العميل
    search_query = request.args.get('search', '').strip()
    search_results = []
    
    # التحقق من عرض جميع العملاء
    show_all = request.args.get('show_all', 'false').lower() == 'true'
    
    if search_query:
        # البحث بالاسم أو رقم الهاتف
        search_results = Client.query.filter(
            db.or_(
                Client.name.ilike(f'%{search_query}%'),
                Client.phone.ilike(f'%{search_query}%')
            )
        ).all()
    
    # إحصائيات العملاء
    total_clients = Client.query.count()
    completed_clients = Client.query.filter_by(status="مكتمل").count()
    in_progress_clients = Client.query.filter_by(status="جاري").count()
    rejected_clients = Client.query.filter_by(status="مرفوض").count()
    resubmit_clients = Client.query.filter_by(status="رفع مرة أخرى").count()
    cancelled_clients = Client.query.filter_by(status="لغا المعاملة").count()
    incomplete_clients = total_clients - completed_clients
    
    # العملاء الجدد في آخر 30 يوم
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    new_clients = Client.query.filter(Client.created_at >= thirty_days_ago).count()
    

    
    # تنبيهات الدفعات القادمة
    today = date.today()
    upcoming_payments = []
    
    # الدفعات التي اقترب موعدها (خلال أسبوع)
    payments_due_soon = Payment.query.filter(
        Payment.is_paid == False,
        Payment.next_due_date >= today,
        Payment.next_due_date <= today + timedelta(days=7)
    ).all()
    
    for payment in payments_due_soon:
        client = Client.query.get(payment.client_id)
        days_left = (payment.next_due_date - today).days
        upcoming_payments.append({
            'client_name': client.name,
            'client_id': client.id,
            'payment_number': payment.number,
            'amount': payment.amount,
            'due_date': payment.next_due_date,
            'days_left': days_left,
            'type': 'قريب'
        })
    
    # الدفعات المتأخرة
    overdue_payments = Payment.query.filter(
        Payment.is_paid == False,
        Payment.next_due_date < today
    ).all()
    
    for payment in overdue_payments:
        client = Client.query.get(payment.client_id)
        days_overdue = (today - payment.next_due_date).days
        upcoming_payments.append({
            'client_name': client.name,
            'client_id': client.id,
            'payment_number': payment.number,
            'amount': payment.amount,
            'due_date': payment.next_due_date,
            'days_left': -days_overdue,
            'type': 'متأخر'
        })
    
    # ترتيب التنبيهات (المتأخرة أولاً، ثم القريبة)
    upcoming_payments.sort(key=lambda x: (x['type'] == 'متأخر', x['days_left']))
    
    # العملاء الذين يحتاجون متابعة (أوراق ناقصة أو دفعات متأخرة)
    clients_needing_attention = []
    
    # جلب العملاء - إما آخر 5 أو جميع العملاء
    if show_all:
        all_clients = Client.query.order_by(Client.created_at.desc()).all()
        clients_to_show = all_clients
    else:
        all_clients = Client.query.order_by(Client.created_at.desc()).all()
        clients_to_show = all_clients[:5]  # عرض آخر 5 عملاء فقط
    
    for client in all_clients:
        missing_docs = len([d for d in client.documents if d.required and d.status != "مكتملة"])
        overdue_payments_count = len([p for p in client.payments if not p.is_paid and p.next_due_date and p.next_due_date < today])
        
        if missing_docs > 0 or overdue_payments_count > 0:
            clients_needing_attention.append({
                'id': client.id,
                'name': client.name,
                'missing_docs': missing_docs,
                'overdue_payments': overdue_payments_count,
                'status': client.status
            })
    
    return render_template("dashboard.html",
                         search_query=search_query,
                         search_results=search_results,
                         total_clients=total_clients,
                         completed_clients=completed_clients,
                         in_progress_clients=in_progress_clients,
                         rejected_clients=rejected_clients,
                         resubmit_clients=resubmit_clients,
                         cancelled_clients=cancelled_clients,
                         new_clients=new_clients,
                         upcoming_payments=upcoming_payments,
                         clients_needing_attention=clients_needing_attention,
                         all_clients=clients_to_show,
                         show_all=show_all)

@app.route("/debug/db")
def debug_db():
    try:
        engine_name = db.engine.name
        engine_url = str(db.engine.url)
        clients_count = Client.query.count()
        payments_count = Payment.query.count()
        documents_count = Document.query.count()
        followups_count = Followup.query.count()
        return {
            "engine": engine_name,
            "url": engine_url,
            "counts": {
                "client": clients_count,
                "payment": payments_count,
                "document": documents_count,
                "followup": followups_count,
            }
        }
    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/contracts/new", methods=["GET", "POST"])
def add_contract():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        visa_type = request.form.get("visa_type", "").strip()
        try:
            total_amount = int(request.form.get("total_amount", "0") or "0")
        except:
            total_amount = 0

        if not name or not phone or not visa_type or total_amount <= 0:
            flash("من فضلك املأ كل الحقول وأدخل مبلغ كلي صحيح.", "danger")
            return redirect(url_for("add_contract"))

        client = Client(name=name, phone=phone, visa_type=visa_type, total_amount=total_amount)
        db.session.add(client)
        db.session.commit()

        # إضافة الوثائق الافتراضية
        seed_documents_for_client(client.id)

        return redirect(url_for("client_detail", client_id=client.id))

    return render_template("add_contract.html")

@app.route("/client/<int:client_id>")
def client_detail(client_id):
    client = Client.query.get_or_404(client_id)

    # تنبيهات الدفعات + قائمة الأوراق الناقصة (إجباري)
    pay_alerts = payment_alerts(client)
    missing_required_docs = document_alert(client)
    
    # تنبيهات مواعيد الأوراق
    deadline_alerts = document_deadline_alerts(client)

    # تجميع الدفعات: المدفوعة + المجدولة (غير مدفوعة)
    payments_sorted = sorted(client.payments, key=lambda x: (x.is_paid is False, x.number))

    # تقسيم المستندات لجدولين
    docs_required = [d for d in client.documents if d.required]
    docs_optional = [d for d in client.documents if not d.required]

    # المتابعات (الأحدث أولاً)
    follows = sorted(client.followups, key=lambda f: f.date, reverse=True)

    return render_template(
        "client_detail.html",
        client=client,
        payments=payments_sorted,
        docs_required=docs_required,
        docs_optional=docs_optional,
        follows=follows,
        pay_alerts=pay_alerts,
        missing_required_docs=missing_required_docs,
        deadline_alerts=deadline_alerts
    )

# -------- دفعات --------
@app.route("/client/<int:client_id>/add_payment", methods=["POST"])
def add_payment(client_id):
    client = Client.query.get_or_404(client_id)
    amount = int(request.form.get("amount") or 0)
    paid_now = request.form.get("paid_now") == "on"
    paid_date_str = request.form.get("paid_date")  # اختياري
    next_due_date_str = request.form.get("next_due_date")  # اختياري

    if amount <= 0:
        flash("أدخل مبلغ دفعة صحيح.", "danger")
        return redirect(url_for("client_detail", client_id=client_id))

    number = next_payment_number(client)
    paid_date = datetime.strptime(paid_date_str, "%Y-%m-%d").date() if paid_date_str else (date.today() if paid_now else None)
    next_due_date = datetime.strptime(next_due_date_str, "%Y-%m-%d").date() if next_due_date_str else None

    payment_type = request.form.get("payment_type", "دفعة")
    payment = Payment(
        client_id=client.id,
        number=number,
        amount=amount,
        paid_date=paid_date,
        next_due_date=next_due_date,
        is_paid=bool(paid_date is not None),
        payment_type=payment_type
    )
    db.session.add(payment)
    db.session.commit()
    flash("تم إضافة حركة الدفعة.", "success")
    return redirect(url_for("client_detail", client_id=client_id))



@app.route("/client/<int:client_id>/mark_payment_paid/<int:payment_id>", methods=["POST"])
def mark_payment_paid(client_id, payment_id):
    client = Client.query.get_or_404(client_id)
    payment = Payment.query.filter_by(id=payment_id, client_id=client_id).first_or_404()
    if not payment.is_paid:
        payment.is_paid = True
        payment.paid_date = date.today()
        db.session.commit()
        flash("تم تسجيل الدفعة كمدفوعة وإزالة التنبيه.", "success")
    return redirect(url_for("client_detail", client_id=client_id))

@app.route("/client/<int:client_id>/delete_payment/<int:payment_id>", methods=["POST"])
def delete_payment(client_id, payment_id):
    client = Client.query.get_or_404(client_id)
    payment = Payment.query.filter_by(id=payment_id, client_id=client_id).first_or_404()
    
    # حذف الدفعة
    db.session.delete(payment)
    db.session.commit()
    flash("تم حذف الدفعة بنجاح.", "success")
    return redirect(url_for("client_detail", client_id=client_id))

# -------- مستندات --------
@app.route("/client/<int:client_id>/upload_document/<int:doc_id>", methods=["POST"])
def upload_document(client_id, doc_id):
    client = Client.query.get_or_404(client_id)
    doc = Document.query.filter_by(id=doc_id, client_id=client_id).first_or_404()
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("اختر ملفًا للرفع.", "danger")
        return redirect(url_for("client_detail", client_id=client_id))

    # حفظ اسم الملف الأصلي
    original_filename = secure_filename(file.filename)
    # قراءة المحتوى وتحديد النوع والحجم
    data = file.read()
    import mimetypes
    guessed_mime, _ = mimetypes.guess_type(original_filename)
    file_mime = file.mimetype or guessed_mime or 'application/octet-stream'
    file_size = len(data) if data is not None else 0

    # حفظ داخل قاعدة البيانات
    doc.file_bytes = data
    doc.file_name = original_filename
    doc.file_mime = file_mime
    doc.file_size = file_size
    # لم نعد نعتمد على التخزين على القرص
    doc.file_path = None
    doc.status = "مكتملة"
    doc.uploaded_at = datetime.utcnow()
    
    # إزالة المواعيد النهائية عند رفع الوثيقة
    doc.deadline_start = None
    doc.deadline_end = None
    doc.deadline_warning_days = 7
    
    db.session.commit()
    
    # رسالة نجاح مع نوع الملف
    file_ext = os.path.splitext(original_filename)[1].lower() if '.' in original_filename else ''
    file_type = "PDF" if file_ext == '.pdf' else "ملف"
    flash(f"تم رفع {file_type} '{original_filename}' وإزالة المواعيد النهائية بنجاح.", "success")
    return redirect(url_for("client_detail", client_id=client_id))

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    # محاولة إيجاد الوثيقة في قاعدة البيانات عبر file_path القديم
    doc = Document.query.filter_by(file_path=filename).first()
    if doc and doc.file_bytes:
        import io
        mime_type = doc.file_mime or 'application/octet-stream'
        return send_file(io.BytesIO(doc.file_bytes), mimetype=mime_type, as_attachment=False, download_name=doc.file_name or filename)
    
    # fallback: من القرص إذا لم تكن موجودة في قاعدة البيانات
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return "الملف غير موجود", 404
    import mimetypes
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type == 'application/pdf':
        return send_file(file_path, mimetype='application/pdf', as_attachment=False)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=False)

@app.route("/view_pdf/<path:filename>")
def view_pdf(filename):
    """عرض ملف PDF في المتصفح مع واجهة محسنة"""
    # محاولة القراءة من قاعدة البيانات أولاً
    doc = Document.query.filter_by(file_path=filename).first()
    if doc and doc.file_bytes:
        import io
        response = send_file(io.BytesIO(doc.file_bytes), mimetype='application/pdf', as_attachment=False, download_name=doc.file_name or filename)
        response.headers['Content-Disposition'] = 'inline; filename="' + (doc.file_name or filename) + '"'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    
    # fallback للقرص
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return "الملف غير موجود", 404
    if not filename.lower().endswith('.pdf'):
        return "هذا الملف ليس PDF", 400
    response = send_file(file_path, mimetype='application/pdf', as_attachment=False)
    response.headers['Content-Disposition'] = 'inline; filename="' + filename + '"'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route("/view_pdf_page/<path:filename>")
def view_pdf_page(filename):
    """عرض صفحة مخصصة لملف PDF"""
    # لو الملف موجود في قاعدة البيانات نسمح بعرض الصفحة أيضاً
    doc = Document.query.filter_by(file_path=filename).first()
    if doc and doc.file_bytes:
        if not (doc.file_name or filename).lower().endswith('.pdf'):
            return "هذا الملف ليس PDF", 400
        return render_template("view_pdf.html", filename=filename)
    
    # fallback للقرص
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return "الملف غير موجود", 404
    if not filename.lower().endswith('.pdf'):
        return "هذا الملف ليس PDF", 400
    return render_template("view_pdf.html", filename=filename)

@app.route("/download_pdf/<path:filename>")
def download_pdf(filename):
    """تحميل ملف PDF"""
    doc = Document.query.filter_by(file_path=filename).first()
    if doc and doc.file_bytes:
        import io
        return send_file(io.BytesIO(doc.file_bytes), mimetype='application/pdf', as_attachment=True, download_name=doc.file_name or filename)
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return "الملف غير موجود", 404
    if not filename.lower().endswith('.pdf'):
        return "هذا الملف ليس PDF", 400
    return send_file(file_path, mimetype='application/pdf', as_attachment=True, download_name=filename)

@app.route("/document/<int:doc_id>/view")
def view_document_by_id(doc_id: int):
    """عرض ملف المخزن في قاعدة البيانات مباشرةً باستخدام معرّف الوثيقة"""
    doc = Document.query.get_or_404(doc_id)
    if not doc.file_bytes:
        return "لا يوجد ملف مرفوع لهذه الوثيقة", 404
    import io
    mime = doc.file_mime or 'application/octet-stream'
    response = send_file(io.BytesIO(doc.file_bytes), mimetype=mime, as_attachment=False, download_name=doc.file_name or f"document_{doc.id}")
    response.headers['Content-Disposition'] = 'inline; filename="' + (doc.file_name or f"document_{doc.id}") + '"'
    return response

@app.route("/document/<int:doc_id>/download")
def download_document_by_id(doc_id: int):
    """تحميل ملف المخزن في قاعدة البيانات مباشرةً باستخدام معرّف الوثيقة"""
    doc = Document.query.get_or_404(doc_id)
    if not doc.file_bytes:
        return "لا يوجد ملف مرفوع لهذه الوثيقة", 404
    import io
    mime = doc.file_mime or 'application/octet-stream'
    return send_file(io.BytesIO(doc.file_bytes), mimetype=mime, as_attachment=True, download_name=doc.file_name or f"document_{doc.id}")

@app.route("/view_image/<path:filename>")
def view_image(filename):
    """عرض الصور في المتصفح مع واجهة محسنة"""
    # من قاعدة البيانات أولاً
    doc = Document.query.filter_by(file_path=filename).first()
    if doc and doc.file_bytes:
        import io
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        fname = (doc.file_name or filename).lower()
        if not any(fname.endswith(ext) for ext in image_extensions):
            return "هذا الملف ليس صورة", 400
        mime_type = doc.file_mime or 'application/octet-stream'
        response = send_file(io.BytesIO(doc.file_bytes), mimetype=mime_type, as_attachment=False, download_name=doc.file_name or filename)
        response.headers['Content-Disposition'] = 'inline; filename="' + (doc.file_name or filename) + '"'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    
    # fallback للقرص
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return "الملف غير موجود", 404
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    if not any(filename.lower().endswith(ext) for ext in image_extensions):
        return "هذا الملف ليس صورة", 400
    import mimetypes
    mime_type, _ = mimetypes.guess_type(file_path)
    response = send_file(file_path, mimetype=mime_type, as_attachment=False)
    response.headers['Content-Disposition'] = 'inline; filename="' + filename + '"'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route("/view_document/<path:filename>")
def view_document(filename):
    """عرض ملفات Word و Excel في المتصفح مع واجهة محسنة"""
    # من قاعدة البيانات أولاً
    doc = Document.query.filter_by(file_path=filename).first()
    if doc and doc.file_bytes:
        import io
        word_extensions = ['.doc', '.docx']
        excel_extensions = ['.xls', '.xlsx']
        fname = (doc.file_name or filename).lower()
        if fname.endswith(tuple(word_extensions)):
            mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif fname.endswith(tuple(excel_extensions)):
            mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:
            return "نوع الملف غير مدعوم", 400
        response = send_file(io.BytesIO(doc.file_bytes), mimetype=mime_type, as_attachment=False, download_name=doc.file_name or filename)
        response.headers['Content-Disposition'] = 'inline; filename="' + (doc.file_name or filename) + '"'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    
    # fallback للقرص
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return "الملف غير موجود", 404
    word_extensions = ['.doc', '.docx']
    excel_extensions = ['.xls', '.xlsx']
    if filename.lower().endswith(tuple(word_extensions)):
        mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        file_type = 'Word'
    elif filename.lower().endswith(tuple(excel_extensions)):
        mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        file_type = 'Excel'
    else:
        return "نوع الملف غير مدعوم", 400
    response = send_file(file_path, mimetype=mime_type, as_attachment=False)
    response.headers['Content-Disposition'] = 'inline; filename="' + filename + '"'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route("/client/<int:client_id>/add_custom_document", methods=["POST"])
def add_custom_document(client_id):
    """إضافة وثيقة مخصصة للعميل"""
    client = Client.query.get_or_404(client_id)
    
    doc_name = request.form.get("doc_name", "").strip()
    is_required = request.form.get("is_required") == "on"
    
    if not doc_name:
        flash("اسم الوثيقة مطلوب.", "danger")
        return redirect(url_for("client_detail", client_id=client_id))
    
    # التحقق من عدم وجود وثيقة بنفس الاسم للعميل
    existing_doc = Document.query.filter_by(
        client_id=client_id, 
        name=doc_name
    ).first()
    
    if existing_doc:
        flash("هذه الوثيقة موجودة بالفعل للعميل.", "warning")
        return redirect(url_for("client_detail", client_id=client_id))
    
    # إنشاء الوثيقة الجديدة
    new_doc = Document(
        client_id=client_id,
        name=doc_name,
        required=is_required,
        status="ناقصة"
    )
    
    db.session.add(new_doc)
    db.session.commit()
    
    doc_type = "إجبارية" if is_required else "اختيارية"
    flash(f"تم إضافة الوثيقة '{doc_name}' كوثيقة {doc_type} بنجاح.", "success")
    
    return redirect(url_for("client_detail", client_id=client_id))

@app.route("/client/<int:client_id>/set_document_deadline/<int:doc_id>", methods=["POST"])
def set_document_deadline(client_id, doc_id):
    """تعيين موعد نهائي للوثيقة"""
    client = Client.query.get_or_404(client_id)
    doc = Document.query.filter_by(id=doc_id, client_id=client_id).first_or_404()
    
    deadline_start = request.form.get("deadline_start")
    deadline_end = request.form.get("deadline_end")
    warning_days = request.form.get("warning_days", "7")
    
    if not deadline_start or not deadline_end:
        flash("بداية ونهاية المدة مطلوبتان.", "danger")
        return redirect(url_for("client_detail", client_id=client_id))
    
    try:
        start_date = datetime.strptime(deadline_start, "%Y-%m-%d").date()
        end_date = datetime.strptime(deadline_end, "%Y-%m-%d").date()
        warning_days_int = int(warning_days)
        
        if start_date >= end_date:
            flash("تاريخ بداية المدة يجب أن يكون قبل تاريخ نهاية المدة.", "danger")
            return redirect(url_for("client_detail", client_id=client_id))
        
        if warning_days_int < 1 or warning_days_int > 30:
            flash("أيام التنبيه يجب أن تكون بين 1 و 30 يوم.", "danger")
            return redirect(url_for("client_detail", client_id=client_id))
        
        # تحديث المواعيد
        doc.deadline_start = start_date
        doc.deadline_end = end_date
        doc.deadline_warning_days = warning_days_int
        
        db.session.commit()
        
        flash(f"تم تعيين موعد نهائي للوثيقة '{doc.name}' بنجاح.", "success")
        
    except ValueError:
        flash("تاريخ غير صحيح.", "danger")
    
    return redirect(url_for("client_detail", client_id=client_id))

@app.route("/client/<int:client_id>/remove_document_deadline/<int:doc_id>", methods=["POST"])
def remove_document_deadline(client_id, doc_id):
    """إزالة موعد نهائي من الوثيقة"""
    client = Client.query.get_or_404(client_id)
    doc = Document.query.filter_by(id=doc_id, client_id=client_id).first_or_404()
    
    doc.deadline_start = None
    doc.deadline_end = None
    doc.deadline_warning_days = 7
    
    db.session.commit()
    
    flash(f"تم إزالة الموعد النهائي من الوثيقة '{doc.name}' بنجاح.", "success")
    return redirect(url_for("client_detail", client_id=client_id))

@app.route("/client/<int:client_id>/delete_custom_document/<int:doc_id>", methods=["POST"])
def delete_custom_document(client_id, doc_id):
    """حذف وثيقة مخصصة من العميل"""
    client = Client.query.get_or_404(client_id)
    doc = Document.query.filter_by(id=doc_id, client_id=client_id).first_or_404()
    
    # التحقق من أن الوثيقة ليست من الوثائق الافتراضية
    if doc.name in DOCS_REQUIRED or doc.name in DOCS_OPTIONAL:
        flash("لا يمكن حذف الوثائق الافتراضية.", "warning")
        return redirect(url_for("client_detail", client_id=client_id))
    
    # حذف الملف الفعلي إذا كان موجوداً على القرص
    if doc.file_path:
        try:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], doc.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            flash(f"خطأ في حذف الملف: {str(e)}", "danger")
            return redirect(url_for("client_detail", client_id=client_id))
    # تنظيف الحقول المخزنة في قاعدة البيانات
    doc.file_bytes = None
    doc.file_name = None
    doc.file_mime = None
    doc.file_size = None
    
    # حذف الوثيقة من قاعدة البيانات
    db.session.delete(doc)
    db.session.commit()
    
    flash(f"تم حذف الوثيقة '{doc.name}' بنجاح.", "success")
    return redirect(url_for("client_detail", client_id=client_id))

@app.route("/client/<int:client_id>/delete_document/<int:doc_id>", methods=["POST"])
def delete_document(client_id, doc_id):
    client = Client.query.get_or_404(client_id)
    doc = Document.query.filter_by(id=doc_id, client_id=client_id).first_or_404()
    
    # حذف الملف الفعلي من المجلد إن وُجد
    if doc.file_path:
        try:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], doc.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            flash(f"خطأ في حذف الملف: {str(e)}", "danger")
            return redirect(url_for("client_detail", client_id=client_id))
    
    # تحديث قاعدة البيانات
    # تنظيف حقول الملف
    doc.file_path = None
    doc.file_bytes = None
    doc.file_name = None
    doc.file_mime = None
    doc.file_size = None
    doc.status = "ناقصة"
    doc.uploaded_at = None
    db.session.commit()
    
    flash("تم حذف الملف وتحديث الحالة.", "success")
    return redirect(url_for("client_detail", client_id=client_id))

@app.route("/client/<int:client_id>/download_all_documents")
def download_all_documents(client_id):
    client = Client.query.get_or_404(client_id)
    
    # البحث عن جميع المستندات المرفوعة (في قاعدة البيانات أو على القرص)
    uploaded_docs = [d for d in client.documents if (d.file_bytes is not None and len(d.file_bytes) > 0) or d.file_path]
    
    if not uploaded_docs:
        flash("لا توجد ملفات مرفوعة للتنزيل.", "warning")
        return redirect(url_for("client_detail", client_id=client_id))
    
    try:
        import zipfile
        import io
        
        # إنشاء ملف ZIP في الذاكرة
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for doc in uploaded_docs:
                # لو المخزن في قاعدة البيانات
                if doc.file_bytes and len(doc.file_bytes) > 0:
                    # استخدام اسم الملف الأصلي أو إنشاء اسم مناسب
                    if doc.file_name:
                        # إضافة امتداد الملف إذا لم يكن موجوداً
                        file_name = doc.file_name
                        if not '.' in file_name and doc.file_mime:
                            if 'pdf' in doc.file_mime:
                                file_name += '.pdf'
                            elif 'image' in doc.file_mime:
                                file_name += '.jpg'
                    else:
                        file_name = f"{doc.name}.pdf"  # افتراضي
                    
                    # تنظيف اسم الملف
                    safe_name = secure_filename(file_name)
                    if not safe_name:
                        safe_name = f"{doc.name}_{doc.id}.pdf"
                    
                    zip_file.writestr(safe_name, doc.file_bytes)
                else:
                    # fallback للقرص
                    if doc.file_path:
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], doc.file_path)
                        if os.path.exists(file_path):
                            zip_filename = f"{doc.name}_{os.path.basename(doc.file_path)}"
                            zip_file.write(file_path, zip_filename)
        
        # إعادة تعيين المؤشر لبداية الملف
        zip_buffer.seek(0)
        
        # إنشاء اسم ملف ZIP
        zip_filename = f"{client.name}_ملفات_مرفوعة_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )
        
    except Exception as e:
        flash(f"خطأ في إنشاء ملف ZIP: {str(e)}", "danger")
        return redirect(url_for("client_detail", client_id=client_id))

# -------- متابعات --------
@app.route("/client/<int:client_id>/add_followup", methods=["POST"])
def add_followup(client_id):
    client = Client.query.get_or_404(client_id)
    date_str = request.form.get("follow_date")
    notes = request.form.get("notes", "").strip()
    if not date_str or not notes:
        flash("تاريخ المتابعة والملاحظات مطلوبان.", "danger")
        return redirect(url_for("client_detail", client_id=client_id))
    fdate = datetime.strptime(date_str, "%Y-%m-%d").date()
    fu = Followup(client_id=client.id, date=fdate, notes=notes)
    db.session.add(fu)
    db.session.commit()
    flash("تم حفظ المتابعة.", "success")
    return redirect(url_for("client_detail", client_id=client_id))

@app.route("/client/<int:client_id>/update_status", methods=["POST"])
def update_client_status(client_id):
    client = Client.query.get_or_404(client_id)
    new_status = request.form.get("new_status", "").strip()
    rejection_reason = request.form.get("rejection_reason", "").strip()
    
    if not new_status:
        flash("من فضلك اختر الحالة الجديدة.", "danger")
        return redirect(url_for("client_detail", client_id=client_id))
    
    if new_status == client.status:
        flash("الحالة المختارة هي نفس الحالة الحالية.", "info")
        return redirect(url_for("client_detail", client_id=client_id))
    
    # التحقق من رقم المرة عند اختيار "رفع مرة أخرى"
    if new_status == "رفع مرة أخرى" and not rejection_reason:
        flash("من فضلك أدخل رقم المرة (مثال: 2، 3، 4...) عند اختيار 'رفع مرة أخرى'.", "danger")
        return redirect(url_for("client_detail", client_id=client_id))
    
    # تحديث الحالة ورقم المرة
    old_status = client.status
    client.status = new_status
    
    if new_status == "رفع مرة أخرى":
        client.rejection_reason = rejection_reason
    else:
        client.rejection_reason = None  # مسح رقم المرة عند تغيير الحالة
    
    db.session.commit()
    
    if new_status == "رفع مرة أخرى":
        flash(f"تم تحديث حالة العميل {client.name} إلى '{new_status}' للمرة رقم {rejection_reason}.", "success")
    else:
        flash(f"تم تحديث حالة العميل {client.name} من '{old_status}' إلى '{new_status}'.", "success")
    
    return redirect(url_for("client_detail", client_id=client_id))

@app.route("/clients_needing_attention")
def clients_needing_attention():
    """عرض جميع العملاء المحتاجين متابعة"""
    # الحصول على جميع العملاء
    all_clients = Client.query.all()
    
    # تصفية العملاء المحتاجين متابعة
    clients_needing_attention = []
    
    for client in all_clients:
        missing_docs = 0
        overdue_payments = 0
        
        # حساب الأوراق الناقصة
        for doc in client.documents:
            if doc.status == "ناقصة" and doc.required:
                missing_docs += 1
        
        # حساب الدفعات المتأخرة
        for payment in client.payments:
            if not payment.is_paid and payment.next_due_date and payment.next_due_date < date.today():
                overdue_payments += 1
        
        # إضافة العميل إذا كان يحتاج متابعة
        if missing_docs > 0 or overdue_payments > 0:
            client.missing_docs = missing_docs
            client.overdue_payments = overdue_payments
            clients_needing_attention.append(client)
    
    # ترتيب العملاء حسب الأولوية (الأوراق الناقصة أولاً، ثم الدفعات المتأخرة)
    clients_needing_attention.sort(key=lambda x: (x.missing_docs, x.overdue_payments), reverse=True)
    
    return render_template("clients_needing_attention.html", 
                         clients=clients_needing_attention,
                         total_clients=len(clients_needing_attention))

@app.route("/all_clients")
def all_clients():
    """عرض جميع العملاء مع إمكانية البحث والتصفية"""
    # الحصول على معاملات البحث
    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    visa_type_filter = request.args.get('visa_type', '')
    
    # بناء الاستعلام
    query = Client.query
    
    # تطبيق فلتر البحث
    if search_query:
        query = query.filter(
            db.or_(
                Client.name.contains(search_query),
                Client.phone.contains(search_query)
            )
        )
    
    # تطبيق فلتر الحالة
    if status_filter:
        query = query.filter(Client.status == status_filter)
    
    # تطبيق فلتر نوع التأشيرة
    if visa_type_filter:
        query = query.filter(Client.visa_type == visa_type_filter)
    
    # ترتيب النتائج
    clients = query.order_by(Client.created_at.desc()).all()
    
    # حساب الإحصائيات
    total_clients = len(clients)
    status_counts = {
        'جاري': len([c for c in clients if c.status == 'جاري']),
        'مكتمل': len([c for c in clients if c.status == 'مكتمل']),
        'مرفوض': len([c for c in clients if c.status == 'مرفوض']),
        'رفع مرة أخرى': len([c for c in clients if c.status == 'رفع مرة أخرى']),
        'لغا المعاملة': len([c for c in clients if c.status == 'لغا المعاملة'])
    }
    
    # الحصول على أنواع التأشيرات الفريدة
    visa_types = db.session.query(Client.visa_type).distinct().all()
    visa_types = [vt[0] for vt in visa_types]
    
    return render_template("all_clients.html", 
                         clients=clients,
                         total_clients=total_clients,
                         status_counts=status_counts,
                         visa_types=visa_types,
                         search_query=search_query,
                         status_filter=status_filter,
                         visa_type_filter=visa_type_filter)


@app.route("/manage_status")
def manage_status():
    # عرض العملاء حسب الحالة
    status_filter = request.args.get('status', '')
    clients = []
    
    if status_filter:
        if status_filter == "مكتمل":
            clients = Client.query.filter_by(status="مكتمل").order_by(Client.created_at.desc()).all()
        elif status_filter == "جاري":
            clients = Client.query.filter_by(status="جاري").order_by(Client.created_at.desc()).all()
        elif status_filter == "مرفوض":
            clients = Client.query.filter_by(status="مرفوض").order_by(Client.created_at.desc()).all()
        elif status_filter == "رفع مرة أخرى":
            clients = Client.query.filter_by(status="رفع مرة أخرى").order_by(Client.created_at.desc()).all()
        elif status_filter == "لغا المعاملة":
            clients = Client.query.filter_by(status="لغا المعاملة").order_by(Client.created_at.desc()).all()
    
    return render_template("manage_status.html", clients=clients, status_filter=status_filter)

# -------- تحديث الأوراق للعملاء الموجودين --------
def update_existing_clients_documents():
    """تحديث الأوراق للعملاء الموجودين بإضافة الأوراق الجديدة"""
    clients = Client.query.all()
    updated_count = 0
    
    for client in clients:
        # الحصول على أسماء الأوراق الموجودة بالفعل
        existing_doc_names = [d.name for d in client.documents]
        
        # إضافة الأوراق الجديدة التي لم تكن موجودة
        for doc_name in DOCS_REQUIRED:
            if doc_name not in existing_doc_names:
                new_doc = Document(
                    client_id=client.id,
                    name=doc_name,
                    required=True,
                    status="ناقصة"
                )
                db.session.add(new_doc)
                updated_count += 1
        
        # إضافة الأوراق الاختيارية الجديدة
        for doc_name in DOCS_OPTIONAL:
            if doc_name not in existing_doc_names:
                new_doc = Document(
                    client_id=client.id,
                    name=doc_name,
                    required=False,
                    status="ناقصة"
                )
                db.session.add(new_doc)
                updated_count += 1
    
    if updated_count > 0:
        db.session.commit()
        return updated_count
    return 0

@app.route("/update_documents")
def update_documents():
    """تحديث الأوراق لجميع العملاء الموجودين"""
    try:
        updated_count = update_existing_clients_documents()
        if updated_count > 0:
            flash(f"تم تحديث {updated_count} ورقة للعملاء الموجودين.", "success")
        else:
            flash("جميع العملاء لديهم الأوراق المطلوبة بالفعل.", "info")
    except Exception as e:
        flash(f"حدث خطأ أثناء تحديث الأوراق: {str(e)}", "danger")
    
    return redirect(url_for("dashboard"))

@app.route("/migrate_db")
def manual_migrate_db():
    """تحديث قاعدة البيانات يدوياً"""
    try:
        migrate_database()
        flash("تم تحديث قاعدة البيانات بنجاح.", "success")
    except Exception as e:
        flash(f"خطأ في تحديث قاعدة البيانات: {str(e)}", "danger")
    
    return redirect(url_for("dashboard"))

@app.route("/fix_user_schema")
def fix_user_schema():
    """إصلاح schema جدول المستخدمين"""
    try:
        from sqlalchemy import text
        engine_name = db.engine.name if hasattr(db, 'engine') else 'sqlite'
        
        if engine_name != 'sqlite':
            # PostgreSQL migration
            with db.engine.begin() as conn:
                conn.execute(text("""
                    DO $$
                    BEGIN
                        -- إضافة عمود employee_name لجدول user إن لم يكن موجوداً
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='user' AND column_name='employee_name'
                        ) THEN
                            ALTER TABLE "user" ADD COLUMN employee_name VARCHAR(120);
                            -- تعيين قيمة افتراضية للمستخدمين الموجودين
                            UPDATE "user" SET employee_name = username WHERE employee_name IS NULL;
                        END IF;
                    END $$;
                """))
        else:
            # SQLite migration
            result = db.session.execute(text("PRAGMA table_info(user)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'employee_name' not in columns:
                db.session.execute(text("ALTER TABLE user ADD COLUMN employee_name VARCHAR(120)"))
                db.session.execute(text("UPDATE user SET employee_name = username WHERE employee_name IS NULL"))
        
        db.session.commit()
        flash("تم إصلاح schema جدول المستخدمين بنجاح.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"خطأ في إصلاح schema جدول المستخدمين: {str(e)}", "danger")
    
    return redirect(url_for("choose_section"))

@app.route("/setup_admin")
def setup_admin():
    """إعداد المستخدم المدير"""
    try:
        # التحقق من وجود المستخدم المدير
        admin_user = User.query.filter_by(username='admin').first()
        
        if admin_user:
            # تحديث الدور إذا لم يكن admin
            if admin_user.role != 'admin':
                admin_user.role = 'admin'
                db.session.commit()
                flash("تم تحديث المستخدم الموجود إلى مدير.", "success")
            else:
                flash("المستخدم المدير موجود بالفعل.", "info")
        else:
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
            flash("تم إنشاء المستخدم المدير بنجاح! (admin/admin123)", "success")
            
    except Exception as e:
        db.session.rollback()
        flash(f"خطأ في إعداد المستخدم المدير: {str(e)}", "danger")
    
    return redirect(url_for("choose_section"))

# -------- تحديث قاعدة البيانات --------
def migrate_database():
    """تحديث قاعدة البيانات لإضافة الأعمدة الجديدة"""
    try:
        from sqlalchemy import text
        # محرك قاعدة البيانات
        engine_name = db.engine.name if hasattr(db, 'engine') else 'sqlite'
        if engine_name != 'sqlite':
            # تنفيذ ترقية مخصصة لـ Postgres لإضافة أعمدة الملفات وإن لم تكن موجودة
            # إضافة الأعمدة بأمان إن لم تكن موجودة
            with db.engine.begin() as conn:
                conn.execute(text("""
                    DO $$
                    BEGIN
                        -- إضافة عمود employee_name لجدول user إن لم يكن موجوداً
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='user' AND column_name='employee_name'
                        ) THEN
                            ALTER TABLE "user" ADD COLUMN employee_name VARCHAR(120);
                            -- تعيين قيمة افتراضية للمستخدمين الموجودين
                            UPDATE "user" SET employee_name = username WHERE employee_name IS NULL;
                        END IF;
                        
                        -- إضافة أعمدة الملفات لجدول document
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='document' AND column_name='file_bytes'
                        ) THEN
                            ALTER TABLE document ADD COLUMN file_bytes BYTEA;
                        END IF;
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='document' AND column_name='file_name'
                        ) THEN
                            ALTER TABLE document ADD COLUMN file_name VARCHAR(300);
                        END IF;
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='document' AND column_name='file_mime'
                        ) THEN
                            ALTER TABLE document ADD COLUMN file_mime VARCHAR(100);
                        END IF;
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='document' AND column_name='file_size'
                        ) THEN
                            ALTER TABLE document ADD COLUMN file_size INTEGER;
                        END IF;
                        
                        -- إضافة أعمدة المواعيد لجدول document
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='document' AND column_name='deadline_start'
                        ) THEN
                            ALTER TABLE document ADD COLUMN deadline_start DATE;
                        END IF;
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='document' AND column_name='deadline_end'
                        ) THEN
                            ALTER TABLE document ADD COLUMN deadline_end DATE;
                        END IF;
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='document' AND column_name='deadline_warning_days'
                        ) THEN
                            ALTER TABLE document ADD COLUMN deadline_warning_days INTEGER DEFAULT 7;
                        END IF;
                        
                        -- إضافة عمود payment_type لجدول payment
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='payment' AND column_name='payment_type'
                        ) THEN
                            ALTER TABLE payment ADD COLUMN payment_type VARCHAR(50);
                        END IF;
                        
                        -- إضافة عمود rejection_reason لجدول client
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='client' AND column_name='rejection_reason'
                        ) THEN
                            ALTER TABLE client ADD COLUMN rejection_reason VARCHAR(50);
                        END IF;
                        
                        -- إضافة عمود client_id لجدول client_followup
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='client_followup' AND column_name='client_id'
                        ) THEN
                            ALTER TABLE client_followup ADD COLUMN client_id INTEGER;
                        END IF;
                    END $$;
                """))
            return
        
        # التحقق من وجود عمود payment_type في جدول payment
        result = db.session.execute(text("PRAGMA table_info(payment)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'payment_type' not in columns:
            db.session.execute(text("ALTER TABLE payment ADD COLUMN payment_type VARCHAR(50)"))
            print("✅ تم إضافة عمود payment_type")
        
        # تحديث الدفعات الموجودة لتكون من نوع "دفعة"
        db.session.execute(text("UPDATE payment SET payment_type = 'دفعة' WHERE payment_type IS NULL"))
        print("✅ تم تحديث الدفعات الموجودة")
        
        # التحقق من وجود عمود rejection_reason في جدول client
        result = db.session.execute(text("PRAGMA table_info(client)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'rejection_reason' not in columns:
            db.session.execute(text("ALTER TABLE client ADD COLUMN rejection_reason VARCHAR(50)"))
            print("✅ تم إضافة عمود rejection_reason")
        
        # التحقق من وجود أعمدة المواعيد في جدول document
        result = db.session.execute(text("PRAGMA table_info(document)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'deadline_start' not in columns:
            db.session.execute(text("ALTER TABLE document ADD COLUMN deadline_start DATE"))
            print("✅ تم إضافة عمود deadline_start")
        
        if 'deadline_end' not in columns:
            db.session.execute(text("ALTER TABLE document ADD COLUMN deadline_end DATE"))
            print("✅ تم إضافة عمود deadline_end")
        
        if 'deadline_warning_days' not in columns:
            db.session.execute(text("ALTER TABLE document ADD COLUMN deadline_warning_days INTEGER DEFAULT 7"))
            print("✅ تم إضافة عمود deadline_warning_days")
        
        # التحقق من وجود عمود client_id في جدول client_followup
        result = db.session.execute(text("PRAGMA table_info(client_followup)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'client_id' not in columns:
            db.session.execute(text("ALTER TABLE client_followup ADD COLUMN client_id INTEGER"))
            print("✅ تم إضافة عمود client_id لجدول client_followup")
        
        # إضافة عمود followup_id لجدول legal_case
        result = db.session.execute(text("PRAGMA table_info(legal_case)"))
        columns = [row[1] for row in result.fetchall()]
        if 'followup_id' not in columns:
            db.session.execute(text("ALTER TABLE legal_case ADD COLUMN followup_id INTEGER"))
            print("✅ تم إضافة عمود followup_id لجدول legal_case")
        
        # إضافة عمود original_client_id لجدول completed_client
        result = db.session.execute(text("PRAGMA table_info(completed_client)"))
        columns = [row[1] for row in result.fetchall()]
        if 'original_client_id' not in columns:
            db.session.execute(text("ALTER TABLE completed_client ADD COLUMN original_client_id INTEGER"))
            print("✅ تم إضافة عمود original_client_id لجدول completed_client")
        
        db.session.commit()
        print("🎉 تم تحديث قاعدة البيانات بنجاح")
        
    except Exception as e:
        print(f"❌ خطأ في تحديث قاعدة البيانات: {e}")
        db.session.rollback()

# -------- تهيئة قاعدة البيانات --------
def init_db():
    db.create_all()
    # تحديث قاعدة البيانات
    migrate_database()

# Initialize database on first request
with app.app_context():
    init_db()
    # تحديث قاعدة البيانات لإضافة الأعمدة الجديدة
    try:
        migrate_database()
    except Exception as e:
        print(f"خطأ في الترقية التلقائية: {e}")
    
    # تحديث الأوراق للعملاء الموجودين تلقائياً
    try:
        update_existing_clients_documents()
    except:
        pass  # تجاهل الأخطاء في حالة عدم وجود عملاء بعد

if __name__ == "__main__":
    app.run(debug=True)
