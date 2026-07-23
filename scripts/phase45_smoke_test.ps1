$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand($Description, [scriptblock]$Command) {
    Write-Host "`nRunning: $Description"
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Description failed with exit code $LASTEXITCODE." }
}

Invoke-CheckedCommand "List registered plugins" { python -m src.main plugin-list }
Invoke-CheckedCommand "Validate configuration" { python -m src.main config-validate }
Invoke-CheckedCommand "Run architecture tests" {
    python -m pytest -q tests/unit/test_plugins.py tests/unit/test_services.py tests/unit/test_events.py tests/unit/test_discovery.py tests/unit/test_runtime.py tests/integration/test_plugin_cli.py
}
Write-Host "Phase 4.5 architecture smoke test passed."
