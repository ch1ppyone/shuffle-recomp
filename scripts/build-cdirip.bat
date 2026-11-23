@echo off
setlocal
set "ROOT=%~dp0.."
set "OUT=%~1"
if "%OUT%"=="" set "OUT=%ROOT%\.deps\cdirip"
if not exist "%OUT%" mkdir "%OUT%"
where gcc >nul 2>nul
if errorlevel 1 (
  echo A C compiler is required. Install MinGW-w64 or use Visual Studio and set CC.
  exit /b 1
)
gcc -O2 -std=c99 -D_WIN32 -I"%ROOT%\third_party\cdirip" "%ROOT%\third_party\cdirip\cdirip.c" "%ROOT%\third_party\cdirip\buffer.c" "%ROOT%\third_party\cdirip\cdi.c" "%ROOT%\third_party\cdirip\common.c" "%ROOT%\third_party\cdirip\audio.c" -o "%OUT%\cdirip.exe"
if errorlevel 1 exit /b %errorlevel%
echo Built: %OUT%\cdirip.exe
