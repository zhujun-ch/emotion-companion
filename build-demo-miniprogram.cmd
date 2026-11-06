@echo off
setlocal
cd /d "%~dp0frontend"
set "UNI_INPUT_DIR=%CD%"
if not defined HX_APP_ROOT set "HX_APP_ROOT=F:\HBuilderX"
set "UNI_CLI_CONTEXT=%HX_APP_ROOT%\plugins\uniapp-cli-vite"
for /f %%I in ('powershell.exe -NoProfile -Command "[guid]::NewGuid().ToString('N').Substring(0,8)"') do set "XINYU_BUILD_ID=%%I"
if not defined XINYU_BUILD_ID exit /b 1
set "XINYU_BUILD_NAME=mp-weixin-mobile-%XINYU_BUILD_ID%"
set "UNI_OUTPUT_DIR=%CD%\unpackage\dist\dev\%XINYU_BUILD_NAME%"
node "%UNI_CLI_CONTEXT%\node_modules\@dcloudio\vite-plugin-uni\bin\uni.js" build -p mp-weixin --config "%UNI_CLI_CONTEXT%\vite.config.js"
if errorlevel 1 exit /b %ERRORLEVEL%
if not exist "%UNI_OUTPUT_DIR%\app.json" exit /b 1
set "XINYU_PROJECT_CONFIG=%~dp0project.config.json"
if exist "%XINYU_PROJECT_CONFIG%" (
    powershell.exe -NoProfile -Command "$ErrorActionPreference = 'Stop'; $project = Get-Content -LiteralPath $env:XINYU_PROJECT_CONFIG -Raw -Encoding UTF8 | ConvertFrom-Json; $project | Add-Member -Force -NotePropertyName miniprogramRoot -NotePropertyValue ('frontend/unpackage/dist/dev/' + $env:XINYU_BUILD_NAME + '/'); [IO.File]::WriteAllText($env:XINYU_PROJECT_CONFIG, ($project | ConvertTo-Json -Depth 20), (New-Object System.Text.UTF8Encoding($false)))"
    if errorlevel 1 exit /b 1
)
echo WeChat demo build: %UNI_OUTPUT_DIR%
