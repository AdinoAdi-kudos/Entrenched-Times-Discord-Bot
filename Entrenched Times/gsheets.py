import gspread
from google.oauth2.service_account import Credentials

scopes = [
    "https://www.googleapis.com/auth/spreadsheets"
]

creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
client = gspread.authorize(creds)

sheet_id = "1TrRcRrto0p_eSyG7wbZFr3v54H5GbCtHeXSJcTHQ6aU"
workbook = client.open_by_key(sheet_id)

sheets = workbook.sheet1

records = sheets.get_all_records()

for record in records:
    print(record)