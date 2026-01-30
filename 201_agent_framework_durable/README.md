---
description: This Python sample demonstrates how to build and deploy a durable AI agent using Azure Functions and the Microsoft Agent Framework with persistent conversation threads.
page_type: sample
products:
- azure-functions
- azure-openai
- azure
urlFragment: durable-agents-quickstart-python
languages:
- python
- bicep
- azdeveloper
---

# Durable task extension for Microsoft Agent Framework using Azure Developer CLI

This template repository contains a durable AI agent reference sample built with Python and deployed to Azure using the Azure Developer CLI (`azd`). The sample demonstrates how to create an AI agent with persistent conversation threads using Azure Functions, Azure OpenAI, and the Microsoft Agent Framework. This sample demonstrates these key features:

* **Durable conversation threads**. The agent maintains conversation context across multiple interactions using durable orchestration, allowing for natural multi-turn conversations.
* **Microsoft Agent Framework integration**. Built on the standard Microsoft Agent Framework pattern for creating AI agents with Azure OpenAI.
* **Managed identity authentication**. Uses Azure managed identity for secure, secret-free connections to Azure OpenAI.

This project is designed to run on your local computer. You can also use GitHub Codespaces if available.

> [!IMPORTANT]
> This sample creates several resources. Make sure to delete the resource group after testing to minimize charges!

## Prerequisites

+ [Python 3.10 or later](https://www.python.org/downloads/)
+ [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local?tabs=v4%2Clinux%2Cpython%2Cportal%2Cbash#install-the-azure-functions-core-tools)
+ To use Visual Studio Code to run and debug locally:
  + [Visual Studio Code](https://code.visualstudio.com/)
  + [Azure Functions extension](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-azurefunctions)
+ [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) (for deployment)
+ [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd?tabs=winget-windows%2Cbrew-mac%2Cscript-linux&pivots=os-windows)
+ An Azure subscription with Microsoft.Web and Microsoft.CognitiveServices [registered resource providers](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-providers-and-types#register-resource-provider)

## Initialize the local project

You can initialize a project from this `azd` template in one of these ways:

+ Use this `azd init` command from an empty local (root) folder:

    ```shell
    azd init --template durable-agents-quickstart-python
    ```

    Supply an environment name, such as `durableagent` when prompted. In `azd`, the environment is used to maintain a unique deployment context for your app.

+ Clone the GitHub template repository locally using the `git clone` command:

    ```shell
    git clone https://github.com/anthonychu/durable-agents-quickstart-python.git
    cd durable-agents-quickstart-python
    ```

    You can also clone the repository from your own fork in GitHub.

## Follow the tutorial

You can follow the step-by-step tutorial for this sample at [](https://learn.microsoft.com/agent-framework/tutorials/agents/create-and-run-durable-agent?pivots=programming-language-python). The tutorial walks you through the code and deployment process in detail.
