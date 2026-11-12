param(
    [Parameter(Mandatory = $true)][string]$TestRoot,
    [switch]$SmokeTest,
    [switch]$WindowProbe,
    [switch]$KeyboardProbe
)

# UTF-8 BOM is intentional: Windows PowerShell 5.1 reads Ukrainian messages.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
try {
    if ($env:OS -ne 'Windows_NT') { throw 'Потрібна нативна Windows.' }
    if (([int]$SmokeTest.IsPresent + [int]$WindowProbe.IsPresent + [int]$KeyboardProbe.IsPresent) -gt 1) {
        throw 'Оберіть лише один діагностичний режим.'
    }
    $root = (Resolve-Path -LiteralPath $TestRoot).Path
    $config = Get-Content -LiteralPath (Join-Path $root 'environment.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($config.source -notmatch '^source-[0-9a-f]{7,40}$' -or $config.revision -notmatch '^[0-9a-f]{40}$') {
        throw 'Некоректна конфігурація тестового середовища.'
    }
    $source = Join-Path $root $config.source
    $python = Join-Path $source '.venv\Scripts\python.exe'
    $data = [IO.Path]::GetFullPath($config.dataDirectory)
    $profilePrefix = [IO.Path]::GetFullPath($env:LOCALAPPDATA).TrimEnd('\') + '\CyberForge-Phase2-Native-'
    if (-not $data.StartsWith($profilePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Demo-каталог має бути в окремому локальному профілі користувача.'
    }
    $sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $allowed = @($sid, 'S-1-5-18', 'S-1-5-32-544')
    $database = Join-Path $data 'demo.sqlite3'
    $credentials = Join-Path $data 'demo-credentials.json'
    foreach ($path in @($data, $database, $credentials)) {
        if (-not (Test-Path -LiteralPath $path)) { throw 'Тестове середовище ще не підготовлено.' }
        $acl = Get-Acl -LiteralPath $path
        foreach ($entry in $acl.Access) {
            $identity = $entry.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
            if ($entry.AccessControlType -eq 'Allow' -and $identity -notin $allowed) {
                throw 'ACL demo-файлів потребують перевірки. Запуск зупинено.'
            }
        }
    }
    if (-not (Get-Acl -LiteralPath $data).AreAccessRulesProtected) {
        throw 'Demo-каталог не має приватних ACL. Запуск зупинено.'
    }
    if (-not (Test-Path -LiteralPath $python)) { throw 'Локальний Python 3.12 не знайдено.' }
    $env:QT_QPA_PLATFORM = 'windows'
    $env:PYTHONUTF8 = '1'
    $env:TEMP = Join-Path $root '.temp'
    $env:TMP = $env:TEMP
    Set-Location -LiteralPath $source
    if ($WindowProbe) {
        & $python -I (Join-Path $source 'tools\window_probe.py')
    } elseif ($KeyboardProbe) {
        & $python -I (Join-Path $source 'tools\keyboard_probe.py')
    } else {
        $arguments = @('-I', '-m', 'cyberforge', '--database', $database)
        if ($SmokeTest) { $arguments += '--smoke-test' }
        & $python @arguments
    }
    exit $LASTEXITCODE
} catch {
    Write-Error ('Не вдалося запустити CyberForge: ' + $_.Exception.Message)
    exit 1
}
