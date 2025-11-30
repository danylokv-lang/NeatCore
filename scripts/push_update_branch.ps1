<#
Script: push_update_branch.ps1
Purpose: Create or update branch 'update' with all current changes and push to remote.
Usage:
  powershell -ExecutionPolicy Bypass -File scripts\push_update_branch.ps1 -RepoUrl "https://github.com/danylokv-lang/task-manager.git"
Parameters:
  -RepoUrl   Optional: GitHub HTTPS remote URL. If omitted tries existing remote.
#>
param(
  [string]$RepoUrl = ""
)

function Assert-GitInstalled {
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "Git not found. Install from https://git-scm.com/download/win or use 'winget install --id Git.Git -e'.";
    exit 1
  }
}

Assert-GitInstalled

# Move to repo root (script assumes it's executed from project root or anywhere inside)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Resolve-Path (Join-Path $scriptDir ".."))

# Initialize git if needed
if (-not (Test-Path .git)) {
  git init | Write-Host
  git branch -M main | Write-Host
  Write-Host "Initialized new git repository (main branch)."
}

# Detect existing remote
$existingRemote = (git remote 2>$null | Select-Object -First 1)
if (-not $existingRemote) {
  if (-not $RepoUrl) {
    Write-Error "No remote found and no -RepoUrl provided. Provide -RepoUrl parameter."; exit 1
  }
  git remote add origin $RepoUrl
  Write-Host "Added remote 'origin' -> $RepoUrl"
} elseif ($RepoUrl) {
  Write-Host "Remote already exists; ignoring provided -RepoUrl ($RepoUrl)."
}

# Ensure working tree clean or proceed
$status = git status --short
if ($status) {
  Write-Host "Uncommitted changes detected; they will be added." -ForegroundColor Yellow
}

# Create or switch to 'update' branch
$branches = git branch --list
if ($branches -match '\bupdate\b') {
  git switch update | Write-Host
  Write-Host "Switched to existing 'update' branch."
} else {
  git switch -c update | Write-Host
  Write-Host "Created and switched to new 'update' branch."
}

# Stage all changes (including deletions)
git add -A

# Commit (skip if nothing to commit)
$diffPending = git diff --cached --name-only
if (-not $diffPending) {
  Write-Host "No changes to commit on 'update' branch." -ForegroundColor Green
} else {
  $msg = "chore(update): latest UI, downloads, headers"
  git commit -m $msg | Write-Host
  Write-Host "Committed with message: $msg"
}

# Push branch (set upstream)
try {
  git push -u origin update | Write-Host
  Write-Host "Branch 'update' pushed to remote." -ForegroundColor Green
} catch {
  Write-Error "Push failed. Check remote permissions or network. $_"
  exit 1
}

Write-Host "Done. Next: Open PR or merge 'update' into 'main'." -ForegroundColor Cyan
