$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot | Split-Path -Parent
$py = 'D:\Codex\Tools\Python313\python.exe'
$env:PLAYWRIGHT_BROWSERS_PATH = 'D:\Codex\Caches\ms-playwright'
$env:PYTHONIOENCODING = 'utf-8'
$env:DOUYIN_API_DATA = Join-Path $root '.smoke-data'
$log = Join-Path $root 'evidence\server.log'
$proc = Start-Process -FilePath $py -ArgumentList '-m','uvicorn','douyin_api.server:create_app','--factory','--port','8795','--host','127.0.0.1' -WorkingDirectory (Join-Path $root 'src') -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError "$log.err"
$base = 'http://127.0.0.1:8795'
$ok = $false
for ($i = 0; $i -lt 60; $i++) { Start-Sleep -Milliseconds 500; try { $h = Invoke-RestMethod "$base/health" -TimeoutSec 2; $ok = $true; break } catch {} }
if (-not $ok) { Write-Host 'SERVER_FAILED'; Get-Content $log, "$log.err" -ErrorAction SilentlyContinue | Select-Object -Last 20; exit 1 }
Write-Host ('HEALTH ' + ($h | ConvertTo-Json -Compress))
Write-Host ('SESSION ' + ((Invoke-RestMethod "$base/auth/session") | ConvertTo-Json -Compress))
$r = Invoke-RestMethod "$base/api/feed/hot-search?limit=3" -TimeoutSec 120
Write-Host "HOT total=$($r.total)"
$r.items | ForEach-Object { Write-Host "   - $($_.word)" }
try { Invoke-RestMethod "$base/api/feed/featured" -TimeoutSec 10 | Out-Null; Write-Host 'FEATURED unexpected 200' } catch { Write-Host "FEATURED_STATUS $($_.Exception.Response.StatusCode.value__)" }
$v = Invoke-RestMethod "$base/diagnostics/version"
Write-Host ('VERSION ' + ($v | ConvertTo-Json -Compress))
Stop-Process -Id $proc.Id -Force
Write-Host 'STOPPED'
