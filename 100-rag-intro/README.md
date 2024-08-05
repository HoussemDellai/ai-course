# Introduction to RAG with Azure OpenAI

## Introduction

This repository contains the code and instructions to create a RAG (Retrieval Augmented Generation) model using Azure OpenAI.

## Create Azure AI Search resource

```sh
$rgName = "rg-openai-course1"
$location = "swedencentral"
$aiSearchName = "ai-search-swc-demo"
$aiServiceName = "ai-services-swc-demo"
```

### 1. Create a resource group

```sh
az group create -n $rgName -l $location
```

### 2. Create a search service

```sh
az search service create -n $aiSearchName -g $rgName --sku free
```

### 3. Get the admin key

```sh
az search admin-key show --service-name $aiSearchName -g $rgName
# {
#   "primaryKey": "4wIdp9wU2xwTM5ltGro4wNF1VPXwPcrrHMuoy47CYeAzSxxxxxxxx",
#   "secondaryKey": "oa1LM4JA47W4lby8wa8cfOvBKif8I4CidFMTHG71yPAzxxxxxxx"
# }
```

### 4. Get the query key

```sh
az search query-key list --service-name $aiSearchName -g $rgName
# [
#   {
#     "key": "Ma8h8QHqT8R7vU4EtC8vzuMrmfNEqwvJOqZK6vdJ8dAzSeDhqU7f",
#     "name": null
#   }
# ]
```

## Create an Azure OpenAI resource

```sh
az cognitiveservices account create -n $aiServiceName -g $rgName --kind AIServices --sku S0 --location $location
```

### Get the endpoint URL

```sh
az cognitiveservices account show -n $aiServiceName -g $rgName --query properties.endpoint
# "https://swedencentral.api.cognitive.microsoft.com/"

az cognitiveservices account keys list -n $aiServiceName -g $rgName
# {
#   "key1": "78f5592e1f70494dabd1a4040a61a96a",
#   "key2": "4f23266a2eb0475c8a0112044e03c4d1"
# }
```

## Creating deployment for ChatGPT 4

```sh
az cognitiveservices account deployment create -n $aiServiceName -g $rgName `
    --deployment-name gpt-4o `
    --model-name gpt-4o `
    --model-version "2024-05-13" `
    --model-format OpenAI `
    --sku-capacity "1" `
    --sku-name "Standard"
```

## Create an embedding model

Replace ` with \ if you are using Linux or MacOS.

```sh
az cognitiveservices account deployment create -n $aiServiceName -g $rgName `
    --deployment-name text-embedding-3-large `
    --model-name text-embedding-3-large `
    --model-version "1" `
    --model-format OpenAI `
    --sku-capacity "1" `
    --sku-name "Standard"
```
## Create a Hub and Project in Azure AI Studio

### Create a Hub

```sh
az extension add -n ml
az extension update -n ml

az ml workspace create --kind hub -g $rgName -n hub-demo
```

### Create a Project

Creating a new project using Azure CLI like the following is not yet supported. You can create a project using the Azure AI studio.

```sh
$hubId=$(az ml workspace show -g $rgName -n hub-demo --query id -o tsv)

az ml workspace create --kind project --hub-id $hubId -g $rgName -n project-demo
```

### Confirm the resources

Confirm you have the folloeing resources in your Azure portal.

![](images/resources.png)