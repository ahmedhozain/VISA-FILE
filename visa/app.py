import os
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, send_file
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

# Database configuration: REQUIRE DATABASE_URL (Postgres). No SQLite fallback
database_url = os.getenv('DATABASE_URL')
if not database_url:
    raise RuntimeError('DATABASE_URL is required and not set. Please configure it in the environment.')

# Render sometimes provides postgres://, convert to postgresql:// for SQLAlchemy
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
db = SQLAlchemy(app)

# ------------------ Models ------------------
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
    return redirect(url_for("dashboard"))

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
                if doc.file_bytes:
                    safe_name = doc.file_name or f"{client.name}_{doc.name}"
                    zip_file.writestr(safe_name, doc.file_bytes)
                else:
                    # fallback للقرص
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], doc.file_path)
                    if os.path.exists(file_path):
                        zip_filename = f"{client.name}_{doc.name}_{os.path.basename(doc.file_path)}"
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

# -------- تحديث قاعدة البيانات --------
def migrate_database():
    """تحديث قاعدة البيانات لإضافة الأعمدة الجديدة"""
    try:
        from sqlalchemy import text
        # محرك قاعدة البيانات
        engine_name = db.engine.name if hasattr(db, 'engine') else 'sqlite'
        if engine_name != 'sqlite':
            # تنفيذ ترقية مخصصة لـ Postgres لإضافة أعمدة الملفات إن لم تكن موجودة
            # إضافة الأعمدة بأمان إن لم تكن موجودة
            with db.engine.begin() as conn:
                conn.execute(text("""
                    DO $$
                    BEGIN
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
