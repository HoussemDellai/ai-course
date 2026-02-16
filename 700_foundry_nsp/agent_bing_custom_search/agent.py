import os
from agent_framework import ChatAgent
from agent_framework_azure_ai import AzureAIAgentClient

from azure.ai.agentserver.agentframework import from_agent_framework

from azure.identity import DefaultAzureCredential as SyncDefaultAzureCredential

from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential

from azure.ai.agents.models import BingCustomSearchTool

from azure.ai.projects import AIProjectClient

from dotenv import load_dotenv

load_dotenv()

# show all environment variables for debugging
for key, value in os.environ.items():
    print(f"{key}: {value}")

    
def create_agent() -> ChatAgent:

    syncCredential = SyncDefaultAzureCredential()

    project_client = AIProjectClient(
        endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
        credential=syncCredential,
    )

    bing_custom_search_connection_id = project_client.connections.get(os.environ["BING_CUSTOM_CONNECTION_NAME"]).id

    bing_custom_search_tool = BingCustomSearchTool(connection_id=bing_custom_search_connection_id, instance_name=os.environ["BING_CONFIGURATION_NAME"])

    asyncCredential = AsyncDefaultAzureCredential()

    chat_client = AzureAIAgentClient(
        project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
        model_deployment_name=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=asyncCredential,
    )

    agent = ChatAgent(
        chat_client=chat_client,
        name="agent-web-search",
        instructions=(
            "You are a helpful assistant that can search the web for current information. "
            "Use the Bing search tool to find up-to-date information and provide accurate, "
            "well-sourced answers. Always cite your sources when possible."
        ),
        tools=bing_custom_search_tool.definitions,
    )
    return agent


if __name__ == "__main__":
    from_agent_framework(lambda _: create_agent()).run()
