---
title: Understanding Azure OpenAI Service deployment types
titleSuffix: Azure AI services
description: Learn how to use Azure OpenAI deployment types | Global-Standard | Standard | Provisioned.
#services: cognitive-services
author: mrbullwinkle
manager: nitinme
ms.service: azure-ai-openai
ms.topic: how-to
ms.date: 05/19/2024
ms.author: mbullwin
---

# Azure OpenAI deployment types

Azure OpenAI provides customers with choices on the hosting structure that fits their business and usage patterns. The service offers two main types of deployment: **standard** and **provisioned**. Standard is offered with a global deployment option, routing traffic globally to provide higher throughput. All deployments can perform the exact same inference operations, however the billing, scale and performance are substantially different. As part of your solution design, you will need to make two key decisions:

- **Data residency needs**: global vs. regional resources  
- **Call volume**: standard vs. provisioned

## Global versus regional deployment types

For standard deployments you have an option of two types of configurations within your resource – **global** or **regional**. Global standard is the recommended starting point for development and experimentation. Global deployments leverage Azure's global infrastructure, dynamically route customer traffic to the data center with best availability for the customer’s inference requests. With global deployments there are higher initial throughput limits, though your latency may vary at high usage levels. For customers that require the lower latency variance at large workload usage, we recommend purchasing provisioned throughput.

Our global deployments will be the first location for all new models and features. Customers with very large throughput requirements should consider our provisioned deployment offering.

## Deployment types

Azure OpenAI offers three types of deployments. These provide a varied level of capabilities that provide trade-offs on: throughput, SLAs, and price. Below is a summary of the options followed by a deeper description of each.

| **Offering** | **Global-Standard** <sup>**1**</sup> | **Standard** | **Provisioned**  |
|---|:---|:---|:---|
| **Best suited for**      | Applications that don’t require data residency. Recommended starting place for customers. | For customers with data residency requirements. Optimized for low to medium volume. | Real-time scoring for large consistent volume. Includes the highest commitments and limits.|
| **How it works**         | Traffic may be routed anywhere in the world | | |
| **Getting started**      | [Model deployment](./create-resource.md) | [Model deployment](./create-resource.md) | [Provisioned onboarding](./provisioned-throughput-onboarding.md) |
| **Cost**                 | [Baseline](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/) | [Regional Pricing](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/) | May experience cost savings for consistent usage |
| **What you get**         | Easy access to all new models with highest default pay-per-call limits.<br><br> Customers with high volume usage may see higher latency variability | Easy access with [SLA on availability](https://azure.microsoft.com/support/legal/sla/). Optimized for low to medium volume workloads with high burstiness. <br><br>Customers with high consistent volume may experience greater latency variability. | Regional access with very high & predictable throughput. Determine throughput per PTU using the provided [capacity calculator](./provisioned-throughput-onboarding.md#estimate-provisioned-throughput-and-cost) |
| **What you don’t get**   | ❌Data residency guarantees | ❌High volume w/consistent low latency | ❌Pay-per-call flexibility |
| **Per-call Latency**     | Optimized for real-time calling & low to medium volume usage. Customers with high volume usage may see higher latency variability. Threshold set per model | Optimized for real-time calling & low to medium volume usage. Customers with high volume usage may see higher latency variability. Threshold set per model | Optimized for real-time. |
| **Sku Name in code**     |    `GlobalStandard`               | `Standard`   |      `ProvisionedManaged`       |
| **Billing model**        | Pay-per-token | Pay-per-token | Monthly Commitments |

<sup>**1**</sup> Global-Standard deployment type is currently in preview.

## Provisioned

Provisioned deployments allow you to specify the amount of throughput you require in a deployment. The service then allocates the necessary model processing capacity and ensures it's ready for you. Throughput is defined in terms of provisioned throughput units (PTU) which is a normalized way of representing the throughput for your deployment. Each model-version pair requires different amounts of PTU to deploy and provide different amounts of throughput per PTU. Learn more from our [Provisioned throughput concepts article](../concepts/provisioned-throughput.md).

## Standard

Standard deployments provide a pay-per-call billing model on the chosen model. Provides the fastest way to get started as you only pay for what you consume. Models available in each region as well as throughput may be limited.  

Standard deployments are optimized for low to medium volume workloads with high burstiness. Customers with high consistent volume may experience greater latency variability.

## Global standard (preview)

Global deployments are available in the same Azure OpenAI resources as non-global offers but allow you to leverage Azure's global infrastructure to dynamically route traffic to the data center with best availability for each request.  Global standard will provide the highest default quota for new models and eliminates the need to load balance across multiple resources.  

The deployment type is optimized for low to medium volume workloads with high burstiness. Customers with high consistent volume may experience greater latency variability. The threshold is set per model. See the [quotas page to learn more](./quota.md).  

For customers that require the lower latency variance at large workload usage, we recommend purchasing provisioned throughput.

### How to disable access to global deployments in your subscription

Azure Policy helps to enforce organizational standards and to assess compliance at-scale. Through its compliance dashboard, it provides an aggregated view to evaluate the overall state of the environment, with the ability to drill down to the per-resource, per-policy granularity. It also helps to bring your resources to compliance through bulk remediation for existing resources and automatic remediation for new resources. [Learn more about Azure Policy and specific built-in controls for AI services](/azure/ai-services/security-controls-policy).

You can use the following policy to disable access to Azure OpenAI global standard deployments.

```json
{
    "mode": "All",
    "policyRule": {
        "if": {
            "allOf": [
                {
                    "field": "type",
                    "equals": "Microsoft.CognitiveServices/accounts/deployments"
                },
                {
                    "field": "Microsoft.CognitiveServices/accounts/deployments/sku.name",
                    "equals": "GlobalStandard"
                }
            ]
        }
    }
}
```

## Deploy models

:::image type="content" source="../media/deployment-types/deploy-models.png" alt-text="Screenshot that shows the model deployment dialog in Azure OpenAI Studio with three deployment types highlighted." lightbox="../media/deployment-types/deploy-models.png":::

To learn about creating resources and deploying models refer to the [resource creation guide](./create-resource.md).

## See also

- [Quotas & limits](./quota.md)
- [Provisioned throughput units (PTU) onboarding](./provisioned-throughput-onboarding.md)
- [Provisioned throughput units (PTU) getting started](./provisioned-get-started.md)
