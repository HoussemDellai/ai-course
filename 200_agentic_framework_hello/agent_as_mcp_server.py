from typing import Annotated
from agent_framework.openai import OpenAIResponsesClient

from dotenv import load_dotenv
import os, logging

log = logging.getLogger()

log.info("Loading environment variables from .env file if it exists")

if os.path.exists(".env"):
    load_dotenv(override=True)


def get_specials() -> Annotated[str, "Returns the specials from the menu."]:
    log.info("Getting specials from the menu")
    return """
        Special Soup: Clam Chowder
        Special Salad: Cobb Salad
        Special Drink: Chai Tea
        """

def get_item_price(
    menu_item: Annotated[str, "The name of the menu item."],
) -> Annotated[str, "Returns the price of the menu item."]:
    return "$9.99"

from agent_framework.azure import AzureOpenAIChatClient

# Create an agent with tools
from agent_framework.azure import AzureOpenAIResponsesClient

agent = AzureOpenAIResponsesClient(
    endpoint="https://ai-services-333-400.openai.azure.com/", # os.environ["AZURE_OPENAI_ENDPOINT"],
    deployment_name="gpt-4o-mini",
    api_key="5bpZ5pkcL449nmrLTVGCmcY4ZbOgr0qGZu6DcbOMDTvI3c7HEdReJQQJ99BLACfhMk5XJ3w3AAAAACOGrfjG", # os.environ["AZURE_OPENAI_API_KEY"],
    api_version="2025-01-01-preview"
    # agent = AzureOpenAIChatClient(
    #     endpoint="https://ai-services-333-400.openai.azure.com/", # os.environ["AZURE_OPENAI_ENDPOINT"],
    #     deployment_name="gpt-4o-mini",
    #     api_key="5bpZ5pkcL449nmrLTVGCmcY4ZbOgr0qGZu6DcbOMDTvI3c7HEdReJQQJ99BLACfhMk5XJ3w3AAAAACOGrfjG" # os.environ["AZURE_OPENAI_API_KEY"],
    # agent = OpenAIResponsesClient(
    # endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    #  model_id="gpt-4o-mini",
    #  api_key=os.environ["AZURE_OPENAI_API_KEY"]
).create_agent(
    name="RestaurantAgent",
    description="Answer questions about the menu.",
    tools=[get_specials, get_item_price],
)

# Expose the agent as an MCP server
server = agent.as_mcp_server()
log.info("Starting MCP stdio server (Ctrl+C to stop)")

import anyio
from mcp.server.stdio import stdio_server

async def run():
    async def handle_stdin():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )

    await handle_stdin()


if __name__ == "__main__":
    anyio.run(run)
