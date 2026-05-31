@echo off
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Не удалось установить зависимости. Проверьте подключение к интернету.
    pause
    exit /b 1
)
echo.
echo Зависимости установлены. Запуск: python main.py
pause
