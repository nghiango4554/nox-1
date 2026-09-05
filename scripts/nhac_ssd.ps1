# Nhac vo bat bai SSD tren Zalo OA. Chay 12:00 ngay 19/08/2026.
Add-Type -AssemblyName System.Windows.Forms
$t = New-Object System.Windows.Forms.Form
$t.TopMost = $true
[void][System.Windows.Forms.MessageBox]::Show(
    $t,
    "Bai SSD Biwin NV7200 1TB dang nam AN tren Zalo OA." + [Environment]::NewLine +
    "Vao oa.zalo.me > Noi dung > Danh sach bai viet," + [Environment]::NewLine +
    "bam dau ba cham o bai dau tien roi chon 'Hien bai viet'." + [Environment]::NewLine + [Environment]::NewLine +
    "Bai da co san anh bia va 13 doan noi dung.",
    "Nhac: bat bai SSD tren Zalo",
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Information)
$t.Dispose()
