from datetime import date, datetime
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///govind_nagar.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="member")  # admin/member
    address = db.Column(db.String(255), nullable=False)
    property_type = db.Column(db.String(20), nullable=False, default="house")  # house/shop
    yearly_charge = db.Column(db.Float, nullable=False, default=700)
    active = db.Column(db.Boolean, default=True)

    payments = db.relationship("Payment", backref="member", lazy=True, cascade="all,delete")
    complaints = db.relationship("Complaint", backref="member", lazy=True, cascade="all,delete")
    reminders = db.relationship("ReminderLog", backref="member", lazy=True, cascade="all,delete")


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    paid_on = db.Column(db.Date, nullable=False, default=date.today)
    method = db.Column(db.String(20), nullable=False, default="cash")
    status = db.Column(db.String(20), nullable=False, default="paid")
    notes = db.Column(db.String(255))


class OtherIncome(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255))
    amount = db.Column(db.Float, nullable=False)
    income_date = db.Column(db.Date, nullable=False, default=date.today)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255))
    amount = db.Column(db.Float, nullable=False)
    expense_date = db.Column(db.Date, nullable=False, default=date.today)
    method = db.Column(db.String(20), nullable=False, default="cash")
    receipt_ref = db.Column(db.String(120))


class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(30), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="open")
    admin_note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Guard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    kyc_id = db.Column(db.String(120), nullable=False)
    kyc_doc = db.Column(db.String(255))
    joining_date = db.Column(db.Date, nullable=False, default=date.today)
    monthly_salary = db.Column(db.Float, nullable=False)
    active = db.Column(db.Boolean, default=True)

    salary_payments = db.relationship("GuardSalaryPayment", backref="guard", lazy=True, cascade="all,delete")


class GuardSalaryPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    guard_id = db.Column(db.Integer, db.ForeignKey("guard.id"), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    paid_on = db.Column(db.Date, nullable=False, default=date.today)
    method = db.Column(db.String(20), nullable=False, default="cash")
    notes = db.Column(db.String(255))


class ReminderLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    channel = db.Column(db.String(20), nullable=False)  # sms/whatsapp
    message = db.Column(db.String(300), nullable=False)
    sent_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(30), nullable=False, default="queued")


class AdminSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=False)


def current_user():
    uid = session.get("user_id")
    return User.query.get(uid) if uid else None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user.role != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)

    return wrapper


def generate_complaint_number():
    year = date.today().year
    count = Complaint.query.filter(Complaint.number.like(f"CMP-{year}-%")).count() + 1
    return f"CMP-{year}-{count:04d}"


def get_setting(key, default="1"):
    s = AdminSetting.query.filter_by(key=key).first()
    return s.value if s else default


def set_setting(key, value):
    s = AdminSetting.query.filter_by(key=key).first()
    if not s:
        s = AdminSetting(key=key, value=value)
        db.session.add(s)
    else:
        s.value = value


def due_status(member: User, year: int):
    paid = (
        db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0))
        .filter_by(user_id=member.id, year=year, status="paid")
        .scalar()
    )
    due = max(member.yearly_charge - paid, 0)
    return paid, due


@app.route("/")
def home():
    if current_user():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/setup")
def setup():
    db.create_all()
    if not User.query.filter_by(role="admin").first():
        admin = User(
            name="Super Admin",
            mobile="9999999999",
            password_hash=generate_password_hash("admin123"),
            role="admin",
            address="Govind Nagar Office",
            property_type="house",
            yearly_charge=700,
        )
        db.session.add(admin)
        db.session.commit()
        flash("Default admin created (mobile: 9999999999 / password: admin123)", "success")
    else:
        flash("Setup already complete.", "info")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        mobile = request.form["mobile"].strip()
        password = request.form["password"]
        user = User.query.filter_by(mobile=mobile, active=True).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            flash("Login successful", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    year = date.today().year
    if user.role == "admin":
        members = User.query.filter_by(role="member").count()
        open_complaints = Complaint.query.filter(Complaint.status != "resolved").count()
        total_income = db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0)).scalar() + db.session.query(
            db.func.coalesce(db.func.sum(OtherIncome.amount), 0)
        ).scalar()
        total_expense = db.session.query(db.func.coalesce(db.func.sum(Expense.amount), 0)).scalar() + db.session.query(
            db.func.coalesce(db.func.sum(GuardSalaryPayment.amount), 0)
        ).scalar()
        return render_template(
            "admin_dashboard.html",
            members=members,
            open_complaints=open_complaints,
            total_income=total_income,
            total_expense=total_expense,
            balance=total_income - total_expense,
            latest_complaints=Complaint.query.order_by(Complaint.created_at.desc()).limit(5).all(),
        )

    paid, due = due_status(user, year)
    return render_template(
        "member_dashboard.html",
        year=year,
        paid=paid,
        due=due,
        complaints=Complaint.query.filter_by(user_id=user.id).order_by(Complaint.created_at.desc()).all(),
        payments=Payment.query.filter_by(user_id=user.id).order_by(Payment.year.desc()).all(),
    )


