# Student Registration & File Upload Website (AWS)

A Flask web application for internship practice:
- Student registration (name, email, phone, course)
- Student details stored in Amazon RDS MySQL
- JPG/PNG/PDF upload to Amazon S3
- Student records list and temporary (pre-signed) S3 download links
- Basic upload extension and 10 MB size validation

## Architecture
Browser -> EC2 (Flask/Gunicorn) -> RDS MySQL
                         \-------> Amazon S3
The EC2 instance should use an **IAM role** granting only required access to the target S3 bucket. Do not put AWS access keys in the application or `.env`.

## Local/EC2 prerequisites
- Python 3.10+
- MySQL database/schema (the app creates its `students` table on first successful registration only if you run `init_db`; see below)
- An S3 bucket in your chosen AWS region
- EC2 instance role with S3 permissions

## Configuration
1. Copy `.env.example` to `.env`.
2. Set `DB_HOST` to the RDS endpoint (hostname only), `DB_USER`, `DB_PASSWORD`, `DB_NAME`, and `S3_BUCKET`.
3. Set a strong `FLASK_SECRET_KEY`.
4. Ensure the EC2 role has S3 access to the bucket.

## Deploy from ZIP (assignment requirement)
1. On your Windows PC, ZIP the project folder (this source package is already ZIP-ready).
2. Transfer the ZIP to EC2 using `scp` from PowerShell, for example:
   `scp -i "C:\\path\\key.pem" student-registration-s3-website.zip ubuntu@EC2_PUBLIC_IP:/home/ubuntu/`
3. On EC2, extract into an application folder (not `/var/www/html`):
   `mkdir -p ~/student-portal && unzip ~/student-registration-s3-website.zip -d ~/student-portal`
4. Create a virtual environment and install dependencies:
   `cd ~/student-portal/student-registration-s3-website`
   `python3 -m venv venv && source venv/bin/activate`
   `pip install -r requirements.txt`
5. Create `.env` and configure values. Keep `.env` private.
6. Initialize the database table (after DB connectivity is configured):
   `python -c "from app import init_db; init_db(); print('Table ready')"`
7. Test app locally on EC2:
   `gunicorn --bind 127.0.0.1:5000 app:app`
   In another SSH terminal: `curl http://127.0.0.1:5000/health`
8. Production: configure Nginx/Apache as a reverse proxy to Gunicorn (port 5000), then run Gunicorn with systemd. Do not expose port 5000 publicly; allow HTTP/HTTPS through the web server only.

## Network/security checklist
- EC2 web security group: HTTP 80 from the internet (HTTPS 443 when configured); SSH 22 only from your own public IP.
- RDS security group: MySQL 3306 only from the EC2 security group, never from `0.0.0.0/0`.
- S3 bucket: Block Public Access ON. Application uses EC2 IAM role and pre-signed links for downloads.
- Use HTTPS for real deployments. This starter uses temporary S3 links (1 hour).

## Troubleshooting
- RDS timeout: verify RDS SG inbound 3306 source is EC2 SG, DB is available, endpoint/port correct, and EC2/RDS network routing.
- Access denied: check DB username/password and grants.
- S3 AccessDenied: verify EC2 instance profile role policy, bucket name, and region.
- Duplicate email: email column is unique; use a different email for testing.
- Import errors: activate venv and `pip install -r requirements.txt`.

## Important
This is an educational starter, not a production-ready system. Add authentication/authorization, CSRF protection, stronger validation, malware scanning, backups, and privacy controls before real student data is used. Never upload real sensitive student documents during a demo.
