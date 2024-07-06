---
title: Azure OpenAI Service model retirements
titleSuffix: Azure OpenAI
description: Learn about the model deprecations and retirements in Azure OpenAI.
ms.service: azure-ai-openai
ms.topic: conceptual
ms.date: 06/04/2024
ms.custom: 
manager: nitinme
author: mrbullwinkle
ms.author: mbullwin 
recommendations: false
---

# Azure OpenAI Service model deprecations and retirements

## Overview

Azure OpenAI Service models are continually refreshed with newer and more capable models. As part of this process, we deprecate and retire older models. This document provides information about the models that are currently available, deprecated, and retired.

### Terminology

* Retirement
	* When a model is retired, it's no longer available for use. Azure OpenAI Service deployments of a retired model always return error responses.
* Deprecation
	* When a model is deprecated, it's no longer available for new customers. It continues to be available for use by customers with existing deployments until the model is retired.

## Preretirement notification

Azure OpenAI notifies customers of active Azure OpenAI Service deployments for models with upcoming retirements. We notify customers of upcoming retirements as follows for each deployment:

* At least 60 days before retirement 
* At least 30 days before retirement 
* At retirement

Retirements are done on a rolling basis, region by region.

### Who is notified of upcoming retirements

Azure OpenAI notifies those who are members of the following roles for each subscription with a deployment of a model with an upcoming retirement.

* Owner
* Contributor
* Reader
* Monitoring contributor
* Monitoring reader

## How to get ready for model retirements and version upgrades

To prepare for model retirements and version upgrades, we recommend that customers evaluate their applications with the new models and versions and evaluate their behavior. We also recommend that customers update their applications to use the new models and versions before the retirement date.

For more information, see [How to upgrade to a new model or version](./model-versions.md).

## Current models

> [!NOTE]
> Not all models go through a deprecation period prior to retirement. Some models/versions only have a retirement date.

These models are currently available for use in Azure OpenAI Service.

| Model | Version | Retirement date |
| ---- | ---- | ---- |
| `gpt-35-turbo` | 0301 | No earlier than August 1, 2024 |
| `gpt-35-turbo`<br>`gpt-35-turbo-16k` | 0613 | No earlier than August 1, 2024 |
| `gpt-35-turbo` | 1106 | No earlier than Nov 17, 2024 |
| `gpt-35-turbo` | 0125 | No earlier than Feb 22, 2025 |
| `gpt-4`<br>`gpt-4-32k` | 0314 | No earlier than July 13, 2024 |
| `gpt-4`<br>`gpt-4-32k` | 0613 | No earlier than Sep 30, 2024 |
| `gpt-4` | 1106-preview | To be upgraded to `gpt-4` Version: `turbo-2024-04-09`, starting on June 10, 2024, or later **<sup>1</sup>** |
| `gpt-4` | 0125-preview |To be upgraded to `gpt-4` Version: `turbo-2024-04-09`, starting on June 10, 2024, or later  **<sup>1</sup>**  |
| `gpt-4` | vision-preview | To be upgraded to `gpt-4` Version: `turbo-2024-04-09`, starting on June 10, 2024, or later  **<sup>1</sup>** |
| `gpt-3.5-turbo-instruct` | 0914 | No earlier than Sep 14, 2025 |
| `text-embedding-ada-002` | 2 | No earlier than April 3, 2025 |
| `text-embedding-ada-002` | 1 | No earlier than April 3, 2025 |
| `text-embedding-3-small` | | No earlier than Feb 2, 2025 |
| `text-embedding-3-large` | | No earlier than Feb 2, 2025 |

 **<sup>1</sup>** We will notify all customers with these preview deployments at least two weeks before the start of the upgrades. We will publish an upgrade schedule detailing the order of regions and model versions that we will follow during the upgrades, and link to that schedule from here.


## Deprecated models