@app.route("/members")
@login_required
@admin_required
def members():
    query = request.args.get("q", "").strip()
    members_q = User.query.filter_by(role="member")
    if query:
        like = f"%{query}%"
        members_q = members_q.filter(
            db.or_(User.name.ilike(like), User.mobile.ilike(like), User.address.ilike(like))
        )
    members = members_q.order_by(User.id.desc()).all()
    year = date.today().year
    return render_template("members.html", members=members, year=year, due_status=due_status)


@app.route("/members/new", methods=["POST"])
@login_required
@admin_required
def create_member():
    ptype = request.form["property_type"]
    charge = 700 if ptype == "house" else 1200
    member = User(
        name=request.form["name"],
        mobile=request.form["mobile"],
        password_hash=generate_password_hash(request.form.get("password", "member123")),
        role="member",
        address=request.form["address"],
        property_type=ptype,
        yearly_charge=charge,
    )
    db.session.add(member)
    db.session.commit()
    flash("Member added successfully", "success")
    return redirect(url_for("members"))


@app.route("/members/<int:user_id>/edit", methods=["POST"])
@login_required
@admin_required
def edit_member(user_id):
    member = User.query.get_or_404(user_id)
    member.name = request.form["name"]
    member.mobile = request.form["mobile"]
    member.address = request.form["address"]
    member.property_type = request.form["property_type"]
    member.yearly_charge = 700 if member.property_type == "house" else 1200
    if request.form.get("password"):
        member.password_hash = generate_password_hash(request.form["password"])
    db.session.commit()
    flash("Member updated and saved", "success")
    return redirect(url_for("members"))


@app.route("/payments", methods=["GET", "POST"])
@login_required
@admin_required
def payments():
    if request.method == "POST":
        payment = Payment(
            user_id=int(request.form["user_id"]),
            year=int(request.form["year"]),
            amount=float(request.form["amount"]),
            paid_on=datetime.strptime(request.form["paid_on"], "%Y-%m-%d").date(),
            method=request.form["method"],
            status=request.form["status"],
            notes=request.form.get("notes", ""),
        )
        db.session.add(payment)
        db.session.commit()
        flash("Payment entry saved", "success")
        return redirect(url_for("payments"))

    payments_list = Payment.query.order_by(Payment.paid_on.desc()).all()
    members = User.query.filter_by(role="member", active=True).all()
    return render_template("payments.html", payments=payments_list, members=members)


@app.route("/reminders/send", methods=["POST"])
@login_required
@admin_required
def send_reminder():
    user_id = int(request.form["user_id"])
    channel = request.form["channel"]
    member = User.query.get_or_404(user_id)
    year = date.today().year
    paid, due = due_status(member, year)
    message = request.form.get(
        "message",
        f"Govind Nagar Suraksha Samiti reminder: Dear {member.name}, please pay pending yearly maintenance of Rs {due:.0f} for {year}.",
    )
    log = ReminderLog(user_id=user_id, channel=channel, message=message, status="sent")
    db.session.add(log)
    db.session.commit()
    flash(f"{channel.upper()} reminder sent to {member.mobile}. (Simulation log created)", "success")
    return redirect(url_for("members"))


@app.route("/complaints", methods=["GET", "POST"])
@login_required
def complaints():
    user = current_user()
    if request.method == "POST":
        complaint = Complaint(
            number=generate_complaint_number(),
            user_id=user.id,
            description=request.form["description"],
        )
        db.session.add(complaint)
        db.session.commit()
        flash(f"Complaint submitted. Number: {complaint.number}", "success")
        return redirect(url_for("complaints"))

    if user.role == "admin":
        all_complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
        return render_template("complaints.html", complaints=all_complaints, admin=True)
    own = Complaint.query.filter_by(user_id=user.id).order_by(Complaint.created_at.desc()).all()
    return render_template("complaints.html", complaints=own, admin=False)


@app.route("/complaints/<int:cid>/update", methods=["POST"])
@login_required
@admin_required
def update_complaint(cid):
    c = Complaint.query.get_or_404(cid)
    c.status = request.form["status"]
    c.admin_note = request.form.get("admin_note", "")
    db.session.commit()
    flash("Complaint updated", "success")
    return redirect(url_for("complaints"))


