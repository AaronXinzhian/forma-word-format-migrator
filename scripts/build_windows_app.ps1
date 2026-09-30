#Requires -Version 7.2
# [INPUT]: 依赖 (未检出外部依赖)
# [OUTPUT]: 提供源码首尾绑定、原生语义 smoke、全部 ZIP CRC/签名与解压复验后的 Windows 包
# [POS]: 构建层-Windows 原生发行门禁；测试和报告写入包外，未签名产物标记 local-unsigned
# [PROTOCOL]: 修改时更新此头部与 FOLDER_INDEX.md
[CmdletBinding()]
param(
    [string]$OutputDirectory,
    [switch]$RequireSigning,
    [string]$CertificateThumbprint = $env:FORMA_WINDOWS_CERTIFICATE_THUMBPRINT,
    [string]$TimestampServer = $env:FORMA_WINDOWS_TIMESTAMP_SERVER
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not $IsWindows) { throw 'Windows 原生构建门禁必须在 Windows 上运行。' }
$ProjectRoot = Split-Path $PSScriptRoot -Parent
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $ProjectRoot 'outputs' }
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
$BuildRoot = Join-Path $ProjectRoot ('build/windows-verified-' + [guid]::NewGuid().ToString('N'))
$PackageRoot = Join-Path $BuildRoot 'package'
$CheckRoot = Join-Path $BuildRoot 'extracted'
$HarnessRoot = Join-Path $BuildRoot 'harness'
$ReportsRoot = Join-Path $BuildRoot 'reports'
$DownloadRoot = Join-Path $ProjectRoot 'build/downloads'
$PythonVersion = '3.14.6'
$LxmlVersion = '6.1.1'
$DotnetVersion = '10.0.302'
$HostPython = if ($env:FORMA_BUILD_PYTHON) { $env:FORMA_BUILD_PYTHON } else { (Get-Command python -ErrorAction Stop).Source }
$Dotnet = (Get-Command dotnet -ErrorAction Stop).Source

