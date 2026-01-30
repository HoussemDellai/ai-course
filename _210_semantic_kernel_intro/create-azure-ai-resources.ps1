# Create Azure AI Services and OpenAI resources

$rgName = "rg-azure-ai-00135-prod"
$aiServiceName = "ai-services-00135-prod" # should be unique
$location = "francecentral"
$llmDeploymentName = "gpt-4o"
$llmModelVersion = "2024-08-06"

### 1. Create a resource group

az group create -n $rgName -l $location

## Create an Azure AI Services resource

az cognitiveservices account create -n $aiServiceName -g $rgName --kind AIServices --sku S0 --custom-domain $aiServiceName --location $location

## Creating deployment for ChatGPT 4o model

az cognitiveservices account deployment create -n $aiServiceName -g $rgName `
    --deployment-name $llmDeploymentName `
    --model-name $llmDeploymentName `
    --model-version $llmModelVersion `
    --model-format OpenAI `
    --sku-capacity "150" `
    --sku-name "GlobalStandard"

## Create a Hub and Project for AI Foundry

az ml workspace create --kind hub -g $rgName -n hub-demo

$hubId=$(az ml workspace show -g $rgName -n hub-demo --query id -o tsv)

az ml workspace create --kind project --hub-id $hubId -g $rgName -n project-demo

## Create a connection.yml file to connect AI Services to the Hub

$endpoint=$(az cognitiveservices account show -n $aiServiceName -g $rgName --query properties.endpoint)
$api_key=$(az cognitiveservices account keys list -n $aiServiceName -g $rgName --query key1)
$ai_services_resource_id=$(az cognitiveservices account show -n $aiServiceName -g $rgName --query id)

@"
name: ai-service-connection
type: azure_ai_services
endpoint: $endpoint
api_key: $api_key
ai_services_resource_id: $ai_services_resource_id
"@ > connection.yml

az ml connection create --file connection.yml -g $rgName --workspace-name hub-demo

# Create the .env file for the python code

@"
GLOBAL_LLM_SERVICE="AzureOpenAI"
AZURE_OPENAI_ENDPOINT=$endpoint
AZURE_OPENAI_API_KEY=$api_key
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME="$llmDeploymentName"
AZURE_OPENAI_API_VERSION="2024-06-01"
"@ > .env