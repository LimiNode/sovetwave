@echo off
setlocal

for %%I in ("%~dp0..\..") do set "OBSIDIAN_VAULT_PATH=%%~fI"

where node.exe >nul 2>nul
if errorlevel 1 (
  echo [obsidian-hybrid-search] node.exe is not available on PATH. 1>&2
  exit /b 1
)

for /f "delims=" %%I in ('npm.cmd root -g') do set "NPM_GLOBAL_ROOT=%%I"
set "CLI_JS=%NPM_GLOBAL_ROOT%\obsidian-hybrid-search\dist\src\cli.js"

if not exist "%CLI_JS%" (
  echo [obsidian-hybrid-search] CLI is not installed. 1>&2
  echo Install it with: npm install -g obsidian-hybrid-search 1>&2
  exit /b 1
)

node "%CLI_JS%" %*
exit /b %ERRORLEVEL%
