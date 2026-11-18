<#
.SYNOPSIS
  ReviewLens - deploy to a Hostinger VPS from your Windows laptop, without clicking in hPanel.

.DESCRIPTION
  Uses the Hostinger API (https://developers.hostinger.com) to:
    1. find your VPS and its IP address
    2. take a VPS snapshot (backup) first
    3. create an SSH key on this laptop (if missing) and add it to the VPS
    4. point <Subdomain>.<Domain> at the VPS (A record; an existing CNAME for that name is replaced)
    5. wait until DNS resolves
    6. SSH into the VPS and run scripts/server_setup.sh (asks for the OpenAI key there, hidden)

  Needs a Hostinger API token: hPanel -> Account -> API (or developers.hostinger.com) -> create token.
  Put it in $env:HOSTINGER_API_TOKEN, or the script asks for it (hidden).

.EXAMPLE
  $env:HOSTINGER_API_TOKEN = "<your token>"
  .\scripts\hostinger_setup.ps1 -Domain example.com

.EXAMPLE
  .\scripts\hostinger_setup.ps1 -Domain example.com -VmId 123456 -Subdomain www -DryRun
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$Domain,          # e.g. example.com (as listed in hPanel, no www)
  [string]$Subdomain = "www",                              # app URL = https://<Subdomain>.<Domain>/<AppPath>/
  [string]$AppPath = "techstack/ReviewLens",
  [long]$VmId = 0,                                         # 0 = pick the only VPS (or ask)
  [string]$KeyPath = "$HOME\.ssh\reviewlens_vps",
  [string]$Repo = "https://github.com/prasanth-sundararajan/reviewlens",
  [switch]$SkipSnapshot,
  [switch]$SkipServerSetup,                                # only do the hPanel/API part
  [switch]$Force,                                          # do not ask before overwriting snapshot / DNS
  [switch]$DryRun                                          # show what would happen; change nothing
)
$ErrorActionPreference = "Stop"
$Api = "https://developers.hostinger.com"
$Fqdn = if ($Subdomain -and $Subdomain -ne "@") { "$Subdomain.$Domain" } else { $Domain }

function Write-Step([string]$Text) { Write-Host "`n==> $Text" -ForegroundColor Cyan }
function Write-Ok([string]$Text) { Write-Host "    OK $Text" -ForegroundColor Green }
function Write-Warn2([string]$Text) { Write-Host "    WARN $Text" -ForegroundColor Yellow }
function Confirm-Action([string]$Question) {
  if ($Force -or $DryRun) { return $true }
  $a = Read-Host "    $Question [y/N]"
  return ($a -match '^(y|yes)$')
}

$Token = $env:HOSTINGER_API_TOKEN
if (-not $Token -and -not $DryRun) {
  $sec = Read-Host "Hostinger API token (hidden)" -AsSecureString
  $Token = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
}
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Invoke-Hostinger([string]$Method, [string]$Path, $Body = $null, [switch]$Write) {
  $uri = "$Api$Path"
  $json = if ($null -ne $Body) { $Body | ConvertTo-Json -Depth 8 -Compress } else { $null }
  if ($DryRun) {
    Write-Host "    [dry-run] $Method $uri $json" -ForegroundColor DarkGray
    return $null
  }
  $headers = @{ Authorization = "Bearer $Token"; Accept = "application/json" }
  try {
    if ($json) { return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -ContentType "application/json" -Body $json }
    return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers
  } catch {
    $code = $null; try { $code = [int]$_.Exception.Response.StatusCode } catch { }
    if ($code -eq 401) { throw "Hostinger rejected the API token (401). Create a new one in hPanel -> Account -> API and set `$env:HOSTINGER_API_TOKEN." }
    if ($code -eq 404 -and $Path -like "*/dns/*") { throw "Domain '$Domain' not found in this Hostinger account (404). Use the domain exactly as listed in hPanel, without www." }
    throw "Hostinger API $Method $Path failed ($code): $($_.Exception.Message)"
  }
}

