# Corrigo Invoice Processing Checkpoint
**Saved:** 2026-10-26
**Status:** Pre-hard-checks version (based on conversation rules)

## Source Data
- JSON: https://raw.githubusercontent.com/Simzy420/big-brain-ape-dashboard/main/corrigo-actions.json?v=TIMESTAMP
- App: https://simzy420.github.io/big-brain-ape-dashboard/corrigo-app.html
- Corrigo Desktop: https://am-desktop.corrigopro.com
- Login: Garysims60@msn.com (do not log password)

## Process Rules (Current)
ONLY process specified WOs. Skip if already in "Sent In to Corrigo" or status=submitted.

### Labor Line
- Category: "Non Taxable Labor - Kevin Boyd"
- QTY: EXACT hours from JSON or Completed card (no rounding)
- Rate: 30 (or from data)
- Description: blank or very short

### Material Line
- Only if materials cost listed in data
- Category: "Non Taxable Material"
- QTY: 1
- Rate: exact materials cost
- Description: blank
- NEVER put hours on material line
- NEVER leave category as "Please select"

### Photo
- Download from url or base64 data in JSON photos array
- Upload to Attachments if not already present
- DO NOT submit without photo if WO has one

### Invoice #
- Use invoiceNumber from JSON if exists
- Otherwise next available real number
- NEVER use 9999

### Other
- Service Date and Invoice Date from data
- Work description: do not overwrite if already filled
- After submit: screenshot to Google Drive 'work order screenshot' folder, email to caseylsims@gmail.com, call moveToSentToCorrigo(woNumber)

## Critical: Do not submit unless hours, material (if required), and photo all correct.
