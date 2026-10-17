import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Depends, Header
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from dotenv import dotenv_values, load_dotenv
from app.config import OCR_MIN_CONFIDENCE
from app.database import init_db, connection, row_to_dict
from app.ocr import extract_text
from app.router import predict, RouterNotTrained
from app.schemas import StaffUpdate

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_FILE)

app = FastAPI(title="Grievance Triage Desk", version="1.0.0")
staff_security = HTTPBasic(auto_error=False)

def require_staff(credentials: HTTPBasicCredentials | None = Depends(staff_security)):
    file_values = dotenv_values(ENV_FILE)
    expected_username = os.getenv("STAFF_USERNAME") or file_values.get("STAFF_USERNAME")
    expected_password = os.getenv("STAFF_PASSWORD") or file_values.get("STAFF_PASSWORD")
    if not expected_username or not expected_password:
        raise HTTPException(503, "Staff access is not configured.")
    if credentials is None or not (
        hmac.compare_digest(credentials.username.encode(), expected_username.encode())
        and hmac.compare_digest(credentials.password.encode(), expected_password.encode())
    ):
        raise HTTPException(401, "Staff sign-in failed.", headers={"WWW-Authenticate": "Basic"})
    return credentials.username

@app.on_event("startup")
def startup():
    init_db()

def save_item(submitted, extracted, kind, filename, ocr_conf, result):
    tracking_code = secrets.token_urlsafe(32)
    tracking_token_hash = hashlib.sha256(tracking_code.encode()).hexdigest()
    reasons = [x for x in (result["review_reason"] or "").split(",") if x]
    if kind == "file":
        if ocr_conf is None or ocr_conf < OCR_MIN_CONFIDENCE:
            reasons.append("low_ocr_confidence")
        if not extracted.strip():
            reasons.append("empty_extracted_text")
    reasons = list(dict.fromkeys(reasons))
    with connection() as conn:
        cur = conn.execute(
            "INSERT INTO grievances (submitted_text,extracted_text,input_type,filename,ocr_confidence,predicted_department,top3_json,confidence,needs_review,review_reason,original_prediction,final_department,tracking_token_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (submitted, extracted, kind, filename, ocr_conf, result["predicted_department"],
             json.dumps(result["top3"]), result["confidence"], int(bool(reasons)),
             ",".join(reasons) or None, result["predicted_department"], result["predicted_department"], tracking_token_hash))
        item = row_to_dict(conn.execute("SELECT * FROM grievances WHERE id=?", (cur.lastrowid,)).fetchone())
        item["tracking_code"] = tracking_code
        return item

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/grievances/{grievance_id}/status")
def grievance_status(grievance_id: int, tracking_code: str = Header(alias="X-Tracking-Code", min_length=20)):
    supplied_hash = hashlib.sha256(tracking_code.encode()).hexdigest()
    with connection() as conn:
        row = conn.execute(
            "SELECT id,status,final_department,resolution_note,created_at,updated_at,tracking_token_hash FROM grievances WHERE id=?",
            (grievance_id,)
        ).fetchone()
    if row is None or not row["tracking_token_hash"] or not hmac.compare_digest(supplied_hash, row["tracking_token_hash"]):
        raise HTTPException(404, "Complaint not found.")
    return {key: row[key] for key in ("id", "status", "final_department", "resolution_note", "created_at", "updated_at")}

@app.post("/grievances")
async def create_grievance(text: str | None = Form(default=None), file: UploadFile | None = File(default=None)):
    has_text = bool(text and text.strip())
    if not has_text and not file:
        raise HTTPException(400, "Enter complaint text or upload an image/PDF before submitting.")
    if has_text and file:
        raise HTTPException(400, "Provide either complaint text or one image/PDF file.")
    try:
        if file:
            content = await file.read()
            extracted, confidence = extract_text(file.filename or "upload", content)
            if extracted.strip():
                result = predict(extracted)
            else:
                # Preserve failed OCR submissions for the officer queue without inventing a class.
                result = {"predicted_department": "Unclassified", "top3": [],
                          "confidence": 0.0, "needs_review": True,
                          "review_reason": "empty_extracted_text"}
            return save_item("", extracted, "file", file.filename, confidence, result)
        result = predict(text)
        return save_item(text, text, "text", None, None, result)
    except RouterNotTrained as exc:
        raise HTTPException(503, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Could not process complaint. Check OCR installation and input file. Details: {exc}")

@app.get("/grievances")
def list_grievances(department: str | None = None, needs_review: bool | None = None,
                    status: str | None = Query(None, pattern="^(pending|solved|rejected)$"),
                    limit: int = Query(200, ge=1, le=1000),
                    _staff: str = Depends(require_staff)):
    sql, params = "SELECT * FROM grievances WHERE 1=1", []
    if department:
        sql += " AND (final_department=? OR predicted_department=?)"; params += [department, department]
    if needs_review is not None:
        sql += " AND needs_review=?"; params.append(int(needs_review))
    if status:
        sql += " AND status=?"; params.append(status)
    sql += " ORDER BY created_at DESC,id DESC LIMIT ?"; params.append(limit)
    with connection() as conn:
        return [row_to_dict(r) for r in conn.execute(sql, params).fetchall()]

@app.patch("/grievances/{grievance_id}")
def update_grievance(grievance_id: int, update: StaffUpdate, _staff: str = Depends(require_staff)):
    changes = update.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(400, "Provide a department, status, or resolution note to update.")
    department = changes.get("department")
    if department is not None:
        department = department.strip()
        if not department:
            raise HTTPException(400, "Department cannot be empty.")
    status = changes.get("status")
    resolution_note = changes.get("resolution_note")
    with connection() as conn:
        found = conn.execute("SELECT id FROM grievances WHERE id=?", (grievance_id,)).fetchone()
        if not found: raise HTTPException(404, "Grievance not found.")
        assignments = ["updated_at=CURRENT_TIMESTAMP"]
        values = []
        if department is not None:
            assignments.extend(["corrected_department=?", "final_department=?", "needs_review=0", "review_reason=NULL"])
            values.extend([department, department])
        if status is not None:
            assignments.append("status=?")
            values.append(status)
        if "resolution_note" in changes:
            assignments.append("resolution_note=?")
            values.append(resolution_note.strip() or None if resolution_note else None)
        values.append(grievance_id)
        conn.execute(f"UPDATE grievances SET {', '.join(assignments)} WHERE id=?", values)
        return row_to_dict(conn.execute("SELECT * FROM grievances WHERE id=?", (grievance_id,)).fetchone())

@app.get("/stats")
def stats(_staff: str = Depends(require_staff)):
    with connection() as conn:
        total = conn.execute("SELECT COUNT(*) n FROM grievances").fetchone()["n"]
        review = conn.execute("SELECT COUNT(*) n FROM grievances WHERE needs_review=1").fetchone()["n"]
        corrected = conn.execute("SELECT COUNT(*) n FROM grievances WHERE corrected_department IS NOT NULL").fetchone()["n"]
        by_dept = conn.execute("SELECT COALESCE(final_department,predicted_department) department,COUNT(*) count FROM grievances GROUP BY COALESCE(final_department,predicted_department) ORDER BY count DESC").fetchall()
    return {"total": total, "needs_review": review, "needs_review_pct": round(100*review/total,2) if total else 0,
            "corrected": corrected, "corrected_pct": round(100*corrected/total,2) if total else 0,
            "counts_by_department": [dict(r) for r in by_dept]}
