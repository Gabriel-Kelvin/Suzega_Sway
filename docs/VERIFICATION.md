# Sway workload assessment — verification

The current interface is one assessment page: Describe → Check assumptions → See impact. Cases, Setup, Review, Planning Lab, Compare and Saved Runs are absent from the active UI.

- 72 backend tests pass, including 16 new workload analysis/calculation/API tests.
- TypeScript and the production build pass.
- Real Groq analysis extracted the support-team example into 1,000 weekly items, 80% adoption, original tasks of 10 and 5 minutes, residual tasks of 2 and 5 minutes, 3-minute additional review, 20% extra corrections at 4 minutes, 3 weekly overhead hours and 40 setup hours.
- Browser → API calculation returned 250 human hours/week today, 197 after AI, and 53 freed under those assumptions.
- Editing review time to 10 minutes, without another model call, returned 290.3 hours/week and 40.3 added hours. The verdict changed to workload increase.
- Downloaded the assessment through the browser and verified actual descriptions, edited inputs, result and model metadata in the JSON file.
- Desktop and mobile widths checked; no horizontal document overflow.
- The server-side Groq key stays in the ignored .env. No Supabase or deployment change.

The estimates concern recurring active human effort at equal demand, with setup effort shown separately. They do not establish real productivity, quality, payroll savings, or elapsed queue times. Sensitivity scenarios vary checking/correction time; they are not confidence intervals. Assessments must be downloaded to preserve them across browser reloads.

A Starlette/httpx deprecation warning remains in the passing test suite.

## PDF input and export extension

- 80 backend tests pass. PDF cases cover all-page extraction, page markers, blank/scanned pages, encrypted PDFs, invalid bytes, size/page limits, API handling and server-recomputed export totals.
- Uploaded a three-page PDF using the browser file chooser, left both descriptions empty, ran actual Groq analysis, calculated 250 hours/week today and 197 after AI, and downloaded the PDF through the browser.
- The PDF includes sources, reviewed inputs, task breakdown, workload totals, break-even, sensitivity, original assumptions, pilot steps and method. Every page was rendered and visually inspected after typography and pagination corrections.
- TypeScript and production build pass. No OCR is included; the UI states text-based PDF, 10 pages / 5 MB each, up to three reports.
