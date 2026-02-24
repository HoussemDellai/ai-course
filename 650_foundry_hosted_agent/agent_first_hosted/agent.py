# https://github.com/microsoft/agent-framework/blob/main/python/samples/01-get-started/01_hello_agent.py

import asyncio
import os

from agent_framework.azure import AzureOpenAIResponsesClient
from azure.ai.agentserver.agentframework import from_agent_framework
from azure.identity.aio import DefaultAzureCredential, AzureCliCredential
from agent_framework.azure import AzureAIAgentClient

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

"""
Environment variables:
  AZURE_AI_PROJECT_ENDPOINT      — Your Azure AI Foundry project endpoint
  AZURE_AI_MODEL_DEPLOYMENT_NAME — Model deployment name (e.g. gpt-5.2)
"""


async def main():
    async with (
        AzureCliCredential() as credential,
        AzureAIAgentClient(
            project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
            model_deployment_name=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
            credential=credential,
        ) as client,
    ):
        agent = client.create_agent(
            name="SeattleHotelAgent",
            instructions="You are a friendly assistant. Keep your answers brief.",
        )

    server = from_agent_framework(agent)
    await server.run_async()

if __name__ == "__main__":
    asyncio.run(main())
