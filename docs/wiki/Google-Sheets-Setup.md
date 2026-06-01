# Google Sheets Setup

The Google Sheet is the bot's backend. There is no separate database.

## 1. Create a Google Sheet

1. Open Google Sheets.
2. Create a blank spreadsheet.
3. Copy the long ID from the URL.

Example:

```text
https://docs.google.com/spreadsheets/d/THIS_IS_THE_SHEET_ID/edit
```

Put that value into `SHEET_ID`.

## 2. Create a Google Cloud project

1. Open Google Cloud Console.
2. Create a new project.
3. Enable Google Sheets API.
4. Enable Google Drive API.

Both APIs are needed so the bot can open and write to the spreadsheet.

## 3. Create a service account

1. Go to IAM and Admin.
2. Open Service Accounts.
3. Create a service account.
4. Create a JSON key.
5. Download the file as `credentials.json`.

## 4. Share the Sheet with the service account

Open `credentials.json` and find `client_email`.

It looks like:

```text
something@project-id.iam.gserviceaccount.com
```

Share your Google Sheet with that email as Editor.

This step is required. If you skip it, the bot can start but cannot write to the Sheet.

## 5. Railway credential format

For Railway, paste the JSON into `GOOGLE_CREDS_JSON` as one line.

For VPS or local development, you can keep the file on disk and set:

```env
GOOGLE_CREDS=credentials.json
```

## 6. Sheet tabs

You do not need to create tabs manually. The bot creates them on first use.

Expected tabs include:

| Tab | Purpose |
|---|---|
| `Đầu ra` | Transactions |
| `Accounts` | Tracked bank/cash accounts |
| `Account Ledger` | Append-only balance ledger |
| `Pending Accounts` | Account onboarding queue |
| `Budget Config` | Monthly budget settings |
| `Sub-category Config` | Optional subcategory labels |
| `Keyword Rules` | Auto-categorization rules |
| `Bot State` | Telegram/Zalo wizard + picker state |
| `Monthly Reports` | Archived monthly reports |

