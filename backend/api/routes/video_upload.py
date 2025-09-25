# backend/api/routes/video_upload.py
from __future__ import annotations
import uuid, json
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

video_bp = Blueprint("video", __name__)

ALLOWED_MIME = {
    "video/mp4", "video/quicktime", "video/x-matroska", "video/webm", "video/avi"
}

# ---------------- helpers ----------------
def _uploads_dir() -> Path:
    # where the actual files live
    p = Path(current_app.instance_path) / "uploads"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _meta_store_path() -> Path:
    """
    Store metadata at backend/videos.json (app root), not in instance/.
    """
    store = Path(current_app.root_path) / "videos.json"
    store.parent.mkdir(parents=True, exist_ok=True)  # parent is app root; safe no-op
    return store

def _append_metadata(meta: dict) -> None:
    """Append meta to backend/videos.json (stored as a JSON array)."""
    store = _meta_store_path()
    if store.exists():
        try:
            data = json.loads(store.read_text())
            if not isinstance(data, list):
                data = []
        except Exception:
            data = []
    else:
        data = []
    data.append(meta)
    store.write_text(json.dumps(data, indent=2))

def _save_video(file_storage) -> dict:
    if not file_storage or file_storage.filename == "":
        raise ValueError("Empty filename")
    if file_storage.mimetype not in ALLOWED_MIME:
        raise ValueError(f"Unsupported mimetype {file_storage.mimetype}")

    file_id = str(uuid.uuid4())
    ext = Path(secure_filename(file_storage.filename)).suffix or ".mp4"
    out = _uploads_dir() / f"{file_id}{ext}"
    file_storage.save(out)
    return {
        "id": file_id,
        "path": str(out),  # absolute server path to the saved file
        "mimetype": file_storage.mimetype,
        "size_bytes": out.stat().st_size,
        "original_name": secure_filename(file_storage.filename),
    }

def _find_path(file_id: str) -> Path | None:
    for p in _uploads_dir().glob(f"{file_id}.*"):
        return p
    return None

def _delete_video(file_id: str) -> bool:
    p = _find_path(file_id)
    if not p:
        return False
    p.unlink(missing_ok=True)
    return True
# -----------------------------------------


@video_bp.post("/videos")
def upload_video():
    """
    Expects multipart/form-data, field name 'file'.
    Saves file to instance/uploads/ and appends metadata to backend/videos.json.
    Returns a minimal ack (no sensitive path to client).
    """
    if "file" not in request.files:
        return jsonify(error="No file part"), 400

    try:
        meta = _save_video(request.files["file"])
    except ValueError as e:
        return jsonify(error=str(e)), 400

    _append_metadata(meta)
    return jsonify({"ok": True, "id": meta["id"]}), 201

