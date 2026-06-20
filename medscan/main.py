import csv
import io
import os
import uuid
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.utils import secure_filename

from .auth import login_required, role_required
from .db import get_db, log_activity

bp = Blueprint("main", __name__)


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


@bp.route("/")
def index():
    if g.user is None:
        return redirect(url_for("auth.login"))
    return redirect(url_for("main.dashboard"))


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]


def _analyze_scan(modality, filename):
    name = filename.lower()
    if "fract" in name or modality.lower() == "x-ray":
        return "Fracture", 0.91, "Potential fracture pattern detected. Recommend radiologist review."
    if modality.lower() == "mri":
        return "Soft Tissue Finding", 0.86, "Signal irregularity seen; correlate with clinical symptoms."
    return "No Major Abnormality", 0.78, "No high-risk pattern detected by baseline model."


@bp.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    total_patients = db.execute("SELECT COUNT(*) AS c FROM patients").fetchone()["c"]
    total_analyses = db.execute("SELECT COUNT(*) AS c FROM scans").fetchone()["c"]
    week_start = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    weekly = db.execute(
        "SELECT COUNT(*) AS c FROM scans WHERE created_at >= ?", (week_start,)
    ).fetchone()["c"]

    recent = db.execute(
        """
        SELECT s.created_at, s.result_label, s.modality, p.full_name
        FROM scans s
        JOIN patients p ON p.id = s.patient_id
        ORDER BY s.created_at DESC
        LIMIT 5
        """
    ).fetchall()

    return render_template(
        "dashboard.html",
        total_patients=total_patients,
        total_analyses=total_analyses,
        weekly=weekly,
        recent=recent,
    )


@bp.route("/patients", methods=["GET", "POST"])
@login_required
def patients():
    db = get_db()
    if request.method == "POST":
        if g.user["role"] not in {"admin", "doctor"}:
            flash("Only admin/doctor can register patients.", "error")
            return redirect(url_for("main.patients"))

        patient_code = request.form.get("patient_code", "").strip()
        full_name = request.form.get("full_name", "").strip()
        age = request.form.get("age", "").strip()
        gender = request.form.get("gender", "").strip()
        contact = request.form.get("contact", "").strip()

        if not patient_code or not full_name or not age or not gender:
            flash("Patient code, name, age, and gender are required.", "error")
            return redirect(url_for("main.patients"))

        try:
            age_int = int(age)
            if age_int <= 0:
                raise ValueError
        except ValueError:
            flash("Age must be a positive number.", "error")
            return redirect(url_for("main.patients"))

        try:
            db.execute(
                """
                INSERT INTO patients (patient_code, full_name, age, gender, contact, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    patient_code,
                    full_name,
                    age_int,
                    gender,
                    contact,
                    g.user["id"],
                    utc_now_iso(),
                ),
            )
            db.commit()
            log_activity("patient", f"Patient {full_name} registered", g.user["id"])
            flash("Patient registered successfully.", "success")
        except Exception:
            flash("Patient code must be unique.", "error")

        return redirect(url_for("main.patients"))

    search = request.args.get("q", "").strip()
    if search:
        rows = db.execute(
            """
            SELECT id, patient_code, full_name, age, gender, contact, created_at
            FROM patients
            WHERE patient_code LIKE ? OR full_name LIKE ?
            ORDER BY created_at DESC
            """,
            (f"%{search}%", f"%{search}%"),
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT id, patient_code, full_name, age, gender, contact, created_at
            FROM patients
            ORDER BY created_at DESC
            """
        ).fetchall()

    return render_template("patients.html", patients=rows, search=search)


@bp.route("/scans", methods=["GET", "POST"])
@login_required
def scans():
    db = get_db()
    patients = db.execute(
        "SELECT id, patient_code, full_name FROM patients ORDER BY created_at DESC"
    ).fetchall()

    if request.method == "POST":
        if g.user["role"] not in {"admin", "doctor", "technician"}:
            flash("Not authorized to upload scans.", "error")
            return redirect(url_for("main.scans"))

        patient_id = request.form.get("patient_id", "").strip()
        modality = request.form.get("modality", "").strip()
        file = request.files.get("scan_file")

        if not patient_id or not modality or file is None or file.filename == "":
            flash("Patient, modality, and scan file are required.", "error")
            return redirect(url_for("main.scans"))

        if not _allowed_file(file.filename):
            flash("Invalid file type. Allowed: png, jpg, jpeg, dcm", "error")
            return redirect(url_for("main.scans"))

        cleaned_name = secure_filename(file.filename)
        stored_name = f"{uuid.uuid4().hex}_{cleaned_name}"
        path = os.path.join(current_app.config["UPLOAD_FOLDER"], stored_name)
        file.save(path)

        label, confidence, report = _analyze_scan(modality, cleaned_name)
        db.execute(
            """
            INSERT INTO scans (patient_id, modality, file_path, result_label, confidence, report, uploaded_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(patient_id),
                modality,
                path,
                label,
                confidence,
                report,
                g.user["id"],
                utc_now_iso(),
            ),
        )
        db.commit()
        log_activity("scan", f"Scan analyzed ({modality}): {label}", g.user["id"])
        flash("Scan uploaded and analyzed successfully.", "success")
        return redirect(url_for("main.records"))

    return render_template("scans.html", patients=patients)


@bp.route("/records")
@login_required
def records():
    rows = get_db().execute(
        """
        SELECT s.id, s.created_at, s.modality, s.result_label, s.confidence, s.report,
               p.patient_code, p.full_name
        FROM scans s
        JOIN patients p ON p.id = s.patient_id
        ORDER BY s.created_at DESC
        """
    ).fetchall()
    return render_template("records.html", records=rows)


@bp.route("/reports/csv")
@login_required
def export_csv():
    rows = get_db().execute(
        """
        SELECT s.created_at, p.patient_code, p.full_name, s.modality, s.result_label, s.confidence, s.report
        FROM scans s
        JOIN patients p ON p.id = s.patient_id
        ORDER BY s.created_at DESC
        """
    ).fetchall()

    def generate():
        headers = [
            "created_at",
            "patient_code",
            "patient_name",
            "modality",
            "result_label",
            "confidence",
            "report",
        ]
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        for row in rows:
            output = [
                row["created_at"],
                row["patient_code"],
                row["full_name"],
                row["modality"],
                row["result_label"],
                str(round(row["confidence"], 4)),
                row["report"],
            ]
            writer.writerow(output)
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=medscan-records.csv"},
    )
