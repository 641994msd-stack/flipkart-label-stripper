@echo off
setlocal
cd /d "%~dp0"
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
py -m PyInstaller --noconfirm --clean --onefile --windowed --name Flipkart_Splitter flipkart_splitter.py
echo.
echo Build complete. EXE is in the dist folder.
pause
