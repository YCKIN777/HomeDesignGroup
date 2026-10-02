@echo off
chcp 65001 >nul
setlocal
set "tempDir=%TEMP%"
set "srcCost=%tempDir%\cost_summary.xlsx"
set "srcMaterial=%tempDir%\material_procurement.xlsx"
set "dstDir=H:\AgentProjects\HomeDesignGroup\output"

if not exist "%dstDir%" mkdir "%dstDir%"

copy "%srcCost%" "%dstDir%\" /Y
copy "%srcMaterial%" "%dstDir%\" /Y

echo.
echo ✅ 文件复制完成，文件存放目录：%dstDir%
endlocal
