using System;
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;
using OpenAI.Chat;

AzureOpenAIClient azureOpenAIClient = new Azure.AI.OpenAI.AzureOpenAIClient(
  new Uri("https://ai-services-333-400.openai.azure.com/"),
  new AzureCliCredential());

ChatClient chatClient = azureOpenAIClient.GetChatClient(deploymentName: "gpt-4o-mini");
    // .GetChatClient("gpt-4o-mini")

AIAgent agent = chatClient.CreateAIAgent(instructions: "You are good at telling jokes.");

// AIAgent agent = new Azure.AI.OpenAI.AzureOpenAIClient(
//   new Uri("https://ai-services-333-400.openai.azure.com/"),
//   new AzureCliCredential())
//     .GetChatClient("gpt-4o-mini")
//     .CreateAIAgent(instructions: "You are good at telling jokes.");

Console.WriteLine(await agent.RunAsync("Tell me a joke about a pirate."));