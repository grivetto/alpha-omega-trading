@echo off
echo === powershell ssh -V ===
powershell -NoProfile -Command "$OutputEncoding = [System.Text.Encoding]::UTF8; & ssh -V 2>&1 | Out-String; Write-Output ('PS_EXIT=' + $LASTEXITCODE)"
echo.
echo === HOME set, ssh -V ===
set HOME=C:\Users\sergio.grivetto
ssh -V
echo exit=%errorlevel%
echo.
echo === ssh-agent list ===
powershell -NoProfile -Command "& ssh-add -L 2>&1 | Out-String; Write-Output ('AGENT_EXIT=' + $LASTEXITCODE)"
