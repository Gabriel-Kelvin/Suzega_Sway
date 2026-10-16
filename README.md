# Sway — AI Workload Assessment

One question: **will a proposed AI integration reduce human workload or create more checking, corrections, and maintenance?**

The app has one page: describe the current work and proposed AI change, review the assumptions, then calculate the impact. There is no Cases, Setup, Review, or Planning Lab navigation.

## Run locally

```powershell
cd 'D:\AI\AI Projects\Suzega'
.\start.ps1
```

Open http://127.0.0.1:5173. Use `start.ps1 -NoBrowser` to start without opening a browser, and `stop.ps1` to stop the recorded services. Services bind to localhost.

## Try it

1. Click **Try a support-team example**.
2. Click **Analyze AI impact**. Groq reads the actual descriptions, identifies remaining work and added work, and proposes editable inputs. Unknown values are scenario assumptions, listed for review.
3. Check the numbers, then click **Calculate workload impact**.
4. For the supplied example, expect 250 human hours/week today, 197 with AI, and 53 hours/week potentially freed.
5. Change **Checking each AI item (min)** from 3 to 10 and calculate again. Expect about 290.3 hours/week with AI: workload increases by about 40.3 hours.
6. Restore checking to 3 and recalculate. Click **Download assessment (PDF)** for a formatted report containing descriptions, source report names, reviewed inputs, computed totals, break-even, sensitivity, assumptions, risks, pilot steps, and method.

Changing numeric inputs does not call the LLM again. Changing descriptions requires another analysis, clearly marked in the UI. Assessments stay in the current browser session unless downloaded; there is no saved-runs module.

### PDF reports as input

Attach up to three text-based PDFs, each at most 10 pages, 5 MB, and 40,000 extracted characters (60,000 combined). You can leave the text fields empty if a report describes both the current work and proposed AI feature. Preview the extracted text before analyzing. Text is extracted by the backend and sent to Groq only when Analyze is clicked. Password-protected, scanned/image pages, corrupt files, and over-limit reports return explicit errors rather than being silently truncated. OCR is not included. Model analysis should reference document names/pages where possible; interpretation still needs review.

The exported PDF is recomputed on the server from the reviewed inputs, so client-supplied totals cannot alter its verdict.

## How it works

- `backend/app/assessment.py`: typed inputs, real Groq analysis, workload calculation.
- `frontend/src/App.tsx`: the single assessment flow.
- `frontend/src/assessment.css`: responsive interface.
- `backend/app/main.py`: `/api/assessment/analyze` and `/api/assessment/calculate`.

**Weekly human effort after AI** equals unchanged items × original time, plus AI-assisted items × (remaining original work + added checking + correction rate × correction time), plus weekly monitoring and maintenance. Minutes are converted to hours. Demand stays equal. One-time setup effort is kept separate from recurring workload.

The result shows weekly workload before/after, work added and removed, review-time break-even, setup payback, and sensitivity to checking/correction time. Sensitivity scenarios are not confidence intervals. These are conditional human-effort estimates, not measurements of quality, elapsed waiting time, costs, headcount or payroll savings. Validate with a measured pilot.

Groq generates the process analysis and proposed assumptions. Python calculates all workload totals and the increase/decrease verdict. The UI does not invent a decision when the provider fails.

## Configuration

Set `GROQ_API_KEY` in the ignored server `.env` file. The default model is `openai/gpt-oss-120b`; the existing model allowlist and local cap of 30 attempts per UTC day remain. No key is shipped to the frontend. Descriptions are sent to Groq when Analyze is clicked. No Supabase is required. Deployment uses one free Render web service.

For a fresh installation, use Python 3.11+ and Node 20.19+ or 22.12+:

```powershell
uv venv .venv --python 3.11
uv pip sync --python .venv/Scripts/python.exe backend/requirements.lock.txt
Copy-Item .env.example .env
cd frontend
npm ci
cd ..
.\start.ps1
```

Without uv, create a venv and install `backend/requirements.lock.txt` with pip.

## Verification

```powershell
.venv/Scripts/python.exe -m pytest backend/tests -q
cd frontend
npm run build
```

80 backend tests pass, including workload arithmetic, real-description boundaries, report parsing, file limits, and PDF export tests. Existing legacy backend data and endpoints are retained for compatibility; their interfaces are not imported into the active app. The actual browser flow was checked using Groq, including a change from workload reduction to workload increase.

## Render deployment

`Dockerfile` builds React with Node and serves its assets from the Python FastAPI server. Render runs `app.server:app`, which exposes only the workload API and website. Legacy simulator/case routes are not registered in this public server.

- Plan: free, region: Singapore.
- Blueprint: `render.yaml`; server binds to `0.0.0.0:$PORT`.
- Set `GROQ_API_KEY` as a Render environment secret. Never commit `.env`.
- Health check: `/api/health`.
- PDF fonts: DejaVu, installed in the Linux image.
- Uploaded report bytes/text are processed in memory, not retained as a document archive. Browser state disappears on refresh; download the PDF before leaving.
- The free service sleeps after inactivity. The local SQLite request counter is ephemeral and resets when the container is replaced. Groq's own account limits still apply; this counter is not durable billing protection.
- No database, disk, login, or Supabase service is provisioned.

For local production-mode verification after building the frontend:

```powershell
.venv/Scripts/python.exe -m uvicorn app.server:app --app-dir backend --host 127.0.0.1 --port 8001
```
