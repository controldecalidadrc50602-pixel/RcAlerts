@echo off
title Compilando OmniPulse a .EXE
echo ========================================================
echo   Empaquetando OmniPulse Intelligence Hub a OmniPulse.exe
echo ========================================================
"C:\Users\Marilyn\AppData\Local\Programs\Python\Python313\python.exe" -m PyInstaller --noconfirm --onedir --name "OmniPulse" --add-data "static;static" --hidden-import="uvicorn.logging" --hidden-import="uvicorn.loops" --hidden-import="uvicorn.loops.auto" --hidden-import="uvicorn.protocols" --hidden-import="uvicorn.protocols.http" --hidden-import="uvicorn.protocols.http.auto" --hidden-import="uvicorn.protocols.websockets" --hidden-import="uvicorn.protocols.websockets.auto" --hidden-import="uvicorn.lifespan" --hidden-import="uvicorn.lifespan.on" launcher.py
echo.
echo ========================================================
echo   COMPILACION COMPLETADA CON EXITO!
echo   El ejecutable se encuentra en: dist\OmniPulse\OmniPulse.exe
echo ========================================================
pause
