$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$azureCli = Get-Command az -CommandType Application -ErrorAction Stop
$arguments = @(
    "acr", "build",
    "--subscription", $env:SUBSCRIPTION_ID,
    "--registry", $env:ACR_NAME,
    "--image", $env:APP_IMAGE_TAG,
    "--file", $env:APP_DOCKERFILE,
    "."
)

if ($IsWindows -and [System.IO.Path]::GetExtension($azureCli.Source) -eq ".cmd") {
    $installDir = Split-Path -Parent (Split-Path -Parent $azureCli.Source)
    $python = Join-Path $installDir "python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        throw "Cannot locate Azure CLI's bundled Python at '$python'. Use the standard Windows Azure CLI installation."
    }
    # az.cmd uses isolated Python (-I), which ignores PYTHONUTF8/PYTHONIOENCODING.
    $env:AZ_INSTALLER = "MSI"
    & $python -I -B -X utf8 -m azure.cli @arguments
} else {
    & $azureCli.Source @arguments
}
if ($LASTEXITCODE -ne 0) { throw "ACR image build failed with exit code $LASTEXITCODE." }
