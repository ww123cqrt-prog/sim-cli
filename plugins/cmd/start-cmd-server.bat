@echo off
REM CMD Server 启动脚本（带安全功能）
REM 用法: start-cmd-server.bat [端口] [用户名] [密码] [超时秒数]

set PORT=%1
set USERNAME=%2
set PASSWORD=%3
set TIMEOUT=%4

if "%PORT%"=="" set PORT=7602
if "%USERNAME%"=="" set USERNAME=admin
if "%PASSWORD%"=="" set PASSWORD=changeme
if "%TIMEOUT%"=="" set TIMEOUT=600

echo ========================================
echo   CMD Server 启动
echo ========================================
echo   端口: %PORT%
echo   用户名: %USERNAME%
echo   超时: %TIMEOUT% 秒
echo ========================================
echo.

REM 启动服务器（带认证和超时）
python -m sim serve --port %PORT% --host 0.0.0.0 --username %USERNAME% --password %PASSWORD% --timeout %TIMEOUT% --require-confirm

pause