# ---------------------------------------------------------------- 1. VPS
Write-Step "1/6 Finding your VPS"
$vm = $null
$vms = Invoke-Hostinger GET "/api/vps/v1/virtual-machines"
if ($DryRun) {
  $vm = [pscustomobject]@{ id = $(if ($VmId) { $VmId } else { 111111 }); hostname = "srvXXXX.hstgr.cloud"; state = "running"
                           ipv4 = @([pscustomobject]@{ address = "203.0.113.10" }) }
} elseif ($VmId) {
  $vm = $vms | Where-Object { $_.id -eq $VmId }
  if (-not $vm) { throw "VPS $VmId not found. Available: $(($vms | ForEach-Object { "$($_.id) ($($_.hostname))" }) -join ', ')" }
} else {
  $running = @($vms | Where-Object { $_.state -eq "running" })
  if ($running.Count -eq 1) { $vm = $running[0] }
  else {
    $vms | ForEach-Object { Write-Host ("    {0}  {1}  {2}  {3}" -f $_.id, $_.hostname, $_.state, $_.ipv4[0].address) }
    $pick = Read-Host "    Which VPS id?"
    $vm = $vms | Where-Object { $_.id -eq [long]$pick }
    if (-not $vm) { throw "No VPS with id $pick" }
  }
}
$Ip = $vm.ipv4[0].address
Write-Ok "VPS $($vm.id) $($vm.hostname) ($($vm.state)) IP $Ip"
if ($vm.state -ne "running") { throw "The VPS is '$($vm.state)'. Start or renew it in hPanel first." }

# ---------------------------------------------------------------- 2. snapshot
Write-Step "2/6 Snapshot (backup) of the VPS"
if ($SkipSnapshot) { Write-Warn2 "skipped (-SkipSnapshot)" }
else {
  $existing = $null
  if (-not $DryRun) { try { $existing = Invoke-Hostinger GET "/api/vps/v1/virtual-machines/$($vm.id)/snapshot" } catch { $existing = $null } }
  if ($existing -and -not (Confirm-Action "A snapshot from $($existing.created_at) exists and will be REPLACED. Continue?")) {
    Write-Warn2 "kept the existing snapshot, no new one taken"
  } else {
    Invoke-Hostinger POST "/api/vps/v1/virtual-machines/$($vm.id)/snapshot" | Out-Null
    Write-Ok "snapshot started (restore any time in hPanel -> VPS -> Snapshots)"
  }
}

# ---------------------------------------------------------------- 3. SSH key
Write-Step "3/6 SSH key"
if (-not (Test-Path $KeyPath)) {
  if ($DryRun) { Write-Host "    [dry-run] ssh-keygen -t ed25519 -f $KeyPath" -ForegroundColor DarkGray }
  else {
    New-Item -ItemType Directory -Force (Split-Path $KeyPath) | Out-Null
    # Start-Process passes -N "" literally, so the empty passphrase works in PowerShell 5.1 and 7
    Start-Process ssh-keygen -ArgumentList "-q -t ed25519 -N `"`" -C reviewlens-deploy -f `"$KeyPath`"" -Wait -NoNewWindow
    if (-not (Test-Path $KeyPath)) { throw "ssh-keygen did not create $KeyPath" }
    Write-Ok "created $KeyPath"
  }
}
$PubKey = if (Test-Path "$KeyPath.pub") { (Get-Content "$KeyPath.pub" -Raw).Trim() } else { "ssh-ed25519 AAAA...(new key) reviewlens-deploy" }
$present = $false
if (-not $DryRun) {
  $keys = Invoke-Hostinger GET "/api/vps/v1/virtual-machines/$($vm.id)/ssh-keys"
  $present = @($keys | Where-Object { $_.key -eq $PubKey }).Count -gt 0
}
if ($present) { Write-Ok "key already on the VPS" }
else { Invoke-Hostinger POST "/api/vps/v1/virtual-machines/$($vm.id)/ssh-keys" @{ keys = @($PubKey) } | Out-Null; Write-Ok "key added to the VPS (root)" }

