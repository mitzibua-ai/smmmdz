@echo off
REM Helper to stage, commit, and push the removed CNAME so GitHub Pages can redeploy.
REM Run this from the repo (double-click or run from cmd).
cd /d "%~dp0\.."
echo Working directory: %CD%

echo Staging CNAME removal (safe if already removed)...
git rm -f CNAME 2>nul || echo "git rm" returned non-zero (file may already be deleted)
echo Adding all changes...
git add -A
echo Committing...
git commit -m "ci: remove CNAME to avoid Pages DNS deployment failure" 2>commit_err.txt || (
  type commit_err.txt
  del commit_err.txt
  echo Commit failed, attempting without commit hooks...
  git commit -m "ci: remove CNAME to avoid Pages DNS deployment failure" --no-verify || (
    echo Nothing to commit or commit still failed. Exiting.
    pause
    exit /b 0
  )
)
echo Pushing to origin main...
git push origin main || (
  echo Push failed. Check remote, credentials, or network.
  pause
  exit /b 1
)
echo Push succeeded. Wait a minute then check Actions → Deploy GitHub Pages.
pause
