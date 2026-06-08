import asyncio
from typing import Annotated

from agent_framework import Agent, FunctionInvocationContext, tool
from agent_framework.openai import OpenAIChatClient
from dotenv import load_dotenv
from pydantic import Field


# Define the function tool with explicit invocation context.
# The context parameter can also be declared as an untyped ``ctx`` parameter.
@tool(approval_mode="never_require")
def get_weather(
    location: Annotated[str, Field(description="The location to get the weather for.")],
    ctx: FunctionInvocationContext,
) -> str:
    """Get the weather for a given location."""
    # Extract the injected argument from the explicit context
    # user_id = ctx.kwargs.get("user_id", "unknown")

    # Simulate using the user_id for logging or personalization
    # print(f"Getting weather for user: {user_id}")

    return f"The weather in {location} is cloudy with a high of 15°C."


async def main() -> None:
    agent = Agent(
        client=OpenAIChatClient(
            base_url=f"http://gemma-4-31b-it-a100.gentlemushroom-793350b5.swedencentral.azurecontainerapps.io/v1",
            api_key="EMPTY",
            model="google/gemma-4-31B-it",
        ),
        name="WeatherAgent",
        instructions="You are a helpful weather assistant.",
        tools=get_weather,
    )

    # Pass the runtime context explicitly when running the agent.
    response = await agent.run(
        # "Tell me about yourself"
        "What is the weather like in Amsterdam?",
        # function_invocation_kwargs={"user_id": "user_123"},
    )

    print(f"Agent: {response.text}")


if __name__ == "__main__":
    asyncio.run(main())
