@echo off
setlocal
cd /d "%~dp0frontend"
set "UNI_INPUT_DIR=%CD%"
set "UNI_OUTPUT_DIR=%CD%\unpackage\dist\dev\mp-weixin-mobile"
if not defined HX_APP_ROOT set "HX_APP_ROOT=F:\HBuilderX"
set "UNI_CLI_CONTEXT=%HX_APP_ROOT%\plugins\uniapp-cli-vite"
node "%UNI_CLI_CONTEXT%\node_modules\@dcloudio\vite-plugin-uni\bin\uni.js" build -p mp-weixin --config "%UNI_CLI_CONTEXT%\vite.config.js"
