az group create --name rg-openai-bicep --location swedencentral
az deployment group create --resource-group rg-openai-bicep --template-file main.bicep

