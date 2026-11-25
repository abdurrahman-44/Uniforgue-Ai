# Launch UNIFORGE AI Backend & Frontend locally on Windows
Write-Host "Starting UNIFORGE AI Backend on http://localhost:8000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..\backend'; .\.venv\Scripts\alembic.exe upgrade head; .\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000"

Write-Host "Starting UNIFORGE AI Frontend on http://localhost:3000 ..." -ForegroundColor Magenta
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..\frontend'; npm run dev"

Write-Host "UNIFORGE AI launching! API Docs: http://localhost:8000/api/docs | Web App: http://localhost:3000" -ForegroundColor Green
