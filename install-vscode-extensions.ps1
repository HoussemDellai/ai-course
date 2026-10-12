#Requires -Version 5.1
<#
.SYNOPSIS
Installs the VS Code extensions exported on 2026-10-10.

.DESCRIPTION
Requires VS Code to be installed and its "code" command to be on PATH.
Installs the latest available Marketplace releases by default. Use
-UseRecordedVersions to install the versions recorded on the source machine.
Extensions or versions unavailable in the Marketplace are reported as failures.
Existing extensions in this list may be updated or, with recorded versions,
downgraded. Other extensions are left untouched.
This script does not copy settings, profiles, or enabled/disabled state.

.EXAMPLE
.\install-vscode-extensions.ps1

.EXAMPLE
.\install-vscode-extensions.ps1 -UseRecordedVersions

.EXAMPLE
.\install-vscode-extensions.ps1 -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$UseRecordedVersions
)

$ErrorActionPreference = 'Stop'

$codeCommand = Get-Command code -ErrorAction SilentlyContinue
if ($null -eq $codeCommand) {
    throw 'VS Code CLI was not found. Install VS Code, add its bin directory to PATH, then open a new PowerShell terminal.'
}

$extensions = @(
    'anthropic.claude-code@2.1.287'
    'blackmist.linkcheckmd@0.3.1'
    'cweijan.dbclient-jdbc@1.4.6'
    'cweijan.vscode-postgresql-client2@9.0.2'
    'davidanson.vscode-markdownlint@0.62.1'
    'docker.docker@0.18.0'
    'esbenp.prettier-vscode@12.4.0'
    'github.github-vscode-theme@6.3.5'
    'github.vscode-github-actions@0.32.3'
    'github.vscode-pull-request-github@0.168.0'
    'hashicorp.hcl@0.6.0'
    'hashicorp.terraform@2.40.0'
    'hediet.vscode-drawio@1.15.0'
    'humao.rest-client@0.25.1'
    'mechatroner.rainbow-csv@3.24.1'
    'ms-azure-devops.azure-pipelines@1.261.1'
    'ms-azuretools.vscode-azure-github-copilot@1.0.236'
    'ms-azuretools.vscode-azure-mcp-server@2.0.46'
    'ms-azuretools.vscode-azurefunctions@1.22.2'
    'ms-azuretools.vscode-azureresourcegroups@0.13.2'
    'ms-azuretools.vscode-azurestaticwebapps@0.13.3'
    'ms-azuretools.vscode-azurestorage@0.17.2'
    'ms-azuretools.vscode-azureterraform@0.10.4'
    'ms-azuretools.vscode-azurevirtualmachines@0.6.11'
    'ms-azuretools.vscode-bicep@0.47.16'
    'ms-azuretools.vscode-containers@2.5.2'
    'ms-azuretools.vscode-docker@2.0.0'
    'ms-dotnettools.csdevkit@3.40.210'
    'ms-dotnettools.csharp@2.160.4'
    'ms-dotnettools.vscode-dotnet-runtime@3.2.0'
    'ms-edgedevtools.vscode-edge-devtools@2.1.12'
    'ms-kubernetes-tools.vscode-kubernetes-tools@1.4.1'
    'ms-mssql.data-workspace-vscode@0.7.0'
    'ms-mssql.mssql@1.46.0'
    'ms-mssql.sql-bindings-vscode@0.4.1'
    'ms-mssql.sql-database-projects-vscode@1.8.0'
    'ms-ossdata.vscode-pgsql@1.32.0'
    'ms-playwright.playwright@1.1.19'
    'ms-python.black-formatter@2026.6.0'
    'ms-python.debugpy@2026.6.0'
    'ms-python.python@2026.8.0'
    'ms-python.vscode-pylance@2026.4.1'
    'ms-python.vscode-python-envs@1.38.0'
    'ms-toolsai.jupyter@2025.9.1'
    'ms-toolsai.jupyter-keymap@1.1.2'
    'ms-toolsai.jupyter-renderers@1.3.0'
    'ms-toolsai.vscode-jupyter-cell-tags@0.1.9'
    'ms-toolsai.vscode-jupyter-slideshow@0.1.6'
    'ms-vscode-remote.remote-containers@0.469.0'
    'ms-vscode-remote.remote-ssh@0.128.0'
    'ms-vscode-remote.remote-ssh-edit@0.87.0'
    'ms-vscode-remote.remote-wsl@0.104.3'
    'ms-vscode-remote.vscode-remote-extensionpack@0.26.0'
    'ms-vscode.azurecli@0.6.0'
    'ms-vscode.makefile-tools@0.12.17'
    'ms-vscode.powershell@2025.4.0'
    'ms-vscode.remote-explorer@0.5.0'
    'ms-vscode.remote-server@1.5.3'
    'ms-vscode.theme-markdownkit@0.1.4'
    'ms-vscode.theme-materialkit@0.1.4'
    'ms-vscode.vscode-chat-customizations-evaluations@1.0.9'
    'ms-vscode.vscode-node-azure-pack@1.8.2'
    'ms-windows-ai-studio.windows-ai-studio@1.6.15'
    'postman.postman-for-vscode@1.19.1'
    'redhat.vscode-xml@0.29.3'
    'redhat.vscode-yaml@1.24.0'
    'tomoki1207.pdf@1.2.2'
    'vscode-icons-team.vscode-icons@13.0.0'
    'zhuangtongfa.material-theme@3.20.2'
)

$failedExtensions = [System.Collections.Generic.List[string]]::new()
$installedCount = 0

foreach ($extension in $extensions) {
    $extensionToInstall = if ($UseRecordedVersions) {
        $extension
    } else {
        $extension.Split('@')[0]
    }

    if ($PSCmdlet.ShouldProcess($extensionToInstall, 'Install VS Code extension')) {
        & $codeCommand --install-extension $extensionToInstall --force
        if ($LASTEXITCODE -ne 0) {
            $failedExtensions.Add($extensionToInstall)
            Write-Warning "Installation failed for '$extensionToInstall' (exit code $LASTEXITCODE)."
        } else {
            $installedCount++
        }
    }
}

if ($failedExtensions.Count -gt 0) {
    throw "Failed to install $($failedExtensions.Count) extension(s): $($failedExtensions -join ', ')"
}

if (-not $WhatIfPreference) {
    Write-Host "Installed or already present: $installedCount extension(s)."
}
