import json
import os
import gspread

from oauth2client.service_account import ServiceAccountCredentials

cred_json = json.loads(
    os.environ["GOOGLE_CREDENTIALS"]
)

with open("cred.json", "w") as f:
    json.dump(cred_json, f)

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    "cred.json",
    scope
)

client = gspread.authorize(creds)

sheet = client.open_by_key(
    os.environ["SHEET_ID"]
)

aba = sheet.worksheet("Base_Mensal")

aba.append_row([
    "2026",
    "Teste",
    "1",
    "1",
    "0",
    "1",
    "0"
])

print("Funcionou!")
