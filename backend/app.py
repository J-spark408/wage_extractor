import os, re
from flask import Flask, request, send_from_directory, jsonify, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
from datetime import timedelta
from time import time
from dotenv import load_dotenv, find_dotenv
from module.processor import process_payroll
from module.accounts import load_accounts, save_accounts, generate_pin
from module.send_email import send_pin_email
from datetime import datetime
import threading 
load_dotenv(find_dotenv(), override=True)


app = Flask(__name__)

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")
NETLIFY_URL = os.getenv("NETLIFY_URL")
LOCAL_URL = os.getenv("LOCAL_URL", "http://localhost:5000")

potential_origins = [
    NETLIFY_URL,
    PUBLIC_BASE_URL,
    LOCAL_URL,
    "http://localhost:5173",
    "https://ezwager.netlify.app", # <-- Explicitly added the client origin
]

allowed_origins = [url for url in potential_origins if url]

CORS(app, supports_credentials=True, origins=allowed_origins)

# CORS(app, supports_credentials=True, origins=[
#     f"{NETLIFY_URL}",
#     f"{PUBLIC_BASE_URL}",
#     f"{LOCAL_URL}",
#     "http://localhost:5173",
# ])

app.config.update(
    SESSION_COOKIE_SAMESITE="None",  # None for cross-site
    SESSION_COOKIE_SECURE=True,      # must be True for SameSite=None
)

_accounts_lock = threading.Lock() 
_last_forgot = {}

@app.post("/api/forgot-pin")
def forgot_pin():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "Email is required"}), 400

    # 1-minute per-email cooldown
    now = time()
    last = _last_forgot.get(email, 0)
    delta = int(now - last)
    if delta < 60:
        return jsonify({"error": f"Please wait {60 - delta} seconds before trying again."}), 429

    # CHANGED: we now generate & persist a new PIN before emailing
    with _accounts_lock:  # NEW
        accounts = load_accounts()
        if email not in accounts:
            # keep explicit error to support your UI's "invalid email" state
            return jsonify({"error": "Email not found"}), 404

        new_pin = generate_pin()  # NEW
        accounts[email] = new_pin  # NEW
        try:
            save_accounts(accounts)  # NEW
        except Exception:
            app.logger.exception("Failed to save new PIN to accounts.json")
            return jsonify({"error": "Could not update PIN"}), 500

    # Attempt send (email sending outside the lock)
    try:
        send_pin_email(email, new_pin)  # CHANGED: send NEW pin
        _last_forgot[email] = now
        return jsonify({"ok": True})
    except Exception:
        app.logger.exception("Failed to send PIN email")
        return jsonify({"error": "Failed to send email"}), 500


# Secret key for session management (needed for authentication flag)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.permanent_session_lifetime = timedelta(minutes=30)
# -------------------------
# PIN Check API (for React)
# -------------------------
@app.post("/api/check-pin")
def check_pin():
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()
    pin   = (data.get("pin") or "").strip()

    accounts = load_accounts()
    expected_pin = accounts.get(email)

    if expected_pin and pin == expected_pin:
        session.permanent = True
        session["authenticated"] = True
        session["email"] = email
        return jsonify({"success": True})
    return jsonify({"success": False}), 401


CLAIM_10_DIGITS = re.compile(r"^\d{10}$")
MM_DD_YYYY      = re.compile(r"^(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])/\d{4}$")
@app.post("/input")
def receive_input():
    data = request.get_json(force=True, silent=True) or {}
    claim_number = (data.get("claimNumber") or "").strip()
    date_loss    = (data.get("dateLoss") or "").strip()

    if claim_number and len(claim_number) != 10:
        return jsonify({"success": False, "error": "Claim number must be exactly 10 characters."}), 400

    if date_loss:
        if not re.fullmatch(r"(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])/\d{4}", date_loss):
            return jsonify({"success": False, "error": "Date must be in MM/DD/YYYY."}), 400
        try:
            datetime.strptime(date_loss, "%m/%d/%Y")
        except ValueError:
            return jsonify({"success": False, "error": "Invalid calendar date."}), 400
        
    # Persist for later steps (e.g., PDF fill)
    session["claim_number"] = claim_number
    session["date_loss"]    = date_loss

    return jsonify({"success": True, "claimNumber": claim_number, "dateLoss": date_loss})

def normalize_date(s: str) -> str:
    """Try a few common formats and return MM/DD/YYYY, or original string if unknown."""
    from datetime import datetime
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).strftime("%m/%d/%Y")
        except Exception:
            pass
    return s

UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
# -------------------------
# File Upload Route
# -------------------------
@app.post("/upload")
def upload_file():
    if not session.get("authenticated"):
        return jsonify({"error": "Unauthorized"}), 403

    uploaded_file = request.files.get("html_file")
    if not uploaded_file:
        return jsonify({"error": "No file uploaded"}), 400

    filename = secure_filename(uploaded_file.filename)
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    uploaded_file.save(path)

    try:
        pdf_path, excel_path = process_payroll(path)

        # relative paths you already compute
        pdf_rel = os.path.relpath(pdf_path, os.path.join(os.getcwd(), "pdf")).replace("\\", "/")
        excel_rel = os.path.relpath(excel_path, os.path.join(os.getcwd(), "excel")).replace("\\", "/")

        # 👇 absolute, publicly reachable URLs
        pdf_url = f"{PUBLIC_BASE_URL}/download/pdf/{pdf_rel}"
        excel_url = f"{PUBLIC_BASE_URL}/download/excel/{excel_rel}"
        #pdf_url = f"{LOCAL_URL}/download/pdf/{pdf_rel}"
        #excel_url = f"{LOCAL_URL}/download/excel/{excel_rel}"

        # Tell the frontend we're returning JSON
        return jsonify({"pdf_url": pdf_url, "excel_url": excel_url})

    except HTTPException:
        raise
    except Exception:
        app.logger.exception("Unexpected error")
        return jsonify({"error": "Server error while processing file."}), 500
        
@app.after_request
def add_cors_headers(resp):
    # lets JS read Content-Disposition if you care
    resp.headers.add("Access-Control-Expose-Headers", "Content-Disposition")
    return resp

# -------------------------
# Download Files
# -------------------------
@app.get("/download/<folder>/<path:filename>")
def download_file(folder, filename):
    """Allows download of generated PDF/Excel."""
    if folder not in ["pdf", "excel"]:
        return "Invalid folder", 400
    directory = os.path.join(os.getcwd(), folder)
    full_path = os.path.join(directory, filename)
    if not os.path.exists(full_path):
        return f"File not found: {full_path}", 404
    return send_from_directory(directory, filename, as_attachment=("inline" not in request.args))


# -------------------------
# Refresh Page Status
# -------------------------
@app.get("/health")
def health():
    return "ok", 200

# -------------------------
# Error Handlers
# -------------------------
@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": e.description or "Bad request"}), 400
@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Server error while processing file."}), 500


if __name__ == "__main__":
    app.run(debug=True)
