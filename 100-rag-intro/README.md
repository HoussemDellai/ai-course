# Introduction to RAG with Azure OpenAI

## Introduction

This repository contains the code and instructions to create a RAG (Retrieval Augmented Generation) model using Azure OpenAI.

## Create Azure AI Search resource

```sh
$rgName = "rg-openai-course"
```

### 1. Create a resource group

```sh
az group create -n $rgName -l swedencentral
```

### 2. Create a search service

```sh
az search service create -n ai-search-swc -g $rgName --sku free
```

### 3. Get the admin key

```sh
az search admin-key show --service-name ai-search-swc -g $rgName
```

### 4. Get the query key

```sh
az search query-key list --service-name ai-search-swc -g $rgName
```

## Create an Azure OpenAI resource

```sh
az cognitiveservices account create -n az-openai-swc -g $rgName --kind OpenAI --sku S0 --location swedencentral
```

### Get the endpoint URL

```sh
# az cognitiveservices account show -n az-openai-swc -g $rgName --query endpoint

az cognitiveservices account keys list -n az-openai-swc -g $rgName
```

## Creating deployment for ChatGPT 4

```sh
az cognitiveservices account deployment create -n az-openai-swc -g $rgName `
    --deployment-name gpt-4o `
    --model-name gpt-4o `
    --model-version "2024-05-13" `
    --model-format OpenAI `
    --sku-capacity "1" `
    --sku-name "Standard"
```

Get the key for the deployment

```sh
az cognitiveservices account keys list -n az-openai-swc -g $rgName
```

## Create an embedding model

Replace ` with \ if you are using Linux or MacOS.

```sh
az cognitiveservices account deployment create -n az-openai-swc -g $rgName `
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

## Get the access keys