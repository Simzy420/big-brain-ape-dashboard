# Corrigo Invoice Processing — HARD CHECKS VERSION
**Based on:** CHECKPOINT_CURRENT_PROCESS.md
**Created:** 2026-10-26
**Purpose:** Add mandatory verification before any Submit. Refuse to submit if hours, material, or photo fail checks.

## Hard Check Rules (enforced)

### 1. Hours Check
- After filling Non Taxable Labor - Kevin Boyd line:
  - Read back the QTY field value.
  - Must exactly equal the hours string/number from JSON or Completed card.
  - If mismatch: STOP. Log "HOURS MISMATCH: expected {expected}, form shows {actual}". Take screenshot. Do not continue.

### 2. Material Check
- If data contains materials cost > 0:
  - Confirm a line with category containing "Non Taxable Material" exists.
  - QTY must be 1, Rate must equal the materials cost exactly.
  - If missing or wrong: STOP with "MATERIAL MISMATCH" + screenshot.
- If no materials cost in data:
  - Confirm no material line was added (or remove it if present).
  - If material line exists when none should: STOP.

### 3. Photo Check
- If WO photos array has any entry with non-empty url or data:
  - After upload attempt, verify Attachments section shows at least one file.
  - If no attachment visible: STOP with "PHOTO REQUIRED BUT NOT ATTACHED" + screenshot.
- Never submit without photo when one exists in source data.

### 4. Category Check
- Never leave any line category as "Please select" or blank.
- Verify both labor and (if present) material categories are correctly selected before proceeding.

### 5. Invoice Number Check
- Must not be 9999.
- Prefer invoiceNumber from JSON.

## Execution Flow
1. Load fresh JSON.
2. Confirm WO is in Completed tab and not already Sent In.
3. Open/create invoice.
4. Set dates and invoice #.
5. Fill labor line (exact hours).
6. **HARD CHECK: Hours**
7. Fill material line if required.
8. **HARD CHECK: Material**
9. Upload photo if required.
10. **HARD CHECK: Photo**
11. **HARD CHECK: Categories**
12. Only if ALL checks pass → Submit.
13. Confirm status = Submitted.
14. Screenshot → Drive folder "work order screenshot".
15. Email screenshot to caseylsims@gmail.com (subject: WO# + total).
16. Call moveToSentToCorrigo(woNumber) in the app.

## Failure Behavior
On any hard check failure:
- Do not click Submit.
- Capture screenshot of current form state.
- Report exact expected vs actual values.
- Stop processing that WO (continue to next only if explicitly allowed).

## Implementation Notes
- Use browser snapshot / evaluate to read field values back after filling.
- Prefer selectors that match the red-boxed fields from user screenshots (SERVICE DATE, INVOICE DATE, INVOICE #, labor QTY/RATE/AMOUNT, material, ATTACHMENTS, SUBMIT).
- Log every check result with timestamp.
