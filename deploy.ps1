# One-shot Cloud Run deploy for MonsoonMitra.ai (PowerShell).
# Prereqs: gcloud installed + authenticated, APIs enabled, $env:GEMINI_API_KEY set for the first run.
param(
    [string]$Project = "project-7dd8dd18-ed36-467b-a8c",
    [string]$Region = "asia-south1",
    [string]$Service = "monsoonmitra",
    [string]$Model = "gemini-3.5-flash",
    [string]$FallbackModel = "gemini-2.5-flash"
)

$ErrorActionPreference = "Stop"

# 1. Secret (create once; add a new version on re-runs)
$secretName = "monsoonmitra-gemini-key"
$exists = gcloud secrets describe $secretName --project $Project 2>$null
if (-not $exists) {
    if (-not $env:GEMINI_API_KEY) { Write-Error "Set `$env:GEMINI_API_KEY before first deploy."; exit 1 }
    $tmp = New-TemporaryFile
    [IO.File]::WriteAllText($tmp.FullName, $env:GEMINI_API_KEY)
    gcloud secrets create $secretName --data-file=$tmp.FullName --project $Project
    Remove-Item $tmp.FullName
}

# 2. Firebase web config (public identifiers) - fetched live so nothing is hard-coded
$token = gcloud auth print-access-token
$apps = Invoke-RestMethod -Uri "https://firebase.googleapis.com/v1beta1/projects/$Project/webApps" -Headers @{Authorization = "Bearer $token"}
if (-not $apps.apps) {
    Write-Output "No Firebase web app found - creating one..."
    Invoke-RestMethod -Method Post -Uri "https://firebase.googleapis.com/v1beta1/projects/$Project/webApps" -Headers @{Authorization = "Bearer $token"} -ContentType "application/json" -Body '{"displayName":"MonsoonMitra Web"}' | Out-Null
    Start-Sleep -Seconds 10
    $apps = Invoke-RestMethod -Uri "https://firebase.googleapis.com/v1beta1/projects/$Project/webApps" -Headers @{Authorization = "Bearer $token"}
}
$appId = $apps.apps[0].appId
$cfg = Invoke-RestMethod -Uri "https://firebase.googleapis.com/v1beta1/projects/$Project/webApps/$appId/config" -Headers @{Authorization = "Bearer $token"}
Write-Output "Firebase web app: $appId"

# 3. Deploy from source
$envVars = "AUTH_REQUIRED=true,GEMINI_MODEL=$Model,GEMINI_MODEL_FALLBACK=$FallbackModel,FIREBASE_PROJECT_ID=$Project,FIREBASE_WEB_API_KEY=$($cfg.apiKey),FIREBASE_AUTH_DOMAIN=$($cfg.authDomain),FIREBASE_APP_ID=$appId"
gcloud run deploy $Service --source . --region $Region --project $Project `
    --allow-unauthenticated --memory 1Gi `
    --set-env-vars $envVars `
    --set-secrets "GEMINI_API_KEY=${secretName}:latest"

# 4. Least-privilege IAM for the runtime service account
$sa = gcloud run services describe $Service --region $Region --project $Project --format 'value(spec.template.spec.serviceAccountName)'
if (-not $sa) { $pn = gcloud projects describe $Project --format 'value(projectNumber)'; $sa = "$pn-compute@developer.gserviceaccount.com" }
gcloud projects add-iam-policy-binding $Project --member="serviceAccount:$sa" --role="roles/datastore.user" --condition=None | Out-Null
gcloud secrets add-iam-policy-binding $secretName --member="serviceAccount:$sa" --role="roles/secretmanager.secretAccessor" --project $Project | Out-Null

# 5. Smoke test
$url = gcloud run services describe $Service --region $Region --project $Project --format 'value(status.url)'
Write-Output "Service URL: $url"
Invoke-RestMethod -Uri "$url/api/healthz" | ConvertTo-Json -Compress
