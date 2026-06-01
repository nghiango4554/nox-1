# Stop job gen title/meta (dual-AI hoặc single) qua endpoint Flask.
# Gọi bởi Task Scheduler lúc 13:40. Log kết quả.
$ErrorActionPreference = "SilentlyContinue"
$log = Join-Path $PSScriptRoot "..\data\backups\stop_gen.log"
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
try {
    $r = Invoke-WebRequest -UseBasicParsing -Method POST `
        -Uri "http://127.0.0.1:5055/seo/title-meta/fix-all/stop" -TimeoutSec 15
    Add-Content $log "[$ts] STOP sent — HTTP $($r.StatusCode): $($r.Content)"
} catch {
    Add-Content $log "[$ts] STOP error: $($_.Exception.Message)"
}
