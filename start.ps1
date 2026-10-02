<#
HomeDesignGroup 项目启动脚本
支持参数 --smoke-test 冒烟自检
#>
param(
    [switch]$smokeTest
)
$root = "H:\AgentProjects\HomeDesignGroup"
$srcPath = Join-Path $root "src"
$depsPath = Join-Path $root ".deps"
$env:PYTHONPATH = $srcPath

Write-Host "====================================="
Write-Host "HomeDesignGroup 家装智能体 启动器"
Write-Host "项目根目录: $root"
Write-Host "=====================================`n"

# 检查Python是否在PATH
if (-not (Get-Command python -ErrorAction SilentlyContinue)){
    Write-Error "❌ 未检测到python，请先安装Python并加入系统环境变量"
    exit 1
}

# 本地项目依赖加载
$env:PYTHONPATH += ";$depsPath"

if ($smokeTest){
    Write-Host "`n🧪 执行冒烟测试"
    python (Join-Path $srcPath "smoke_test.py")
    Write-Host "✅ 冒烟测试完成"
    exit 0
}

Write-Host "🚀 启动消息总线主程序"
python (Join-Path $srcPath "main.py")
