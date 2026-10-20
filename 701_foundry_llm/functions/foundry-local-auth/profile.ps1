$ErrorActionPreference = 'Stop'

Import-Module Az.Accounts -RequiredVersion '4.0.2'
Import-Module Az.CognitiveServices -RequiredVersion '1.15.0'
Disable-AzContextAutosave -Scope Process | Out-Null
