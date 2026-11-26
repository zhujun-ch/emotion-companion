@echo off
cd /d "%~dp0frontend"
set "UNI_INPUT_DIR=%~dp0frontend"
set "UNI_OUTPUT_DIR=%~dp0frontend\unpackage\dist\dev\h5"
if not defined HX_APP_ROOT set "HX_APP_ROOT=F:\HBuilderX"
set "UNI_CLI_CONTEXT=%HX_APP_ROOT%\plugins\uniapp-cli-vite"
set "UNI_PLATFORM=h5"
if not exist "node_modules" mklink /J "node_modules" "%UNI_CLI_CONTEXT%\node_modules" >nul
if not exist "node_modules\@dcloudio\uni-components\package.json" exit /b 1
node "%UNI_CLI_CONTEXT%\node_modules\@dcloudio\vite-plugin-uni\bin\uni.js" --config "%UNI_CLI_CONTEXT%\vite.config.js" --host 127.0.0.1 --port 5173 --strictPort
