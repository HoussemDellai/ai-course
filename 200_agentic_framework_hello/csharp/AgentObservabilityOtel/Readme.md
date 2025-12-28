# Agent Observability with OpenTelemetry in ASP.NET Core MVC

src: [link for demo](https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/enable-observability?pivots=programming-language-csharp)

How to create the project and add the required packages:

```sh
dotnet new mvc -f net10.0 -n AgentObservabilityOtel

cd AgentObservabilityOtel

# Microsoft Agent Framework with Azure OpenAI
dotnet add package Azure.AI.OpenAI --prerelease
dotnet add package Azure.Identity
dotnet add package Microsoft.Agents.AI.OpenAI --prerelease

# add OpenTelemetry support
dotnet add package OpenTelemetry
dotnet add package OpenTelemetry.Exporter.Console
```
