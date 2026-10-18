<<<<<<< HEAD
# Grievance Triage Desk (Lite, with OCR)

Prototype for typed and scanned complaints using TF-IDF + Logistic Regression, Tesseract OCR, FastAPI, SQLite, and Streamlit.

## Architecture
- Dataset: CFPB-derived frozen Hugging Face Parquet snapshot `BEE-spoke-data/consumer-finance-complaints`, `has-text` config; label is `Product`.
- Model: word uni/bi-gram TF-IDF + class-weighted Logistic Regression; top-three class probabilities.
- OCR: Tesseract for image files; PyMuPDF renders PDF pages for OCR.
- API: POST/GET `/grievances`, PATCH `/grievances/{id}`, GET `/stats`.
- UI: Streamlit complaint registration and officer queue.
- Review: validation-selected classifier threshold, short-text check, and Tesseract confidence heuristic.

## Requirements
Python 3.10+, internet access on first training run to download the public dataset snapshot, and Tesseract installed locally.
Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
macOS: `brew install tesseract`
Windows: install Tesseract OCR and add its executable to PATH.

## Access and complaint status
Complainants can submit complaints and check status with the complaint ID and one-time tracking code returned at submission. Staff must sign in to view the officer queue, change the department, set a status (`pending`, `solved`, or `rejected`), and add a resolution note. Copy `.env.example` to `.env`, replace the staff placeholders with private credentials, and do not commit `.env`. The API loads this file at startup; Docker Compose also reads it automatically.

On Windows PowerShell, create the local environment file from the project directory:
```powershell
Copy-Item .env.example .env
```
Edit `.env` to set your staff username and password, then restart the API. The tracking code is shown only once; store it to check the complaint later.

## Run
1. `python -m venv .venv`
2. Activate it: `source .venv/bin/activate` (Windows: `.venv\\Scripts\\activate`)
3. `pip install -r requirements.txt`
4. `python -m scripts.train`
5. Start API with `uvicorn app.main:app --reload` and UI in another terminal with `streamlit run frontend/app.py`.

API docs: http://127.0.0.1:8001/docs; UI: http://localhost:8501.

## Run with Docker
Requires Docker Desktop with Compose and internet access for the first training run.

1.Build and start the application by running:
`docker compose up --build`

2.Open the website in your browser:
http://localhost:8501

3.Stop the application by pressing Ctrl+C in the terminal, then run:
`docker compose down`

4. Train the model if it is missing
If the application reports that `artifacts/router.joblib` cannot be found, train the model inside the running API container:
`docker compose exec -e PYTHONPATH=/app api python scripts/train.py`
If the API container is not running, start the services first:
`docker compose up -d --build`
Then run the training command above.
Refresh the frontend after training completes.

Open http://localhost:8501 for the UI and http://localhost:8001/docs for the API. The `artifacts` and `runtime` folders persist the model and SQLite database on the host.

Run OCR evaluation: `python -m scripts.evaluate_ocr`
Run tests: `pytest -q`

## Assumptions and limitations
- CFPB Product is a proxy label, not a state-government department taxonomy.
- Rare labels with fewer than 50 training examples are grouped into `Other / rare product`.
- Threshold selection maximizes validation coverage subject to at least 85% validation accuracy on auto-routed examples; if none qualifies, fallback threshold is 0.55.
- Logistic Regression confidence is not automatically calibrated.
- OCR confidence is an average of Tesseract word confidence values, not a calibrated probability.
- Officer correction updates final/corrected department while retaining original prediction.
- The dataset sample, database, OCR images, and trained artifacts are not committed.
- Training loads the CFPB-derived February 2024 `has-text` Parquet snapshot, shuffles it with the chosen seed, and takes up to the requested number of non-empty narratives with `Product` labels.

## AI tools
AI coding assistance was used to scaffold and review project structure, code, tests, and documentation. Review, run, debug, and understand every part before submission.
=======
# Grievance-Triage-Desk
>>>>>>> fe9805794d93b29d07b461da465818e68ae9e0e5