function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program 退出码 $LASTEXITCODE" }
}
function Get-Verified([string]$Url, [string]$Destination, [string]$Hash) {
    if (-not (Test-Path -LiteralPath $Destination)) { Invoke-WebRequest -Uri $Url -OutFile $Destination }
    if ((Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Hash) {
        throw "下载文件校验失败：$Destination"
    }
}
function Get-SourceManifest([string]$Destination, [string]$Channel) {
    Invoke-Checked $HostPython @('scripts/source_manifest.py','--out',$Destination,'--platform','Windows','--toolchain',".NET SDK $DotnetVersion",'--channel',$Channel)
    return Get-Content -LiteralPath $Destination -Raw -Encoding utf8 | ConvertFrom-Json
}
function Test-SourceBinding($Start, $End) {
    if ($Start.source_commit -ne $End.source_commit -or $Start.source_tree_sha256 -ne $End.source_tree_sha256 -or $Start.source_dirty -ne $End.source_dirty) {
        throw '构建期间源码、测试输入或 Git 状态发生变化。'
    }
    if ($RequireSigning -and ($Start.source_dirty -or $End.source_dirty)) {
        throw '正式发行需要干净已提交源码。'
    }
}
function Get-PackageFingerprint([string]$Directory) {
    $Hashes = [Collections.Generic.SortedDictionary[string,string]]::new([StringComparer]::Ordinal)
    foreach ($File in Get-ChildItem -LiteralPath $Directory -Recurse -File -Force) {
        if ($File.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw '发行包不得包含文件链接。' }
        $Relative = [IO.Path]::GetRelativePath($Directory,$File.FullName).Replace('\','/')
        $Hashes.Add($Relative,(Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash)
    }
    return ConvertTo-Json -InputObject $Hashes -Depth 5 -Compress
}
function Test-ZipCrc([string]$Archive) {
    $Check = @'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as archive:
    bad = archive.testzip()
    if bad is not None:
        raise RuntimeError("ZIP CRC failed: " + bad)
'@
    Invoke-Checked $HostPython @('-B','-X','utf8','-c',$Check,$Archive)
}
function Invoke-SmokeHarness([string]$Phase, [string]$Directory) {
    $ReportPath = Join-Path $ReportsRoot "$Phase.json"
    $StartInfo = [Diagnostics.ProcessStartInfo]::new()
    $StartInfo.FileName = Join-Path $HarnessRoot 'WindowsSmokeHarness.exe'
    $StartInfo.WorkingDirectory = $HarnessRoot
    $StartInfo.UseShellExecute = $false
    $StartInfo.CreateNoWindow = $true
    foreach ($Argument in @('--package-root',$Directory,'--fixture-root',(Join-Path $ProjectRoot 'tests/fixtures'),'--work-root',(Join-Path $BuildRoot "smoke-$Phase"),'--report-path',$ReportPath)) {
        $StartInfo.ArgumentList.Add($Argument)
    }
    # PowerShell 的 & 不保证等待 WinExe；显式等待此进程并检查它的真实退出码。
    $Process = [Diagnostics.Process]::Start($StartInfo)
    if ($null -eq $Process) { throw '无法启动 Windows 冒烟程序。' }
    try {
        if (-not $Process.WaitForExit(300000)) {
            $Process.Kill($true)
            throw "Windows 冒烟程序超时：$Phase"
        }
        if ($Process.ExitCode -ne 0) { throw "Windows 冒烟程序退出码 $($Process.ExitCode)：$Phase" }
    } finally {
        $Process.Dispose()
    }
    $Report = Get-Content -LiteralPath $ReportPath -Raw -Encoding utf8 | ConvertFrom-Json
    if (-not $Report.ok -or $Report.smoke_schema -ne 'forma.windows-smoke.v2' -or $Report.operating_system_family -ne 'Windows' -or $Report.architecture -ne 'X64' -or $Report.runtime.platform -ne 'win32') {
        throw "Windows 原生内置运行时 smoke 未通过：$Phase"
    }
    return $Report
}
function Test-PackageSignature([string]$Directory) {
    foreach ($File in Get-ChildItem -LiteralPath $Directory -Recurse -File -Force | Where-Object { $_.Extension -in '.exe','.dll','.pyd' }) {
        $Signature = Get-AuthenticodeSignature -LiteralPath $File.FullName
        if ($Signature.Status -ne 'Valid') { throw "包内签名无效：$($File.Name)" }
        # 供应商已有有效签名保留；本次签名必须带时间戳。
        if ($Signature.SignerCertificate.Thumbprint -eq $CertificateThumbprint -and -not $Signature.TimeStamperCertificate) {
            throw "本次签名缺少时间戳：$($File.Name)"
        }
    }
}

New-Item -ItemType Directory -Force -Path $BuildRoot,$PackageRoot,$HarnessRoot,$ReportsRoot,$DownloadRoot,$OutputDirectory | Out-Null
[xml]$Project = Get-Content -LiteralPath (Join-Path $ProjectRoot 'windows-app/FormaFushi.Windows/FormaFushi.Windows.csproj') -Raw -Encoding utf8
$Version = [string]$Project.Project.PropertyGroup.Version
Push-Location $ProjectRoot
try {
    $SdkVersion = (& $Dotnet --version).Trim()
    if ($LASTEXITCODE -ne 0 -or $SdkVersion -ne $DotnetVersion) { throw "需要 .NET SDK $DotnetVersion，当前 $SdkVersion" }
    $StartManifest = Get-SourceManifest (Join-Path $BuildRoot 'source-start.json') '验证中'
    if ($RequireSigning -and ($StartManifest.source_dirty -or -not $CertificateThumbprint -or -not $TimestampServer)) {
        throw '正式发行需要干净已提交源码、签名证书及可信时间戳服务。'
    }
    if ($CertificateThumbprint) {
        if (-not $TimestampServer) { throw '签名需要显式配置 HTTPS 时间戳服务器。' }
        [uri]$TimestampUri = $TimestampServer
        if (-not $TimestampUri.IsAbsoluteUri -or $TimestampUri.Scheme -ne 'https') { throw '签名需要显式配置 HTTPS 时间戳服务器。' }
        $Certificate = Get-Item -LiteralPath "Cert:/CurrentUser/My/$CertificateThumbprint"
        $CodeSigningOids = foreach ($Extension in $Certificate.Extensions) {
            if ($Extension -is [Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]) {
                foreach ($Usage in $Extension.EnhancedKeyUsages) { $Usage.Value }
            }
        }
        if (-not $Certificate.HasPrivateKey -or $Certificate.NotBefore -gt (Get-Date) -or $Certificate.NotAfter -lt (Get-Date) -or '1.3.6.1.5.5.7.3.3' -notin @($CodeSigningOids)) {
            throw '需要有效且带私钥的代码签名证书。'
        }
    }
    $PythonArchive = Join-Path $DownloadRoot "python-$PythonVersion-embed-amd64.zip"
    $LxmlArchive = Join-Path $DownloadRoot "lxml-$LxmlVersion-cp314-cp314-win_amd64.whl"
    Get-Verified -Url "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip" -Destination $PythonArchive -Hash 'df901e84a896ff1ee720ad03377e0c8d8c2244fda79808aeeaff6316df1cb75c'
    Get-Verified -Url "https://files.pythonhosted.org/packages/b8/ce/3cf9a827342269f54d405a6202397de63f07c69cbd6ce7d183a3f0cba1e9/lxml-$LxmlVersion-cp314-cp314-win_amd64.whl" -Destination $LxmlArchive -Hash 'b2d444f2e66624d68e9c6b211e28a76e22fff5fcabcfff4deac18b529b7d4137'
    Invoke-Checked $HostPython @('-m','unittest','discover','-s','tests','-p','test_*.py','-v')
    Invoke-Checked $HostPython @('scripts/gen_ui_strings.py','--check')
    Invoke-Checked $Dotnet @('run','--project','tests/WindowsPackDeletionPolicyTests/WindowsPackDeletionPolicyTests.csproj','-c','Release','--','--strict')
    Invoke-Checked $Dotnet @('publish','windows-app/FormaFushi.Windows/FormaFushi.Windows.csproj','-c','Release','-r','win-x64','--self-contained','true','-o',$PackageRoot)
    $Runtime = Join-Path $PackageRoot 'runtime'
    $SitePackages = Join-Path $Runtime 'Lib/site-packages'
    $Resources = Join-Path $PackageRoot 'resources'
    $Licenses = Join-Path $PackageRoot '第三方许可'
    New-Item -ItemType Directory -Force -Path $Runtime,$SitePackages,$Resources,$Licenses | Out-Null
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::ExtractToDirectory($PythonArchive,$Runtime)
    [IO.Compression.ZipFile]::ExtractToDirectory($LxmlArchive,$SitePackages)
    Copy-Item -LiteralPath 'windows-app/runtime/python314._pth' -Destination $Runtime
    Copy-Item -LiteralPath 'style_pack_manager.py','word_style_transfer.py' -Destination $Resources
    Copy-Item -LiteralPath 'LICENSE' -Destination $PackageRoot
    Copy-Item -LiteralPath 'windows-app/README-Windows.md' -Destination (Join-Path $PackageRoot '使用说明.md')
    Copy-Item -LiteralPath (Join-Path $Runtime 'LICENSE.txt') -Destination (Join-Path $Licenses 'Python-LICENSE.txt')
    $LxmlLicenses = Join-Path $SitePackages "lxml-$LxmlVersion.dist-info/licenses"
    if (-not (Test-Path -LiteralPath $LxmlLicenses)) { throw 'lxml 许可证缺失。' }
    Copy-Item -LiteralPath $LxmlLicenses -Destination (Join-Path $Licenses 'lxml') -Recurse
    $DotnetRoot = Split-Path $Dotnet -Parent
    Copy-Item -LiteralPath (Join-Path $DotnetRoot 'ThirdPartyNotices.txt') -Destination (Join-Path $Licenses 'dotnet-ThirdPartyNotices.txt')
    Copy-Item -LiteralPath (Join-Path $DotnetRoot 'LICENSE.txt') -Destination (Join-Path $Licenses 'dotnet-LICENSE.txt')
    foreach ($Required in 'FormaFushi.exe','FormaFushi.dll','FormaFushi.runtimeconfig.json','hostfxr.dll','coreclr.dll','System.Windows.Forms.dll','runtime/python.exe','resources/style_pack_manager.py','resources/word_style_transfer.py','LICENSE') {
        if (-not (Test-Path -LiteralPath (Join-Path $PackageRoot $Required) -PathType Leaf)) { throw "发行包缺少：$Required" }
    }
    $RuntimeConfig = Get-Content -LiteralPath (Join-Path $PackageRoot 'FormaFushi.runtimeconfig.json') -Raw -Encoding utf8 | ConvertFrom-Json
    if (-not $RuntimeConfig.runtimeOptions.includedFrameworks) { throw 'Windows 应用不是自包含部署。' }
    Invoke-Checked $Dotnet @('publish','tests/WindowsSmokeHarness/WindowsSmokeHarness.csproj','-c','Release','-r','win-x64','--self-contained','true','-o',$HarnessRoot)
    $SmokeReports = [ordered]@{}
    $SmokeReports['before_signing'] = Invoke-SmokeHarness 'before-signing' $PackageRoot
    $Channel = '本机测试构建（未签名，已通过 Windows 原生门禁）'
    $Suffix = '-local-unsigned'
    if ($CertificateThumbprint) {
        foreach ($File in Get-ChildItem -LiteralPath $PackageRoot -Recurse -File -Force | Where-Object { $_.Extension -in '.exe','.dll','.pyd' }) {
            # 保留 Python/.NET 已有的有效供应商签名，给无效或未签名部件补签。
            if ((Get-AuthenticodeSignature -LiteralPath $File.FullName).Status -ne 'Valid') {
                $Signature = Set-AuthenticodeSignature -FilePath $File.FullName -Certificate $Certificate -TimestampServer $TimestampServer -HashAlgorithm SHA256
                if ($Signature.Status -ne 'Valid' -or -not $Signature.TimeStamperCertificate) { throw "签名失败：$($File.Name)" }
            }
        }
        Test-PackageSignature $PackageRoot
        $SmokeReports['after_signing'] = Invoke-SmokeHarness 'after-signing' $PackageRoot
        $Channel = 'Authenticode 签名并通过 Windows 原生门禁'
        $Suffix = if ($RequireSigning) { '' } else { '-local-signed' }
    }
    $EndManifest = Get-SourceManifest (Join-Path $PackageRoot 'source-manifest.json') $Channel
    Test-SourceBinding $StartManifest $EndManifest
    $PackageHashes = Get-PackageFingerprint $PackageRoot
    $Archive = Join-Path $BuildRoot "Forma赋式-Windows-x64-v$Version$Suffix.zip"
    [IO.Compression.ZipFile]::CreateFromDirectory($PackageRoot,$Archive,[IO.Compression.CompressionLevel]::Optimal,$false,[Text.UTF8Encoding]::new($false,$true))
    Test-ZipCrc $Archive
    [IO.Compression.ZipFile]::ExtractToDirectory($Archive,$CheckRoot)
    if ($PackageHashes -cne (Get-PackageFingerprint $CheckRoot)) { throw '解压后的发行包文件清单或内容摘要与原包不一致。' }
    if ($CertificateThumbprint) { Test-PackageSignature $CheckRoot }
    $SmokeReports['after_archive'] = Invoke-SmokeHarness 'after-archive' $CheckRoot
    $ValidatedManifest = Get-SourceManifest (Join-Path $BuildRoot 'source-after-validation.json') $Channel
    Test-SourceBinding $StartManifest $ValidatedManifest

    $Published = Join-Path $OutputDirectory (Split-Path $Archive -Leaf)
    $PublishedReport = "$Published.windows-smoke-report.json"
    foreach ($Destination in $Published,"$Published.sha256",$PublishedReport) {
        if (Test-Path -LiteralPath $Destination) { throw "输出已存在，拒绝覆盖：$Destination" }
    }
    $Hash = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
    $TemporaryPublished = Join-Path $OutputDirectory ('.forma-' + [guid]::NewGuid().ToString('N') + '.tmp')
    [IO.File]::Copy($Archive,$TemporaryPublished,$false)
    if ((Get-FileHash -LiteralPath $TemporaryPublished -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Hash) { throw '输出目录副本校验失败。' }
    [IO.File]::Move($TemporaryPublished,$Published,$false)
    "$Hash  $(Split-Path $Published -Leaf)" | Set-Content -LiteralPath "$Published.sha256" -Encoding utf8
    [ordered]@{
        schema = 'forma.windows-release-checks.v1'
        source_commit = $EndManifest.source_commit
        source_tree_sha256 = $EndManifest.source_tree_sha256
        source_dirty = $EndManifest.source_dirty
        channel = $Channel
        archive_sha256 = $Hash
        full_archive_zip_crc = $true
        extracted_files_identical = $true
        smoke_phases = $SmokeReports
    } | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $PublishedReport -Encoding utf8
    Write-Output "Windows 验证包：$Published"
    Write-Output "Windows 原生验证报告：$PublishedReport"
} finally {
    Pop-Location
}
