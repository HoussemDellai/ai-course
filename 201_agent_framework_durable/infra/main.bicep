targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
@allowed([ 'westus2', 'westus3', 'eastus2'])
@metadata({
  azd: {
    type: 'location'
  }
})
param location string

@description('Optional numeric suffix for resource names (e.g., 56093778). Auto-generated if not provided.')
param nameSuffix string = ''

@description('Id of the user or app to assign application roles')
param principalId string = ''

param apiServiceName string = ''
param apiUserAssignedIdentityName string = ''
param applicationInsightsName string = ''
param logAnalyticsName string = ''
param resourceGroupName string = ''
param storageAccountName string = ''
param dtsSkuName string = 'Consumption'
param dtsName string = ''

@allowed(['gpt-4o-mini'])
param chatModelName string = 'gpt-4o-mini'

import * as regionSelector from './app/util/region-selector.bicep'
var abbrs = loadJsonContent('./abbreviations.json')

// Auto-generate suffix if not provided
var autoSuffix = toLower(take(uniqueString(subscription().id, environmentName, location), 8))
var actualSuffix = !empty(nameSuffix) ? nameSuffix : autoSuffix

// Base name for all resources
var resourceToken = 'durableagents'

var tags = { 'azd-env-name': environmentName }
var functionAppName = !empty(apiServiceName) ? apiServiceName : '${abbrs.webSitesFunctions}api-${resourceToken}-${actualSuffix}'
var deploymentStorageContainerName = 'app-package-${take(functionAppName, 32)}-${take(toLower(uniqueString(functionAppName, resourceToken)), 7)}'

var storageAccountActualName = !empty(storageAccountName) ? storageAccountName : '${abbrs.storageStorageAccounts}${resourceToken}${actualSuffix}'

// Organize resources in a resource group
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: !empty(resourceGroupName) ? resourceGroupName : '${abbrs.resourcesResourceGroups}${environmentName}'
  location: location
  tags: tags
}

// User assigned managed identity to be used by the function app
module apiUserAssignedIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.1' = {
  name: 'apiUserAssignedIdentity'
  scope: rg
  params: {
    location: location
    tags: tags
    name: !empty(apiUserAssignedIdentityName) ? apiUserAssignedIdentityName : '${abbrs.managedIdentityUserAssignedIdentities}api-${resourceToken}-${actualSuffix}'
  }
}

