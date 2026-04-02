import json
import os
import re
import subprocess
import requests
from google.auth.transport.requests import Request
from dotenv import load_dotenv

load_dotenv()

# ── Auth config ──────────────────────────────────────────────────────────────
# Primary: OAuth token (user-context, accesses all your files without sharing)
# Fallback: Service account (needs files shared with SA email)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MCP_GOOGLE = os.path.join(os.path.dirname(_PROJECT_ROOT), "mcp-stack", "google")

OAUTH_TOKEN_PATH = os.getenv("GOOGLE_OAUTH_TOKEN", os.path.join(_PROJECT_ROOT, "google_oauth_token.json"))
GOOGLE_SA_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "config/google_service_account.json")
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# LibreOffice binary — try system path first, then macOS app bundle
_LO_CANDIDATES = [
    "libreoffice",
    "soffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/libreoffice",
    "/usr/bin/soffice",
]


def _lo_bin() -> str:
    """Return the first working LibreOffice binary."""
    import shutil
    for candidate in _LO_CANDIDATES:
        if shutil.which(candidate) or os.path.isfile(candidate):
            return candidate
    raise RuntimeError("LibreOffice not found — install it or set PATH")


def doc_url_to_id(url_or_id: str) -> str:
    """
    Accept a Google Docs/Drive URL or a bare file ID and return the file ID.
    Handles formats:
      - https://docs.google.com/document/d/<ID>/edit
      - https://drive.google.com/file/d/<ID>/view
      - https://drive.google.com/open?id=<ID>
      - bare ID (returned as-is)
    """
    # Google Docs / Drive URL patterns
    m = re.search(r"/d/([a-zA-Z0-9_-]{20,})", url_or_id)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]{20,})", url_or_id)
    if m:
        return m.group(1)
    # Assume it's already a bare ID
    return url_or_id.strip()


def get_credentials():
    """Try OAuth token first (user-context), fall back to service account."""
    # ── OAuth (preferred) ────────────────────────────────────────────────
    if os.path.exists(OAUTH_TOKEN_PATH):
        try:
            with open(OAUTH_TOKEN_PATH) as f:
                token_data = json.load(f)

            from google.oauth2.credentials import Credentials
            creds = Credentials(
                token=None,  # force refresh — cached tokens go stale silently
                refresh_token=token_data["refresh_token"],
                token_uri=token_data["token_uri"],
                client_id=token_data["client_id"],
                client_secret=token_data["client_secret"],
                scopes=token_data.get("scopes", SCOPES),
            )
            creds.refresh(Request())
            # Save refreshed token back
            token_data["token"] = creds.token
            with open(OAUTH_TOKEN_PATH, "w") as f:
                json.dump(token_data, f, indent=2)
            print("[gdrive] Using OAuth token (user-context)")
            return creds
        except Exception as e:
            print(f"[gdrive] OAuth token failed ({e}), trying service account...")

    # ── Service Account (fallback) ───────────────────────────────────────
    if os.path.exists(GOOGLE_SA_JSON):
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_SA_JSON, scopes=SCOPES
        )
        creds.refresh(Request())
        print("[gdrive] Using service account")
        return creds

    raise RuntimeError(
        f"No Google credentials found. "
        f"Checked OAuth: {OAUTH_TOKEN_PATH}, SA: {GOOGLE_SA_JSON}"
    )


def convert_docx_to_pdf(docx_path: str) -> str:
    """Convert a DOCX file to PDF using LibreOffice headless. Returns the PDF path."""
    out_dir = os.path.dirname(os.path.abspath(docx_path))
    subprocess.run(
        [_lo_bin(), "--headless", "--convert-to", "pdf", "--outdir", out_dir, docx_path],
        check=True, timeout=60, capture_output=True,
    )
    pdf_path = os.path.splitext(docx_path)[0] + ".pdf"
    if not os.path.exists(pdf_path):
        raise RuntimeError(f"PDF conversion produced no output: {pdf_path}")
    return pdf_path


def download_doc_as_pdf(doc_id: str, output_path: str) -> str:
    """Download a Google Drive file as PDF via authenticated Drive API.
    Handles both native Google Docs (export) and uploaded DOCX (download + convert).
    doc_id may be a bare ID or a full Google Docs URL."""
    doc_id = doc_url_to_id(doc_id)
    creds = get_credentials()
    headers = {"Authorization": f"Bearer {creds.token}"}

    # Step 1: Check file mimeType
    meta_r = requests.get(
        f"https://www.googleapis.com/drive/v3/files/{doc_id}",
        params={"fields": "id,name,mimeType"},
        headers=headers, timeout=15,
    )
    meta_r.raise_for_status()
    mime = meta_r.json().get("mimeType", "")
    name = meta_r.json().get("name", "")

    if "google-apps.document" in mime:
        # Native Google Doc — export directly as PDF
        r = requests.get(
            f"https://www.googleapis.com/drive/v3/files/{doc_id}/export",
            params={"mimeType": "application/pdf"},
            headers=headers, stream=True, timeout=30,
        )
        r.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    else:
        # Uploaded file (DOCX/PDF/etc) — download raw then convert if needed
        r = requests.get(
            f"https://www.googleapis.com/drive/v3/files/{doc_id}",
            params={"alt": "media"},
            headers=headers, stream=True, timeout=30,
        )
        r.raise_for_status()

        if "pdf" in mime:
            # Already PDF — save directly
            with open(output_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        else:
            # DOCX or other — save then convert via LibreOffice
            docx_path = output_path.replace(".pdf", ".docx")
            with open(docx_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            convert_docx_to_pdf(docx_path)
            # LibreOffice outputs same name with .pdf extension
            if os.path.exists(docx_path):
                os.remove(docx_path)

    if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
        raise RuntimeError(f"PDF too small or missing — likely empty doc")
    print(f"[gdrive] Downloaded PDF: {name} ({os.path.getsize(output_path) // 1024}KB)")
    return output_path


def download_doc_as_docx(doc_id: str, output_path: str) -> str:
    """doc_id may be a bare ID or a full Google Docs URL."""
    doc_id = doc_url_to_id(doc_id)
    creds = get_credentials()
    headers = {"Authorization": f"Bearer {creds.token}"}

    # Check mimeType to decide export vs download
    meta_r = requests.get(
        f"https://www.googleapis.com/drive/v3/files/{doc_id}",
        params={"fields": "mimeType"},
        headers=headers, timeout=15,
    )
    meta_r.raise_for_status()
    mime = meta_r.json().get("mimeType", "")

    if "google-apps.document" in mime:
        url = f"https://www.googleapis.com/drive/v3/files/{doc_id}/export"
        params = {"mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    else:
        url = f"https://www.googleapis.com/drive/v3/files/{doc_id}"
        params = {"alt": "media"}

    r = requests.get(url, params=params, headers=headers, stream=True, timeout=30)
    r.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return output_path
