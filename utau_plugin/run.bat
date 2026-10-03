@echo off
python -m utau_lyrics_mcp.plugin "%~1" "%~dp0settings.ini"
if errorlevel 1 pause
