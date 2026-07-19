$root = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$runtime = @("server.py", "static", "anthill")
Push-Location $root
$hits = rg -n "visual-lab/va1|va1-concept" -- @runtime 2>$null
Pop-Location
if ($LASTEXITCODE -eq 0 -and $hits) { throw "VA1 already crosses the production boundary:`n$hits" }
if ($LASTEXITCODE -notin @(0, 1)) { exit $LASTEXITCODE }
@{ isolated = $true; scanned = $runtime } | ConvertTo-Json -Compress
