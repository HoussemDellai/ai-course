dotnet new web -n agui-server -o ./

dotnet add package Microsoft.Agents.AI.Hosting.AGUI.AspNetCore --prerelease
dotnet add package Azure.AI.OpenAI --prerelease
dotnet add package Azure.Identity
dotnet add package Microsoft.Extensions.AI.OpenAI --prerelease

dotnet run --urls http://localhost:8888