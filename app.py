import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
from mysql.connector import Error
import boto3
from botocore.exceptions import ClientError
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", ""),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", ""),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "studentdb"),
}
S3_BUCKET = os.getenv("S3_BUCKET", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

s3 = boto3.client("s3", region_name=AWS_REGION)

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(120) NOT NULL,
                email VARCHAR(160) NOT NULL UNIQUE,
                phone VARCHAR(30),
                course VARCHAR(100),
                file_key VARCHAR(500),
                file_name VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
    finally:
        conn.close()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/students")
def students():
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, full_name, email, phone, course, file_key, file_name, created_at FROM students ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        for row in rows:
            row["file_url"] = create_file_url(row["file_key"]) if row["file_key"] else None
        return render_template("students.html", students=rows)
    except Error as e:
        app.logger.exception("Database error")
        flash("Could not load student records. Check database configuration/connectivity.", "error")
        return render_template("students.html", students=[]), 500

def create_file_url(key):
    if not key or not S3_BUCKET:
        return None
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=3600
        )
    except ClientError:
        app.logger.exception("Could not create S3 download URL")
        return None

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    course = request.form.get("course", "").strip()
    upload = request.files.get("document")

    if not full_name or not email:
        flash("Name and email are required.", "error")
        return redirect(url_for("register"))
    if not S3_BUCKET:
        flash("S3_BUCKET is not configured on the server.", "error")
        return redirect(url_for("register"))

    file_key, original_name = None, None
    if upload and upload.filename:
        if not allowed_file(upload.filename):
            flash("Only PNG, JPG, JPEG, and PDF files are allowed.", "error")
            return redirect(url_for("register"))
        upload.stream.seek(0, os.SEEK_END)
        size = upload.stream.tell()
        upload.stream.seek(0)
        if size > MAX_FILE_SIZE:
            flash("File size must be 10 MB or less.", "error")
            return redirect(url_for("register"))

        original_name = secure_filename(upload.filename)
        extension = original_name.rsplit(".", 1)[1].lower()
        file_key = f"student-uploads/{uuid.uuid4().hex}.{extension}"
        try:
            s3.upload_fileobj(
                upload,
                S3_BUCKET,
                file_key,
                ExtraArgs={"ContentType": upload.mimetype or "application/octet-stream"}
            )
        except ClientError:
            app.logger.exception("S3 upload failed")
            flash("File upload to S3 failed. Check the EC2 IAM role and bucket settings.", "error")
            return redirect(url_for("register"))

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO students (full_name, email, phone, course, file_key, file_name) VALUES (%s,%s,%s,%s,%s,%s)",
            (full_name, email, phone, course, file_key, original_name)
        )
        conn.commit()
        cur.close()
        conn.close()
        flash("Student registered successfully!", "success")
        return redirect(url_for("students"))
    except Error as e:
        app.logger.exception("Database insert failed")
        # Avoid leaving an orphaned S3 object if DB insertion fails.
        if file_key:
            try:
                s3.delete_object(Bucket=S3_BUCKET, Key=file_key)
            except ClientError:
                app.logger.warning("Could not clean up uploaded S3 object")
        flash("Registration failed. Check RDS connectivity or whether the email already exists.", "error")
        return redirect(url_for("register"))

@app.route("/health")
def health():
    return {"status": "ok", "app": "student-registration"}, 200

if __name__ == "__main__":
    # For local testing only. In production use Gunicorn behind Nginx/Apache.
    app.run(host="0.0.0.0", port=5000, debug=False)

if __name__ == '__main__' and os.getenv('INIT_DB_ON_START') == '1':
    init_db()
