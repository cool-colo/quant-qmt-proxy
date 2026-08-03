@echo off
chcp 65001 >nul

set BASE_DIR=D:\code\quant-qmt-proxy
set LOG_DIR=%BASE_DIR%\logs

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set TODAY=%date:~0,4%%date:~5,2%%date:~8,2%

set TASK_LOG=%LOG_DIR%\task_%TODAY%.log
set RUN_LOG=%LOG_DIR%\run_%TODAY%.log


echo ====================================== >> "%TASK_LOG%"
echo [%date% %time%] restart start >> "%TASK_LOG%"


cd /d "%BASE_DIR%"


echo [%date% %time%] killing old process >> "%TASK_LOG%"

for /f "tokens=5" %%i in ('netstat -ano ^| findstr :8000') do (
    echo kill pid %%i >> "%TASK_LOG%"
    taskkill /f /pid %%i >> "%TASK_LOG%" 2>&1
)


timeout /t 2 /nobreak >nul

set "PYTHONPATH=D:\code\xtquant_big_convert\src;%PYTHONPATH%"
set APP_MODE=dev
set APP_SERVERS=all


echo [%date% %time%] starting python >> "%TASK_LOG%"


start "" /b "C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe" run.py >> "%RUN_LOG%" 2>&1


timeout /t 5 /nobreak >nul


netstat -ano | findstr :8000 >nul

if %errorlevel% equ 0 (
    echo [%date% %time%] service started OK >> "%TASK_LOG%"
) else (
    echo [%date% %time%] service start FAILED >> "%TASK_LOG%"
)


echo [%date% %time%] restart finished >> "%TASK_LOG%"
echo ====================================== >> "%TASK_LOG%"