// Backing storage for Azure Functions api
module storage 'br/public:avm/res/storage/storage-account:0.8.3' = {
  name: 'storage'
  scope: rg
  params: {
    name: storageAccountActualName
    location: location
    tags: tags
    skuName: 'Standard_LRS'
    blobServices: {
      containers: [{name: deploymentStorageContainerName}, {name: 'snippets'}]
    }
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

var StorageBlobDataOwner = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
var StorageQueueDataContributor = '974c5e8b-45b9-4653-ba55-5f855dd0fb88'

// Allow access from api to blob storage using a managed identity
module blobRoleAssignmentApi 'app/rbac/storage-access.bicep' = {
  name: 'blobRoleAssignmentapi'
  scope: rg
  params: {
    storageAccountName: storage.outputs.name
    roleDefinitionID: StorageBlobDataOwner
    principalID: apiUserAssignedIdentity.outputs.principalId
  }
}

// Allow access from api to queue storage using a managed identity
module queueRoleAssignmentApi 'app/rbac/storage-access.bicep' = {
  name: 'queueRoleAssignmentapi'
  scope: rg
  params: {
    storageAccountName: storage.outputs.name
    roleDefinitionID: StorageQueueDataContributor
    principalID: apiUserAssignedIdentity.outputs.principalId
  }
}

// Monitor application with Azure Monitor
module monitoring 'app/monitoring.bicep' = {
  name: 'monitoring'
  scope: rg
  params: {
    location: location
    tags: tags
    logAnalyticsName: !empty(logAnalyticsName) ? logAnalyticsName : '${abbrs.operationalInsightsWorkspaces}${resourceToken}-${actualSuffix}'
    applicationInsightsName: !empty(applicationInsightsName) ? applicationInsightsName : '${abbrs.insightsComponents}${resourceToken}-${actualSuffix}'
  }
}

var MonitoringMetricsPublisher = '3913510d-42f4-4e42-8a64-420c390055eb' // Monitoring Metrics Publisher role ID

// Allow access from api to application insights using a managed identity
module appInsightsRoleAssignmentApi './app/rbac/appinsights-access.bicep' = {
  name: 'appInsightsRoleAssignmentapi'
  scope: rg
  params: {
    appInsightsName: monitoring.outputs.applicationInsightsName
    roleDefinitionID: MonitoringMetricsPublisher
    principalID: apiUserAssignedIdentity.outputs.principalId
  }
}

// Azure OpenAI for chat
module openai './app/ai/cognitive-services.bicep' = {
  name: 'openai'
  scope: rg
  params: {
    location: regionSelector.getAiServicesRegion(location, chatModelName)
    tags: tags
    chatModelName: chatModelName
    aiServicesName: '${abbrs.cognitiveServicesAccounts}${resourceToken}-${actualSuffix}'
  }
}

// Assign Cognitive Services OpenAI User role to the managed identity for OpenAI access
// This role enables: using chat models and AI agents through AIServices
var CognitiveServicesOpenAIUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
module openaiRoleAssignment 'app/rbac/openai-access.bicep' = {
  name: 'openaiRoleAssignment'
  scope: rg
  params: {
    openAIAccountName: openai.outputs.aiServicesName
    roleDefinitionId: CognitiveServicesOpenAIUser
    principalId: apiUserAssignedIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Assign Cognitive Services OpenAI User role to the developer (for local development)
module openaiRoleAssignmentDeveloper 'app/rbac/openai-access.bicep' = if (!empty(principalId)) {
  name: 'openaiRoleAssignmentDeveloper'
  scope: rg
  params: {
    openAIAccountName: openai.outputs.aiServicesName
    roleDefinitionId: CognitiveServicesOpenAIUser
    principalId: principalId
    principalType: 'User'
  }
}

module api './app/api.bicep' = {
  name: 'api'
  scope: rg
  params: {
    name: functionAppName
    location: regionSelector.getFlexConsumptionRegion(location)
    tags: tags
    resourceToken: resourceToken
    actualSuffix: actualSuffix
    applicationInsightsName: monitoring.outputs.applicationInsightsName
    storageAccountName: storage.outputs.name
    deploymentStorageContainerName: deploymentStorageContainerName
    identityId: apiUserAssignedIdentity.outputs.resourceId
    identityClientId: apiUserAssignedIdentity.outputs.clientId
    appSettings: {
      AGENTS_MODEL_DEPLOYMENT_NAME: openai.outputs.chatDeploymentName
      AZURE_OPENAI_ENDPOINT: openai.outputs.azureOpenAIServiceEndpoint
      PROJECT_ENDPOINT: openai.outputs.aiFoundryProjectEndpoint
      AZURE_CLIENT_ID: apiUserAssignedIdentity.outputs.clientId
      DURABLE_TASK_SCHEDULER_CONNECTION_STRING: 'Endpoint=${dts.outputs.dts_URL};Authentication=ManagedIdentity;ClientID=${apiUserAssignedIdentity.outputs.clientId}'
      TASKHUB_NAME: dts.outputs.TASKHUB_NAME
    }
  }
  dependsOn: [
    blobRoleAssignmentApi
    queueRoleAssignmentApi
    appInsightsRoleAssignmentApi
    openaiRoleAssignment
  ]
}

// Durable Task Scheduler
module dts './app/dts.bicep' = {
  scope: rg
  name: 'dtsResource'
  params: {
    name: !empty(dtsName) ? dtsName : '${abbrs.dts}${resourceToken}-${actualSuffix}'
    location: location
    tags: tags
    ipAllowlist: [
      '0.0.0.0/0'
    ]
    skuName: dtsSkuName
  }
}

// Allow access from durable function to storage account using a user assigned managed identity
module dtsRoleAssignment 'app/rbac/dts-Access.bicep' = {
  name: 'dtsRoleAssignment'
  scope: rg
  params: {
   roleDefinitionID: '0ad04412-c4d5-4796-b79c-f76d14c8d402'
   principalID: apiUserAssignedIdentity.outputs.principalId
   principalType: 'ServicePrincipal'
   dtsName: dts.outputs.dts_NAME
  }
}

module dtsDashboardRoleAssignment 'app/rbac/dts-Access.bicep' = {
  name: 'dtsDashboardRoleAssignment'
  scope: rg
  params: {
   roleDefinitionID: '0ad04412-c4d5-4796-b79c-f76d14c8d402'
   principalID: principalId
   principalType: 'User'
   dtsName: dts.outputs.dts_NAME
  }
}

// ==================================
// Outputs
// ==================================
// Define outputs needed specifically for configuring local.settings.json
// Use 'azd env get-values' to retrieve these after provisioning.
// WARNING: Secrets (Keys, Connection Strings) are output directly and will be visible in deployment history.
// Output names directly match the corresponding keys in local.settings.json for easier mapping.

@description('Name of the resource group.')
output AZURE_RESOURCE_GROUP string = rg.name

@description('Endpoint for Azure OpenAI services. Output name matches the AZURE_OPENAI_ENDPOINT key in local settings.')
output AZURE_OPENAI_ENDPOINT string = openai.outputs.azureOpenAIServiceEndpoint

@description('AI Foundry project endpoint for Agent Service. Output name matches the PROJECT_ENDPOINT key in local settings.')
output PROJECT_ENDPOINT string = openai.outputs.aiFoundryProjectEndpoint

@description('Name of the deployed Azure Function App.')
output AZURE_FUNCTION_NAME string = api.outputs.SERVICE_API_NAME // Function App Name

@description('Connection string for the Azure Storage Account. Output name matches the AzureWebJobsStorage key in local settings.')
output AZUREWEBJOBSSTORAGE string = storage.outputs.primaryBlobEndpoint

@description('Name of the Durable Task Scheduler resource.')
output DTS_NAME string = dts.outputs.dts_NAME