These models were deprecated on July 6, 2023 and will be retired on June 14, 2024. These models are no longer available for new deployments. Deployments created before July 6, 2023 remain available to customers until June 14, 2024. We recommend customers migrate their applications to deployments of replacement models before the June 14, 2024 retirement.

If you're an existing customer looking for information about these models, see [Legacy models](./legacy-models.md).

| Model | Deprecation date | Retirement date | Suggested replacement |
| --------- | --------------------- | ------------------- | -------------------- | 
| ada | July 6, 2023 | June 14, 2024 | babbage-002 |
| babbage | July 6, 2023 | June 14, 2024 | babbage-002 |
| curie | July 6, 2023 | June 14, 2024 | davinci-002 |
| davinci | July 6, 2023 | June 14, 2024 | davinci-002 |
| text-ada-001 | July 6, 2023 | June 14, 2024 | gpt-35-turbo-instruct |
| text-babbage-001 | July 6, 2023 | June 14, 2024 | gpt-35-turbo-instruct |
| text-curie-001 | July 6, 2023 | June 14, 2024 | gpt-35-turbo-instruct |
| text-davinci-002 | July 6, 2023 | June 14, 2024 | gpt-35-turbo-instruct |
| text-davinci-003 | July 6, 2023 | June 14, 2024 | gpt-35-turbo-instruct |
| code-cushman-001 | July 6, 2023 | June 14, 2024 | gpt-35-turbo-instruct |
| code-davinci-002 | July 6, 2023 | June 14, 2024 | gpt-35-turbo-instruct |
| text-similarity-ada-001 | July 6, 2023 | June 14, 2024 | text-embedding-3-small |
| text-similarity-babbage-001 | July 6, 2023 | June 14, 2024 | text-embedding-3-small |
| text-similarity-curie-001 | July 6, 2023 | June 14, 2024 | text-embedding-3-small |
| text-similarity-davinci-001 | July 6, 2023 | June 14, 2024 | text-embedding-3-small |
| text-search-ada-doc-001 | July 6, 2023 | June 14, 2024 | text-embedding-3-small |
| text-search-ada-query-001 | July 6, 2023 | June 14, 2024 | text-embedding-3-small |
| text-search-babbage-doc-001 | July 6, 2023 | June 14, 2024 | text-embedding-3-small |
| text-search-babbage-query-001 | July 6, 2023 | June 14, 2024 | text-embedding-3-small |
| text-search-curie-doc-001 | July 6, 2023 | June 14, 2024 | text-embedding-3-small |
| text-search-curie-query-001 | July 6, 2023 | June 14, 2024 | text-embedding-3-small |
| text-search-davinci-doc-001 | July 6, 2023 | June 14, 2024 | text-embedding-3-small |
| text-search-davinci-query-001 | July 6, 2023 | June 14, 2024 | text-embedding-3-small |
| code-search-ada-code-001 | July 6, 2023 | June 14, 2024 | text-embedding-3-small |
| code-search-ada-text-001 | July 6, 2023 | June 14, 2024 | text-embedding-3-small |
| code-search-babbage-code-001 | July 6, 2023 | June 14, 2024 | text-embedding-3-small |
| code-search-babbage-text-001 | July 6, 2023 | June 14, 2024 | text-embedding-3-small |

## Retirement and deprecation history

### June 4, 2024

Retirement date for legacy models updated by one month.

### April 24, 2024

Earliest retirement date for `gpt-35-turbo` 0301 and 0613 has been updated to August 1, 2024.

### March 13, 2024

We published this document to provide information about the current models, deprecated models, and upcoming retirements.

### February 23, 2024

We announced the upcoming in-place upgrade of `gpt-4` version `1106-preview` to `0125-preview` to start no earlier than March 8, 2024.

### November 30, 2023

The default version of `gpt-4` and `gpt-3-32k` was updated from `0314` to `0613` starting on November 30, 2023. The upgrade of `0314` deployments set for autoupgrade to `0613` was completed on December 3, 2023.

### July 6, 2023

We announced the deprecation of models with upcoming retirement on July 5, 2024.