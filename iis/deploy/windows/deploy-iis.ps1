[CmdletBinding()]
param(
    [string]$SiteName = "Traceability-Portal",
    [int]$Port = 8374,
    [string]$InstallRoot = "D:\Apps\Traceability-Portal",
    [string]$WebRoot = "C:\inetpub\wwwroot\Traceability-Portal",
    [string]$PythonExe = "D:\Program Files\Python312\python.exe",
    [string]$NssmExe = "D:\Tools\nssm\nssm.exe",
    [string]$ServiceName = "TraceabilityPortalBackend"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)) { throw "Hãy chạy PowerShell bằng Run as administrator." }

$IisSource = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$FrontendSource = Join-Path $IisSource "frontend"
$BackendSource = Join-Path $IisSource "backend"
$BackendTarget = Join-Path $InstallRoot "backend"
$LogsTarget = Join-Path $InstallRoot "logs"
$VenvPython = Join-Path $BackendTarget ".venv\Scripts\python.exe"
$EnvFile = Join-Path $BackendTarget ".env"
$EnvExampleFile = Join-Path $BackendTarget ".env.example"
$SqlTarget = Join-Path $BackendTarget "sql"
$LegacySiteName = "WebTruySuat"
$LegacyServiceName = "WebTruySuatBackend"
$AppCmd = "$env:SystemRoot\System32\inetsrv\appcmd.exe"

function Sync-EnvSetting {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$TargetPath
    )

    $sourceLine = Get-Content $SourcePath -Encoding UTF8 |
        Where-Object { $_.StartsWith("$Name=", [StringComparison]::OrdinalIgnoreCase) } |
        Select-Object -First 1
    if (-not $sourceLine) { throw "Không tìm thấy $Name trong $SourcePath" }

    $found = $false
    $targetLines = @(
        Get-Content $TargetPath -Encoding UTF8 | ForEach-Object {
            if ($_.StartsWith("$Name=", [StringComparison]::OrdinalIgnoreCase)) {
                $found = $true
                $sourceLine
            } else {
                $_
            }
        }
    )
    if (-not $found) { $targetLines += $sourceLine }
    Set-Content -Path $TargetPath -Value $targetLines -Encoding UTF8
}

foreach ($requiredPath in @($PythonExe, $FrontendSource, $BackendSource)) {
    if (-not (Test-Path $requiredPath)) { throw "Không tìm thấy: $requiredPath" }
}
if (-not (Test-Path "$env:SystemRoot\System32\inetsrv\rewrite.dll")) {
    throw "IIS URL Rewrite chưa được cài đặt."
}
if (-not (Test-Path $NssmExe)) {
    throw "Không tìm thấy NSSM tại $NssmExe. Hãy cài NSSM hoặc truyền -NssmExe."
}

# Dừng và vô hiệu hóa bản triển khai cũ để không tranh port với tên mới.
$legacyService = Get-Service -Name $LegacyServiceName -ErrorAction SilentlyContinue
if ($legacyService) {
    if ($legacyService.Status -ne "Stopped") {
        Stop-Service -Name $LegacyServiceName -Force
        $legacyService.WaitForStatus("Stopped", [TimeSpan]::FromSeconds(30))
    }
    Set-Service -Name $LegacyServiceName -StartupType Disabled
}
if (& $AppCmd list site "/name:$LegacySiteName") {
    & $AppCmd stop site "/site.name:$LegacySiteName" | Out-Null
}
if (& $AppCmd list apppool "/name:$LegacySiteName") {
    & $AppCmd stop apppool "/apppool.name:$LegacySiteName" | Out-Null
}

$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService -and $existingService.Status -ne "Stopped") {
    Stop-Service -Name $ServiceName -Force
    $existingService.WaitForStatus("Stopped", [TimeSpan]::FromSeconds(30))
}

New-Item -ItemType Directory -Force -Path $BackendTarget, $LogsTarget, $WebRoot | Out-Null
Copy-Item -Path (Join-Path $FrontendSource "*") -Destination $WebRoot -Recurse -Force
Get-ChildItem -Path $BackendSource -Force |
    Where-Object { $_.Name -notin @(".env", ".venv", "__pycache__") } |
    Copy-Item -Destination $BackendTarget -Recurse -Force