@app.route("/finance", methods=["GET", "POST"])
@login_required
@admin_required
def finance():
    if request.method == "POST":
        form_type = request.form["form_type"]
        if form_type == "expense":
            ex = Expense(
                category=request.form["category"],
                description=request.form.get("description", ""),
                amount=float(request.form["amount"]),
                expense_date=datetime.strptime(request.form["expense_date"], "%Y-%m-%d").date(),
                method=request.form["method"],
                receipt_ref=request.form.get("receipt_ref", ""),
            )
            db.session.add(ex)
            flash("Expense saved", "success")
        elif form_type == "income":
            inc = OtherIncome(
                source=request.form["source"],
                description=request.form.get("description", ""),
                amount=float(request.form["amount"]),
                income_date=datetime.strptime(request.form["income_date"], "%Y-%m-%d").date(),
            )
            db.session.add(inc)
            flash("Other income saved", "success")
        db.session.commit()
        return redirect(url_for("finance"))

    year = int(request.args.get("year", date.today().year))
    payment_income = db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0)).filter(Payment.year == year).scalar()
    other_income = (
        db.session.query(db.func.coalesce(db.func.sum(OtherIncome.amount), 0))
        .filter(db.extract("year", OtherIncome.income_date) == year)
        .scalar()
    )
    total_income = payment_income + other_income

    expenses_total = (
        db.session.query(db.func.coalesce(db.func.sum(Expense.amount), 0))
        .filter(db.extract("year", Expense.expense_date) == year)
        .scalar()
    )
    guard_salary_total = (
        db.session.query(db.func.coalesce(db.func.sum(GuardSalaryPayment.amount), 0))
        .filter(GuardSalaryPayment.year == year)
        .scalar()
    )
    total_expense = expenses_total + guard_salary_total

    return render_template(
        "finance.html",
        year=year,
        incomes=OtherIncome.query.order_by(OtherIncome.income_date.desc()).all(),
        expenses=Expense.query.order_by(Expense.expense_date.desc()).all(),
        guard_salaries=GuardSalaryPayment.query.order_by(GuardSalaryPayment.paid_on.desc()).all(),
        total_income=total_income,
        total_expense=total_expense,
        net_balance=total_income - total_expense,
        payment_income=payment_income,
        other_income=other_income,
        expenses_total=expenses_total,
        guard_salary_total=guard_salary_total,
    )


@app.route("/guards", methods=["GET", "POST"])
@login_required
@admin_required
def guards():
    if request.method == "POST":
        form_type = request.form["form_type"]
        if form_type == "guard":
            g = Guard(
                name=request.form["name"],
                mobile=request.form["mobile"],
                address=request.form["address"],
                kyc_id=request.form["kyc_id"],
                kyc_doc=request.form.get("kyc_doc", ""),
                joining_date=datetime.strptime(request.form["joining_date"], "%Y-%m-%d").date(),
                monthly_salary=float(request.form["monthly_salary"]),
            )
            db.session.add(g)
            flash("Guard details + KYC saved", "success")
        else:
            s = GuardSalaryPayment(
                guard_id=int(request.form["guard_id"]),
                month=int(request.form["month"]),
                year=int(request.form["year"]),
                amount=float(request.form["amount"]),
                paid_on=datetime.strptime(request.form["paid_on"], "%Y-%m-%d").date(),
                method=request.form["method"],
                notes=request.form.get("notes", ""),
            )
            db.session.add(s)
            flash("Guard salary payment saved", "success")
        db.session.commit()
        return redirect(url_for("guards"))

    return render_template(
        "guards.html",
        guards=Guard.query.order_by(Guard.id.desc()).all(),
        salary_payments=GuardSalaryPayment.query.order_by(GuardSalaryPayment.paid_on.desc()).all(),
    )


@app.route("/admins", methods=["GET", "POST"])
@login_required
@admin_required
def admins():
    if request.method == "POST":
        admin = User(
            name=request.form["name"],
            mobile=request.form["mobile"],
            password_hash=generate_password_hash(request.form["password"]),
            role="admin",
            address=request.form.get("address", "Office"),
            property_type="house",
            yearly_charge=700,
        )
        db.session.add(admin)
        db.session.commit()
        flash("New admin added successfully", "success")
        return redirect(url_for("admins"))
    return render_template("admins.html", admins=User.query.filter_by(role="admin").all())


@app.route("/settings", methods=["GET", "POST"])
@login_required
@admin_required
def settings():
    if request.method == "POST":
        for key in ["show_balance_sheet", "show_expenses", "show_complaints"]:
            set_setting(key, "1" if request.form.get(key) else "0")
        db.session.commit()
        flash("Visibility settings updated", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html", get_setting=get_setting)


@app.context_processor
def inject_globals():
    return {
        "current_user": current_user(),
        "show_balance_sheet": get_setting("show_balance_sheet", "1") == "1",
        "show_expenses": get_setting("show_expenses", "1") == "1",
        "show_complaints": get_setting("show_complaints", "1") == "1",
    }


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0", port=5000)
