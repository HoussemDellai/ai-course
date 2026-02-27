import asyncio
import os

from agent_framework.azure import AzureOpenAIResponsesClient
from azure.identity import AzureCliCredential
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

"""
Environment variables:
  AZURE_AI_PROJECT_ENDPOINT      — Your Azure AI Foundry project endpoint
  AZURE_AI_MODEL_DEPLOYMENT_NAME — Model deployment name (e.g. gpt-4o)
"""


async def main() -> None:
    
    credential = AzureCliCredential()
    client = AzureOpenAIResponsesClient(
        project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
        deployment_name=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential,
    )

    agent = client.as_agent(
        name="AgentSimple",
        instructions="You are a friendly assistant. Keep your answers brief.",
    )
    
    # Non-streaming: get the complete response at once
    result = await agent.run("What is the capital of Tunisia?")
    print(f"Agent: {result}")

    # Streaming: receive tokens as they are generated
    print("Agent (streaming): ", end="", flush=True)
    async for chunk in agent.run("Tell me the history of Tunisia in 3 sentences.", stream=True):
        if chunk.text:
            print(chunk.text, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(main())