@echo off
setlocal

for %%I in ("%~dp0..\..") do set "OBSIDIAN_VAULT_PATH=%%~fI"
set "OPENAI_API_KEY="
set "OPENAI_BASE_URL="
set "OPENAI_EMBEDDING_MODEL="
set "LOCAL_EMBEDDING_MODEL=Xenova/multilingual-e5-small"

where node.exe >nul 2>nul
if errorlevel 1 (
  echo [obsidian-hybrid-search] node.exe is not available on PATH. 1>&2
  exit /b 1
)

for /f "delims=" %%I in ('npm.cmd root -g') do set "NPM_GLOBAL_ROOT=%%I"
set "SERVER_JS=%NPM_GLOBAL_ROOT%\obsidian-hybrid-search\dist\src\server.js"

if not exist "%SERVER_JS%" (
  echo [obsidian-hybrid-search] MCP server is not installed. 1>&2
  echo Install it with: npm install -g obsidian-hybrid-search 1>&2
  exit /b 1
)

node "%SERVER_JS%"
