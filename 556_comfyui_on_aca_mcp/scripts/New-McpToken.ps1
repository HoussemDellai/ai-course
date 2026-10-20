param(
    [string]$Path = (Join-Path (Split-Path $PSScriptRoot) ".mcp-token.clixml")
)
$ErrorActionPreference = "Stop"
if (Test-Path -LiteralPath $Path) {
    throw "Token file already exists. Reuse it, or explicitly remove it before rotating the token."
}
if (-not $IsWindows) {
    throw "This helper requires Windows DPAPI. On other systems use your secret manager and TF_VAR_mcp_token."
}
$token = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).ToLowerInvariant()
$secure = ConvertTo-SecureString -String $token -AsPlainText -Force
$secure | Export-Clixml -LiteralPath $Path
Write-Host "Created a Windows DPAPI-protected token file. No token value was printed."
