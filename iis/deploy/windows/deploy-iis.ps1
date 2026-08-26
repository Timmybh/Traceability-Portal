[CmdletBinding()]
param(
    [string]$SiteName = "WebTruySuat",
    [int]$Port = 8374,
    [string]$InstallRoot = "C:\Apps\WebTruySuat",
    [string]$WebRoot = "C:\inetpub\wwwroot\WebTruySuat",
    [string]$PythonExe = "C:\Program Files\Python312\python.exe",
    [string]$NssmExe = "C:\Tools\nssm\nssm.exe",
    [string]$ServiceName = "WebTruySuatBackend"
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

foreach ($requiredPath in @($PythonExe, $FrontendSource, $BackendSource)) {
    if (-not (Test-Path $requiredPath)) { throw "Không tìm thấy: $requiredPath" }
}
if (-not (Test-Path "$env:SystemRoot\System32\inetsrv\rewrite.dll")) {
    throw "IIS URL Rewrite chưa được cài đặt."
}
if (-not (Test-Path $NssmExe)) {
    throw "Không tìm thấy NSSM tại $NssmExe. Hãy cài NSSM hoặc truyền -NssmExe."
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

if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $BackendTarget ".env.example") $EnvFile
    Write-Warning "Đã tạo $EnvFile. Hãy điền SQLSERVER_HOST, SQLSERVER_USER và SQLSERVER_PASSWORD rồi chạy lại script."
    return
}
if ((Get-Content $EnvFile -Raw) -match "(?m)^SQLSERVER_(HOST|USER|PASSWORD)=\s*$") {
    throw "File .env chưa có đủ SQLSERVER_HOST, SQLSERVER_USER và SQLSERVER_PASSWORD."
}

if (-not (Test-Path $VenvPython)) {
    & $PythonExe -m venv (Join-Path $BackendTarget ".venv")
}
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $BackendTarget "requirements.txt")

Import-Module WebAdministration
if (-not (Test-Path "IIS:\AppPools\$SiteName")) { New-WebAppPool -Name $SiteName | Out-Null }
Set-ItemProperty "IIS:\AppPools\$SiteName" -Name managedRuntimeVersion -Value ""
Set-ItemProperty "IIS:\AppPools\$SiteName" -Name processModel.identityType -Value ApplicationPoolIdentity

$site = Get-Website -Name $SiteName -ErrorAction SilentlyContinue
if (-not $site) {
    New-Website -Name $SiteName -Port $Port -PhysicalPath $WebRoot -ApplicationPool $SiteName | Out-Null
} else {
    Set-ItemProperty "IIS:\Sites\$SiteName" -Name physicalPath -Value $WebRoot
}
& "$env:SystemRoot\System32\inetsrv\appcmd.exe" set config /section:system.webServer/proxy /enabled:true /preserveHostHeader:true | Out-Null

if (-not $existingService) { & $NssmExe install $ServiceName $VenvPython | Out-Null }
& $NssmExe set $ServiceName AppDirectory $BackendTarget | Out-Null
& $NssmExe set $ServiceName AppParameters "-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1" | Out-Null
& $NssmExe set $ServiceName AppStdout (Join-Path $LogsTarget "backend-stdout.log") | Out-Null
& $NssmExe set $ServiceName AppStderr (Join-Path $LogsTarget "backend-stderr.log") | Out-Null
& $NssmExe set $ServiceName AppRotateFiles 1 | Out-Null
& $NssmExe set $ServiceName Start SERVICE_AUTO_START | Out-Null

Start-Service -Name $ServiceName
Start-WebSite -Name $SiteName
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
