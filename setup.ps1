$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PipCache = Join-Path $ProjectRoot ".pip-cache"
$ModelsDirectory = Join-Path $ProjectRoot "models"

py -3.14 --version
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.14 was not found. Install 64-bit Python 3.14 and enable the Python launcher, then run setup.ps1 again."
}

if (-not (Test-Path $Python)) {
    py -3.14 -m venv (Join-Path $ProjectRoot ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Could not create the virtual environment." }
}

& $Python -m pip install --cache-dir $PipCache --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Could not upgrade pip." }

& $Python -m pip install --cache-dir $PipCache -r (Join-Path $ProjectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

New-Item -ItemType Directory -Force -Path $ModelsDirectory | Out-Null
$Models = @(
    @{
        Name = "hand_landmarker.task"
        Url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
    },
    @{
        Name = "pose_landmarker_lite.task"
        Url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
    }
)
foreach ($Model in $Models) {
    $ModelPath = Join-Path $ModelsDirectory $Model.Name
    if (-not (Test-Path $ModelPath)) {
        Invoke-WebRequest -Uri $Model.Url -OutFile $ModelPath
        if ($LASTEXITCODE -ne 0) { throw "Could not download model: $($Model.Name)" }
    }
}

Write-Host "Setup complete. Environment: $Python"
Write-Host "Package cache: $PipCache"
Write-Host "Model files: $ModelsDirectory"
Write-Host "Start the dry run with .\run.ps1"
