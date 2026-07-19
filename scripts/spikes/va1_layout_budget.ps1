$viewport = 1600
$outer = 64
$gaps = 32
$panel = [math]::Floor(($viewport - $outer - $gaps) / 3)
$scene = $panel - 24
if ($panel -lt 500 -or $scene -lt 470) { throw "VA1 board width budget failed: panel=$panel scene=$scene" }
[pscustomobject]@{ viewport = $viewport; panel = $panel; scene = $scene; minimum = 470 } | ConvertTo-Json -Compress