# ---------------------------------------------------------------- 4. DNS
Write-Step "4/6 DNS: $Fqdn -> $Ip"
$name = if ($Subdomain) { $Subdomain } else { "@" }
$zone = if ($DryRun) { @() } else { @(Invoke-Hostinger GET "/api/dns/v1/zones/$Domain") }
$current = @($zone | Where-Object { $_.name -eq $name -and ($_.type -eq "A" -or $_.type -eq "CNAME") })
$already = @($current | Where-Object { $_.type -eq "A" -and @($_.records.content) -contains $Ip }).Count -gt 0
if ($already) { Write-Ok "A record already points at $Ip" }
else {
  foreach ($r in $current) { Write-Host "    current: $($r.type) $name -> $(@($r.records.content) -join ', ')" }
  if ($current.Count -and -not (Confirm-Action "Replace the record(s) above with A $name -> $Ip ?")) { throw "DNS left unchanged." }
  if (@($current | Where-Object { $_.type -eq "CNAME" }).Count -gt 0) {
    Invoke-Hostinger DELETE "/api/dns/v1/zones/$Domain" @{ filters = @(@{ name = $name; type = "CNAME" }) } | Out-Null
    Write-Ok "removed CNAME $name"
  }
  $record = @{ name = $name; type = "A"; ttl = 300; records = @(@{ content = $Ip }) }
  Invoke-Hostinger PUT "/api/dns/v1/zones/$Domain" @{ overwrite = $true; zone = @($record) } | Out-Null
  Write-Ok "A $name -> $Ip set"
}

# ---------------------------------------------------------------- 5. wait for DNS
Write-Step "5/6 Waiting for DNS"
if ($DryRun) { Write-Host "    [dry-run] Resolve-DnsName $Fqdn -Server 8.8.8.8" -ForegroundColor DarkGray }
else {
  $deadline = (Get-Date).AddMinutes(10); $seen = $null
  while ((Get-Date) -lt $deadline) {
    try { $seen = (Resolve-DnsName $Fqdn -Type A -Server 8.8.8.8 -DnsOnly -ErrorAction Stop | Where-Object { $_.IPAddress } | Select-Object -First 1).IPAddress } catch { $seen = $null }
    if ($seen -eq $Ip) { break }
    Start-Sleep -Seconds 15
  }
  if ($seen -eq $Ip) { Write-Ok "$Fqdn resolves to $Ip" } else { Write-Warn2 "$Fqdn resolves to '$seen' so far - HTTPS may need a few more minutes" }
}

# ---------------------------------------------------------------- 6. server
Write-Step "6/6 Installing / updating ReviewLens on the VPS"
$raw = ($Repo -replace '^https://github.com/', 'https://raw.githubusercontent.com/') + "/main/scripts/server_setup.sh"
$remote = "curl -fsSLo /root/server_setup.sh $raw && APP_DOMAIN=$Fqdn APP_PATH=$AppPath REPO=$Repo.git bash /root/server_setup.sh"
if ($SkipServerSetup) { Write-Warn2 "skipped (-SkipServerSetup). Run later: ssh -i $KeyPath root@$Ip `"$remote`"" }
elseif ($DryRun) { Write-Host "    [dry-run] ssh -t -i $KeyPath root@$Ip `"$remote`"" -ForegroundColor DarkGray }
else {
  & ssh -t -o StrictHostKeyChecking=accept-new -i $KeyPath "root@$Ip" $remote
  if ($LASTEXITCODE -ne 0) { throw "Server setup failed (exit $LASTEXITCODE). Re-run this script or SSH in and run: bash /root/server_setup.sh" }
}

Write-Host "`nDone. App: https://$Fqdn/$AppPath/" -ForegroundColor Green
Write-Host "Update later: ssh -i $KeyPath root@$Ip `"bash /opt/reviewlens/scripts/server_setup.sh`""
