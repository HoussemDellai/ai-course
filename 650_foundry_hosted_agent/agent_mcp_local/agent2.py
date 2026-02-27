import os
import asyncio
from typing import Annotated
from random import randint
from pydantic import Field
from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework.azure import AzureOpenAIResponsesClient
from azure.identity import AzureCliCredential, DefaultAzureCredential

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_weather(
    location: Annotated[str, Field(description="The location to get the weather for.")],
) -> str:
    """Get the weather for a given location."""
    conditions = ["sunny", "cloudy", "rainy", "stormy"]
    return f"The weather in {location} is {conditions[randint(0, 3)]} with a high of {randint(10, 30)}°C."


def get_menu_specials() -> str:
    """Get today's menu specials."""
    return """
    Special Soup: Clam Chowder
    Special Salad: Cobb Salad
    Special Drink: Chai Tea
    """


async def main():
    # Agent(
    #     client=AzureOpenAIResponsesClient(credential=DefaultAzureCredential(), project_endpoint=os.getenv("AZURE_AI_PROJECT_ENDPOINT"), deployment_name=os.getenv("AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME")),
    #     instructions="You are a helpful assistant"
    # ) as agent
    # response = await agent.run("Hello!")

    client = AzureOpenAIResponsesClient(
        credential=AzureCliCredential(),
        project_endpoint=os.getenv("AZURE_AI_PROJECT_ENDPOINT"),
        deployment_name=os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME"),
        tools=[get_weather, get_menu_specials],
    ).as_agent(instructions="You are a helpful assistant")

    # client=AzureOpenAIResponsesClient(
    #     credential=AzureCliCredential(),
    #     project_endpoint=os.getenv("AZURE_AI_PROJECT_ENDPOINT"),
    #     deployment_name=os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    #     ),
    # client = AzureOpenAIChatClient(
    #     api_key="",
    #     endpoint="",
    #     deployment_name="",
    #     api_version="",
    # )

    agent = Agent(
        client=client,
        instructions="You are a helpful assistant that can provide weather and restaurant information.",
        tools=[get_weather, get_menu_specials],
    )

    response = await agent.run(
        "What's the weather in Amsterdam and what are today's specials?"
    )
    print(response)

    """
    Output:
    The weather in Amsterdam is sunny with a high of 22°C. Today's specials include
    Clam Chowder soup, Cobb Salad, and Chai Tea as the special drink.
    """


if __name__ == "__main__":
    asyncio.run(main())
