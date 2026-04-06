# run_nightly.ps1 —— 定时任务执行的入口脚本
# 用法：手动触发  Start-ScheduledTask -TaskName "QuantAI-NightlyBuild"
#       直接运行  powershell -File run_nightly.ps1

$logFile = "$env:TEMP\QuantAI-nightly-$(Get-Date -Format 'yyyyMMdd').log"
Start-Transcript -Path $logFile -Append

Set-Location D:\work\Quant_Trading\sdd_full

# 激活虚拟环境
& "backend\.venv\Scripts\Activate.ps1"

# 找最近 3 天内修改过的需求文档（取最新一个）
# 宽松窗口避免昨天写好今天才跑时找不到文件
$req = Get-ChildItem "需求文档-v*.md" |
       Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-3) } |
       Sort-Object LastWriteTime -Descending |
       Select-Object -First 1

if ($req) {
    Write-Host "[$( Get-Date -Format 'HH:mm:ss' )] 开始处理：$($req.Name)"
    python -X utf8 auto_fix.py --req $req.FullName --commit
    Write-Host "[$( Get-Date -Format 'HH:mm:ss' )] 流水线结束，退出码：$LASTEXITCODE"
} else {
    Write-Host "[$( Get-Date -Format 'HH:mm:ss' )] 最近3天无新需求文档，跳过执行"
}

Stop-Transcript
