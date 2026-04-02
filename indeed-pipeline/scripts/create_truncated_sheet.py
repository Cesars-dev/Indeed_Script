import os
import json
import csv
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

OAUTH_TOKEN_PATH = "/home/julio/projects/Indeed_Script/indeed-pipeline/google_oauth_token.json"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1bR12LF7nCLANCz5hfRinIsbY9BXfCLF23ug8F_g_Nuw/export?format=csv&gid=0"

def main():
    # 1. Download original CSV
    resp = requests.get(SHEET_URL)
    resp.raise_for_status()
    import io
    reader = list(csv.reader(io.StringIO(resp.text)))
    
    # Original processed index 0 to 24 (25 jobs). Job 26 is index 25 in Python.
    # reader[0] = header. reader[1] = job index 0. reader[26] = job index 25 (Job 26)
    new_rows = [reader[0]] + reader[26:]
    
    # 2. Auth via existing OAuth token
    with open(OAUTH_TOKEN_PATH) as f:
        token_data = json.load(f)
        
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data["refresh_token"],
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data["scopes"],
    )
    
    service = build("sheets", "v4", credentials=creds)
    
    # 3. Create Sheet
    spreadsheet = {
        "properties": {
            "title": "Indeed Pipeline - Truncated (Jobs 26+)"
        }
    }
    sheet = service.spreadsheets().create(body=spreadsheet, fields="spreadsheetId,spreadsheetUrl").execute()
    sheet_id = sheet.get("spreadsheetId")
    sheet_url = sheet.get("spreadsheetUrl")
    
    # 4. Upload rows
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id, range="A1",
        valueInputOption="RAW", body={"values": new_rows}
    ).execute()
    
    # 5. Share so pipeline can read it via export URL
    try:
        drive_service = build("drive", "v3", credentials=creds)
        drive_service.permissions().create(
            fileId=sheet_id,
            body={"type": "anyone", "role": "reader"}
        ).execute()
    except Exception as e:
        print("Warning sharing:", e)
        
    print(f"SUCCESS!")
    print(f"Sheet URL: {sheet_url}")
    print(f"CSV URL: https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=0")

if __name__ == "__main__":
    main()
