@echo off
set "OLLAMA_MODELS=%~dp0ollama\models"
set "OLLAMA_HOST=127.0.0.1:11434"
"%~dp0ollama\ollama.exe" %*
