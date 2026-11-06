<#
parear_whatsapp.ps1 - Conecta (pareia) o WhatsApp que envia os alertas.

Use quando "python -m notificador --status" mostrar "NÃO conectado".
  1. reinicia a sessão na whatsapp-api;
  2. salva o QR Code em qr.png e abre na tela (atualiza a cada 10 s);
  3. termina quando o celular ler o QR (ou após 3 minutos).

Uso:  powershell -ExecutionPolicy Bypass -File scripts\parear_whatsapp.ps1 [-Pasta C:\whatsapp-api] [-Sessao ABCD]
#>
param(
  [string]$Pasta = 'C:\whatsapp-api',
  [string]$Sessao = 'ABCD',
  [string]$Base = 'http://localhost:3000'
)
$k = ((Get-Content "$Pasta\.env" | Where-Object { $_ -match '^API_KEY=' }) -replace '^API_KEY=','' -replace '\s+#.*$','').Trim()
$h = @{ 'x-api-key' = $k }
$qr = Join-Path $PSScriptRoot '..\qr.png'
try { Invoke-WebRequest -UseBasicParsing "$Base/session/terminate/$Sessao" -Headers $h | Out-Null } catch {}
Start-Sleep 3
try { Invoke-WebRequest -UseBasicParsing "$Base/session/start/$Sessao" -Headers $h | Out-Null } catch {}
$aberto = $false
for ($i = 0; $i -lt 18; $i++) {
  Start-Sleep 10
  try { $st = (Invoke-WebRequest -UseBasicParsing "$Base/session/status/$Sessao" -Headers $h).Content } catch { $st = '' }
  # -cmatch (diferencia maiúsculas): "session_not_connected" não pode contar como conectado.
  if ($st -cmatch '"state":"CONNECTED"') { 'CONECTADO'; Remove-Item $qr -ErrorAction SilentlyContinue; exit 0 }
  try {
    Invoke-WebRequest -UseBasicParsing "$Base/session/qr/$Sessao/image" -Headers $h -OutFile $qr
    if (-not $aberto) { Start-Process $qr; $aberto = $true; 'QR Code aberto: leia no celular (Aparelhos conectados)' }
  } catch { 'aguardando QR...' }
}
'TEMPO ESGOTADO - rode de novo'
exit 1
