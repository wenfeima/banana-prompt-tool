# 香蕉提示词工具链 - 一键发版脚本
# 用法: 双击 发版.bat (或 powershell -ExecutionPolicy Bypass -File release.ps1)
# 功能: 同步最新代码 -> 重新打包 zip -> git 提交推送 -> 创建 GitHub Release

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ---------- 配置 ----------
$gh  = "L:\工作流\小工具\gh-cli\bin\gh.exe"
$git = "C:\Program Files\Git\cmd\git.exe"
$src = "L:\工作流\小工具\香蕉提示词抓取"
$repo = "L:\工作流\小工具\banana-prompt-tool"
$upd = "L:\ComfyUI\ComfyUI\custom_nodes\localbanana-prompts\update_banana_daily.py"
$env:HTTPS_PROXY = "http://127.0.0.1:10808"
$env:HTTP_PROXY  = "http://127.0.0.1:10808"
$env:PATH = "C:\Program Files\Git\cmd;" + $env:PATH

# 发布的核心文件清单（源目录 -> 仓库目录）
$coreFiles = @(
    "banana_gui.py",
    "config.json",
    "scan_cleanup.py",
    "serve_viewer.py",
    "香蕉提示词库查看器.html",
    "打开查看器.bat",
    "香蕉提示词抓取器.exe"
)

Write-Host "==== 香蕉提示词工具链 一键发版 ====" -ForegroundColor Cyan

# 1) 读取当前最新版本
$latest = "v0.1.0"
try {
    $latest = (& $gh repo view wenfeima/banana-prompt-tool --json latestRelease --jq ".latestRelease.tagName" 2>$null)
    if ([string]::IsNullOrWhiteSpace($latest)) { $latest = "v0.1.0" }
} catch {}
Write-Host "当前最新版本: $latest"

# 默认版本号 = 次版本 +1
$dft = "v0.1.0"
$m = [regex]::Match($latest, 'v(\d+)\.(\d+)\.(\d+)')
if ($m.Success) {
    $dft = "v$($m.Groups[1].Value).$([int]$m.Groups[2].Value + 1).0"
}
$ver = Read-Host "输入新版本号 (直接回车用默认 $dft)"
if ([string]::IsNullOrWhiteSpace($ver)) { $ver = $dft }

# 2) 同步核心文件到仓库目录
Write-Host "[1/4] 同步最新代码..." -ForegroundColor Green
foreach ($f in $coreFiles) {
    $p = Join-Path $src $f
    if (Test-Path -LiteralPath $p) { Copy-Item -LiteralPath $p -Destination $repo -Force }
    else { Write-Warning "源目录缺少: $f (跳过)" }
}
if (Test-Path -LiteralPath $upd) { Copy-Item -LiteralPath $upd -Destination (Join-Path $repo "update_banana_daily.py") -Force }

# 3) 重新打包 zip（排除 .git / 旧 zip / 发版脚本）
Write-Host "[2/4] 打包 zip..." -ForegroundColor Green
$zip = Join-Path $repo "banana-prompt-tool.zip"
Remove-Item -LiteralPath $zip -ErrorAction SilentlyContinue
$files = Get-ChildItem -LiteralPath $repo -Force | Where-Object {
    $_.Name -ne ".git" -and $_.Name -ne "banana-prompt-tool.zip" -and $_.Name -ne "release.ps1" -and $_.Name -ne "发版.bat"
}
Compress-Archive -Path $files.FullName -DestinationPath $zip -Force
Write-Host "     zip: $zip ($([math]::Round((Get-Item $zip).Length/1MB,1)) MB)"

# 4) git 提交 + 推送
Write-Host "[3/4] git 提交推送..." -ForegroundColor Green
& $git -C $repo add -A
& $git -C $repo commit -m "更新: $ver" | Out-Null
& $git -C $repo push origin main
if ($LASTEXITCODE -ne 0) { throw "git push 失败" }

# 5) 创建 Release
Write-Host "[4/4] 创建 GitHub Release..." -ForegroundColor Green
$notes = "香蕉提示词工具链 $ver`n`n- 增量抓取 localbanana 美女提示词`n- 白名单+黑名单双过滤`n- 后期筛查机制`n- 网页查看器`n- Windows 启动器 exe`n`n下载解压即用: 双击 香蕉提示词抓取器.exe"
& $gh release create $ver $zip --repo wenfeima/banana-prompt-tool --title "banana-prompt-tool $ver" --notes $notes
if ($LASTEXITCODE -ne 0) { throw "gh release create 失败" }

Write-Host ""
Write-Host "==== 发布完成! $ver ====" -ForegroundColor Green
Write-Host "https://github.com/wenfeima/banana-prompt-tool/releases/tag/$ver"
Write-Host ""
pause
