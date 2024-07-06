---
title: 'Speech to text with Azure OpenAI Service'
titleSuffix: Azure OpenAI
description: Use the Azure OpenAI Whisper model for speech to text.
manager: nitinme
ms.service: azure-ai-openai
ms.custom: devx-track-python
ms.topic: quickstart
ms.date: 3/19/2024
ms.reviewer: v-baolianzou
ms.author: eur
author: eric-urban
recommendations: false
zone_pivot_groups: openai-whisper
---

# Quickstart: Speech to text with the Azure OpenAI Whisper model

In this quickstart, you use the Azure OpenAI Whisper model for speech to text. 

The file size limit for the Azure OpenAI Whisper model is 25 MB. If you need to transcribe a file larger than 25 MB, you can use the Azure AI Speech [batch transcription](../speech-service/batch-transcription-create.md#use-a-whisper-model) API.

## Prerequisites

- An Azure subscription - [Create one for free](https://azure.microsoft.com/free/cognitive-services?azure-portal=true).
- Access granted to Azure OpenAI Service in the desired Azure subscription.
- An Azure OpenAI resource with a `whisper` model deployed in a supported region. [Whisper model regional availability](./concepts/models.md#whisper-models). For more information, see [Create a resource and deploy a model with Azure OpenAI](how-to/create-resource.md).

> [!NOTE]
> Currently, you must submit an application to access Azure OpenAI Service. To apply for access, complete [this form](https://aka.ms/oai/access). 

## Set up

### Retrieve key and endpoint

To successfully make a call against Azure OpenAI, you'll need an **endpoint** and a **key**.

|Variable name | Value |
|--------------------------|-------------|
| `AZURE_OPENAI_ENDPOINT`               | This value can be found in the **Keys & Endpoint** section when examining your resource from the Azure portal. Alternatively, you can find the value in the **Azure OpenAI Studio** > **Playground** > **Code View**. An example endpoint is: `https://aoai-docs.openai.azure.com/`.|
| `AZURE_OPENAI_API_KEY` | This value can be found in the **Keys & Endpoint** section when examining your resource from the Azure portal. You can use either `KEY1` or `KEY2`.|

Go to your resource in the Azure portal. The **Endpoint and Keys** can be found in the **Resource Management** section. Copy your endpoint and access key as you'll need both for authenticating your API calls. You can use either `KEY1` or `KEY2`. Always having two keys allows you to securely rotate and regenerate keys without causing a service disruption.

:::image type="content" source="media/quickstarts/endpoint.png" alt-text="Screenshot of the overview UI for an Azure OpenAI resource in the Azure portal with the endpoint & access keys location circled in red." lightbox="media/quickstarts/endpoint.png":::

Create and assign persistent environment variables for your key and endpoint.

### Environment variables

# [Command Line](#tab/command-line)

```CMD
setx AZURE_OPENAI_API_KEY "REPLACE_WITH_YOUR_KEY_VALUE_HERE" 
```

```CMD
setx AZURE_OPENAI_ENDPOINT "REPLACE_WITH_YOUR_ENDPOINT_HERE" 
```

# [PowerShell](#tab/powershell)

```powershell
[System.Environment]::SetEnvironmentVariable('AZURE_OPENAI_API_KEY', 'REPLACE_WITH_YOUR_KEY_VALUE_HERE', 'User')
```

```powershell
[System.Environment]::SetEnvironmentVariable('AZURE_OPENAI_ENDPOINT', 'REPLACE_WITH_YOUR_ENDPOINT_HERE', 'User')
```

# [Bash](#tab/bash)

```Bash
echo export AZURE_OPENAI_API_KEY="REPLACE_WITH_YOUR_KEY_VALUE_HERE" >> /etc/environment && source /etc/environment
```

```Bash
echo export AZURE_OPENAI_ENDPOINT="REPLACE_WITH_YOUR_ENDPOINT_HERE" >> /etc/environment && source /etc/environment
```
---


::: zone pivot="rest-api"

[!INCLUDE [REST API quickstart](includes/whisper-rest.md)]

::: zone-end

::: zone pivot="programming-language-powershell"

[!INCLUDE [PowerShell quickstart](includes/whisper-powershell.md)]

::: zone-end

::: zone pivot="programming-language-python"

[!INCLUDE [Python quickstart](includes/whisper-python.md)]

::: zone-end

## Clean up resources

If you want to clean up and remove an Azure OpenAI resource, you can delete the resource. Before deleting the resource, you must first delete any deployed models.

- [Portal](../multi-service-resource.md?pivots=azportal#clean-up-resources)
- [Azure CLI](../multi-service-resource.md?pivots=azcli#clean-up-resources)

## Next steps

* Learn more about how to work with Whisper models with the Azure AI Speech [batch transcription](../speech-service/batch-transcription-create.md) API.
* For more examples, check out the [Azure OpenAI Samples GitHub repository](https://aka.ms/AOAICodeSamples)
