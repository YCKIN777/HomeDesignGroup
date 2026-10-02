# 家装 AI 智能体平台 · 一键启动（阶段1骨架版）
# 用法：右键“使用 PowerShell 运行”，或在此目录执行 .\start_platform.ps1
# 启动后浏览器打开 http://127.0.0.1:8000  默认账号 admin / 12345678

$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\src"

Write-Host "== 家装 AI 智能体平台（壹城精工·骨架版）==" -ForegroundColor Cyan
Write-Host "启动中：uvicorn api_server:app --port 8000 ..."
Write-Host "打开浏览器访问: http://127.0.0.1:8000   （Ctrl+C 停止）" -ForegroundColor Yellow

python -m uvicorn api_server:app --host 127.0.0.1 --port 8000
