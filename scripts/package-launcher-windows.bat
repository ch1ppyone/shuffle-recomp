@echo off
setlocal
set "ROOT=%~dp0.."
python -m pip install -r "%ROOT%\launcher\requirements.txt"
python "%ROOT%\scripts\make-icons.py"
cmake -S "%ROOT%" -B "%ROOT%\build-win" -G Ninja -DCMAKE_BUILD_TYPE=Release -DDREAM_RENDERER=ON -DDREAMCOMP_FRONTEND=OFF -DDREAM_BUILD_TESTS=OFF -DDREAM_WERROR=OFF
if errorlevel 1 exit /b %errorlevel%
cmake --build "%ROOT%\build-win" --parallel
if errorlevel 1 exit /b %errorlevel%
if "%CDIRIP%"=="" set "CDIRIP=%ROOT%\.deps\cdirip\cdirip.exe"
if not exist "%CDIRIP%" call "%ROOT%\scripts\build-cdirip.bat"
if not exist "%CDIRIP%" (
  echo Build cdirip from third_party\cdirip with the Visual Studio or MinGW compiler first.
  exit /b 1
)
python "%ROOT%\launcher\package.py" --game "%ROOT%\build-win\game\sonic-shuffle-recomp.exe" --cdirip "%CDIRIP%"
