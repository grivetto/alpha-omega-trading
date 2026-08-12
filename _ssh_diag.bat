@echo off
echo === ENV ===
whoami
echo USERPROFILE=%USERPROFILE%
echo HOME=%HOME%
echo HOMEDRIVE=%HOMEDRIVE% %HOMEPATH%
echo USERNAME=%USERNAME%
echo.
echo === .ssh locations ===
for %%D in ("%USERPROFILE%\.ssh" "C:\Users\sergio.grivetto\.ssh" "C:\Users\SERGIO~1.GRI\.ssh") do (
  if exist %%D (echo FOUND: %%D & dir %%D /b) else (echo missing: %%D)
)
echo.
echo === ssh config search ===
for %%F in ("%USERPROFILE%\.ssh\config" "C:\Users\sergio.grivetto\.ssh\config" "C:\Users\SERGIO~1.GRI\.ssh\config") do (
  if exist %%F (echo FOUND CONFIG: %%F & type %%F) else (echo no config: %%F)
)
