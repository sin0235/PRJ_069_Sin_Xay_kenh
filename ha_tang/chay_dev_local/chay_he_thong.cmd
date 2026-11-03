@echo off
REM Bam dup de khoi dong toan bo he thong dev local (them -Dung de dung, -SuaLLM de sua dia chi LLM).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0chay_he_thong.ps1" %*
pause
