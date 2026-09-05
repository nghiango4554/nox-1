# Nhac vo dang bai Zalo OA - chay 12:30 moi ngay.
# Lich tu dong dang (NoxZalo01-09) DA TAT tu 20/08/2026 theo y vo -> chuyen sang nhac tay.
Add-Type -AssemblyName System.Windows.Forms

$draft = "C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\zalo_sp_draft.json"
$log   = "C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\zalo_dang_log.txt"

# Liet ke bai da soan san (neu doc duoc)
$cho = ""
try {
    if (Test-Path $draft) {
        $d = Get-Content $draft -Raw -Encoding UTF8 | ConvertFrom-Json
        $ma = $d.PSObject.Properties.Name
        if ($ma.Count -gt 0) { $cho = "Bai da soan san: " + ($ma -join ", ") }
    }
} catch { }

# Lan dang gan nhat
$lan = ""
try {
    if (Test-Path $log) {
        $dong = Get-Content $log -Encoding UTF8 | Where-Object { $_ -match 'XONG|DANG XONG' } | Select-Object -Last 1
        if ($dong) { $lan = "Lan dang gan nhat: " + $dong.Substring(0, [Math]::Min(40, $dong.Length)) }
    }
} catch { }

$noi = @()
$noi += "Den gio dang bai Zalo OA."
$noi += ""
$noi += "Han muc: 15 bai / chu ky, reset ngay 15 hang thang."
$noi += "Vao oa.zalo.me/manage/content/article/ xem so X/15 truoc khi dang."
$noi += ""
if ($cho) { $noi += $cho }
if ($lan) { $noi += $lan }
$noi += ""
$noi += "Muon dang bang lenh: py -3.12 nox-1\scripts\zalo_dang_bai.py <ma_bai>"
$noi += "(script tu lam moi token va tu kiem sau khi dang)"

$t = New-Object System.Windows.Forms.Form
$t.TopMost = $true
[void][System.Windows.Forms.MessageBox]::Show(
    $t,
    ($noi -join [Environment]::NewLine),
    "Nhac dang bai Zalo OA - 12:30",
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Information)
$t.Dispose()