New-Item -ItemType Directory -Force -Path $SqlTarget | Out-Null
Copy-Item -Path (Join-Path $IisSource "..\docs\TRACEABILITY-NEW-QUERY.sql") -Destination $SqlTarget -Force

if (-not (Test-Path $EnvFile)) {
    Copy-Item $EnvExampleFile $EnvFile
    Write-Warning "Đã tạo $EnvFile. Hãy điền SQLSERVER_HOST, SQLSERVER_USER và SQLSERVER_PASSWORD rồi chạy lại script."
    return
}

# Query là một phần của phiên bản ứng dụng; thông tin đăng nhập trong .env được giữ nguyên.
Sync-EnvSetting -Name "SQLQUERY" -SourcePath $EnvExampleFile -TargetPath $EnvFile
Sync-EnvSetting -Name "SQLQUERY_NEW" -SourcePath $EnvExampleFile -TargetPath $EnvFile
Sync-EnvSetting -Name "SQLQUERY_NEW_FILE" -SourcePath $EnvExampleFile -TargetPath $EnvFile
Sync-EnvSetting -Name "SQLQUERY_IMAGE" -SourcePath $EnvExampleFile -TargetPath $EnvFile
Sync-EnvSetting -Name "SQLQUERY_PO" -SourcePath $EnvExampleFile -TargetPath $EnvFile
Sync-EnvSetting -Name "SQLQUERY_LOT" -SourcePath $EnvExampleFile -TargetPath $EnvFile
Sync-EnvSetting -Name "IMAGE_METADATA_CACHE_SECONDS" -SourcePath $EnvExampleFile -TargetPath $EnvFile
Sync-EnvSetting -Name "DOCUMENT_BASE_URL" -SourcePath $EnvExampleFile -TargetPath $EnvFile

if ((Get-Content $EnvFile -Raw) -match "(?m)^SQLSERVER_(HOST|USER|PASSWORD)=\s*$") {
    throw "File .env chưa có đủ SQLSERVER_HOST, SQLSERVER_USER và SQLSERVER_PASSWORD."
}

if (-not (Test-Path $VenvPython)) {
    & $PythonExe -m venv (Join-Path $BackendTarget ".venv")
}
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $BackendTarget "requirements.txt")

if (-not (& $AppCmd list apppool "/name:$SiteName")) {
    & $AppCmd add apppool "/name:$SiteName" | Out-Null
}
& $AppCmd set apppool "/apppool.name:$SiteName" /managedRuntimeVersion:"" /processModel.identityType:ApplicationPoolIdentity | Out-Null

if (-not (& $AppCmd list site "/name:$SiteName")) {
    & $AppCmd add site "/name:$SiteName" "/bindings:http/*:${Port}:" "/physicalPath:$WebRoot" | Out-Null
} else {
    & $AppCmd set vdir "$SiteName/" "/physicalPath:$WebRoot" | Out-Null
}
& $AppCmd set app "$SiteName/" "/applicationPool:$SiteName" | Out-Null
& $AppCmd set config /section:system.webServer/proxy /enabled:true /preserveHostHeader:true | Out-Null

if (-not $existingService) { & $NssmExe install $ServiceName $VenvPython | Out-Null }
& $NssmExe set $ServiceName AppDirectory $BackendTarget | Out-Null
& $NssmExe set $ServiceName AppParameters "-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1" | Out-Null
& $NssmExe set $ServiceName AppStdout (Join-Path $LogsTarget "backend-stdout.log") | Out-Null
& $NssmExe set $ServiceName AppStderr (Join-Path $LogsTarget "backend-stderr.log") | Out-Null
& $NssmExe set $ServiceName AppRotateFiles 1 | Out-Null
& $NssmExe set $ServiceName Start SERVICE_AUTO_START | Out-Null

Start-Service -Name $ServiceName
& $AppCmd start site "/site.name:$SiteName" | Out-Null
Start-Sleep -Seconds 2
$backendHealth = Invoke-RestMethod "http://127.0.0.1:8000/health"
$iisHealth = Invoke-RestMethod "http://127.0.0.1:$Port/health"

[pscustomobject]@{
    SiteName = $SiteName
    SiteUrl = "http://127.0.0.1:$Port"
    BackendStatus = $backendHealth.status
    DatabaseStatus = $backendHealth.database
    IisProxyStatus = $iisHealth.status
    ServiceName = $ServiceName
    ServiceStart = (Get-Service $ServiceName).StartType
}
