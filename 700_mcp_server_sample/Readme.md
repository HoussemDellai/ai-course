# Implementing sample MCP Server

This lab is based on Microsoft documentation for MCP Server. It provides a sample implementation of an MCP server that can be used to test and demonstrate the capabilities of the MCP protocol [https://learn.microsoft.com/en-us/dotnet/ai/quickstarts/build-mcp-server](https://learn.microsoft.com/en-us/dotnet/ai/quickstarts/build-mcp-server).

## Create the project

Install the MCP Server template

```sh
dotnet new install Microsoft.Extensions.AI.Templates
```

Create a new MCP server app with the dotnet new mcpserver command:

```sh
dotnet new mcpserver -n SampleMcpServer
```

Navigate to the SampleMcpServer directory:

```sh
cd SampleMcpServer
```

Build the project:

```sh
dotnet build
```

Update the <PackageId> in the .csproj file to be unique on NuGet.org, for example <NuGet.org username>.SampleMcpServer.