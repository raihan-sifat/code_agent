@echo off
setlocal
echo ============================================
echo   Building CodeAgent.exe
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo Python not found on PATH. Aborting.
    goto :end
)

echo Bundling CustomTkinter assets and dependencies...
echo.

python -m PyInstaller --noconfirm --onefile --windowed ^
    --name "CodeAgent" ^
    --collect-all "customtkinter" ^
    --hidden-import "tkinter" ^
    --hidden-import "openai" ^
    main.py

echo.
if exist dist\CodeAgent.exe (
    echo Build successful! Executable: dist\CodeAgent.exe
) else (
    echo Build failed. Check the output above for errors.
)

:end
echo.
pause
endlocal
