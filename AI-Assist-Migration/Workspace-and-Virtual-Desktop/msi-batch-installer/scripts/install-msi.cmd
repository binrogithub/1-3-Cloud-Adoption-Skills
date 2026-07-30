@echo off
REM ============================================================
REM  install-msi.cmd - MSI Batch Installer (CMD)
REM  Installs all .msi files in a directory (or specific files)
REM
REM  Usage:
REM    install-msi.cmd                      Install all .msi in current dir
REM    install-msi.cmd "C:\Packages"        Install all .msi in C:\Packages
REM    install-msi.cmd app1.msi app2.msi    Install specific files
REM ============================================================

setlocal enabledelayedexpansion

REM --- Configuration ---
set "LOGDIR=%TEMP%\msi-install-logs"
set "UI_MODE=/qn"
set "EXTRA_PROPS="
set "CONTINUE_ON_ERROR=1"

REM --- Prepare log directory ---
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

REM --- Build timestamp ---
set "TIMESTAMP=!date:~10,4!!date:~4,2!!date:~7,2!_!time:~0,2!!time:~3,2!!time:~6,2!"
set "TIMESTAMP=!TIMESTAMP: =0!"
set "TIMESTAMP=!TIMESTAMP:/=!"
set "TIMESTAMP=!TIMESTAMP::=!"

REM --- Collect MSI files ---
set "MSI_COUNT=0"
set "MSI_LIST="

if "%~1"=="" (
    REM No args - scan current directory
    for %%f in (*.msi) do (
        set /a MSI_COUNT+=1
        set "MSI_LIST=!MSI_LIST! %%f"
    )
) else (
    REM Process arguments
    :parse_args
    if "%~1"=="" goto :args_done
    if exist "%~1\*" (
        REM Directory - collect .msi files
        for %%f in ("%~1\*.msi") do (
            set /a MSI_COUNT+=1
            set "MSI_LIST=!MSI_LIST! %%~fnxf"
        )
    ) else if exist "%~1" (
        REM File - add directly
        set /a MSI_COUNT+=1
        set "MSI_LIST=!MSI_LIST! %~1"
    ) else (
        echo [WARN] Path not found: %~1
    )
    shift
    goto :parse_args
    :args_done
)

if !MSI_COUNT! equ 0 (
    echo No .msi files found.
    exit /b 1
)

REM --- Header ---
echo.
echo ======================================================================
echo   MSI Batch Installer ^(CMD^)
echo   Files   : !MSI_COUNT!
echo   UI mode : !UI_MODE!
echo   Log dir : %LOGDIR%
echo ======================================================================
echo.

REM --- Install loop ---
set "INDEX=0"
set "SUCCESS_COUNT=0"
set "FAILED_COUNT=0"

for %%f in (!MSI_LIST!) do (
    set /a INDEX+=1
    set "MSI_NAME=%%~nxf"
    set "MSI_BASE=%%~nf"
    set "MSI_BASE=!MSI_BASE:.=_!"
    set "LOG_PATH=%LOGDIR%\!MSI_BASE!_!TIMESTAMP!.log"

    echo [!INDEX!/!MSI_COUNT!] Installing: !MSI_NAME!
    echo        Log: !LOG_PATH!

    msiexec /i "%%f" !UI_MODE! /norestart /L*V "!LOG_PATH!" !EXTRA_PROPS!
    set "EXIT_CODE=!ERRORLEVEL!"

    REM --- Decode exit code ---
    call :decode_exit !EXIT_CODE!

    if !EXIT_CODE! equ 0 (
        echo        Result: !EXIT_MSG! ^(!EXIT_CODE!^)
        set /a SUCCESS_COUNT+=1
    ) else if !EXIT_CODE! equ 3010 (
        echo        Result: !EXIT_MSG! ^(!EXIT_CODE!^)
        set /a SUCCESS_COUNT+=1
    ) else (
        echo        Result: !EXIT_MSG! ^(!EXIT_CODE!^)
        set /a FAILED_COUNT+=1
        if "!CONTINUE_ON_ERROR!"=="0" (
            echo.
            echo   [!] Stopping - continue_on_error is 0.
            goto :summary
        )
    )
    echo.
)

goto :summary

REM --- Exit code decoder ---
:decode_exit
    if %1 equ 0    set "EXIT_MSG=Success"
    if %1 equ 1602 set "EXIT_MSG=User cancelled"
    if %1 equ 1603 set "EXIT_MSG=Fatal error"
    if %1 equ 1618 set "EXIT_MSG=Another install running"
    if %1 equ 1619 set "EXIT_MSG=MSI file not found/corrupt"
    if %1 equ 1625 set "EXIT_MSG=System policy blocks install"
    if %1 equ 1638 set "EXIT_MSG=Different version installed"
    if %1 equ 3010 set "EXIT_MSG=Success - reboot required"
    if not defined EXIT_MSG set "EXIT_MSG=Unknown error: %1"
    goto :eof

:summary
echo ======================================================================
echo   Summary
echo ======================================================================
echo   Total: !INDEX!  ^|  Success: !SUCCESS_COUNT!  ^|  Failed: !FAILED_COUNT!
echo   Logs:  %LOGDIR%
echo.

if !FAILED_COUNT! gtr 0 exit /b 1
exit /b 0
