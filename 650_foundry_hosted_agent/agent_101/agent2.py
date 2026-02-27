import asyncio
import os

# from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import AzureCliCredential

from azure.ai.agentserver.agentframework import from_agent_framework

from dotenv import load_dotenv

load_dotenv(override=True)

async def main():
    async with (
        AzureCliCredential() as credential,
        AzureAIAgentClient(
            project_endpoint=os.getenv("AZURE_AI_PROJECT_ENDPOINT"),
            model_deployment_name=os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME"),
            credential=credential,
            agent_name="HelperAgent",
        ).as_agent(instructions="You are a helpful assistant.") as agent,
    ):
        server = from_agent_framework(agent)
        await server.run_async()
        # result = await agent.run("Hello!")
        # print(result.text)

    # async with (
    #     AzureCliCredential() as credential,
    #     AzureAIAgentClient(
    #         project_endpoint=os.getenv("AZURE_AI_PROJECT_ENDPOINT"),
    #         model_deployment_name=os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME"),
    #         credential=credential,
    #         agent_name="HelperAgent",
    #     ).as_agent(instructions="You are a helpful assistant.") as agent,
    # ):
    #     result = await agent.run("Hello!")
    #     print(result.text)


asyncio.run(main())
