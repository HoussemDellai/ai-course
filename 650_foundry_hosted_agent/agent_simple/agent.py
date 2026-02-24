import os
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv(override=True)

from agent_framework import tool #, FunctionTool, ChatAgent
from agent_framework.azure import AzureOpenAIResponsesClient
# from agent_framework.azure import AzureAIAgentClient
from azure.ai.agentserver.agentframework import from_agent_framework
from azure.identity import DefaultAzureCredential

# Configure these for your Azure AI Foundry project
PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT")  # e.g., "https://<resource>.services.ai.azure.com/api/projects/<project>"
MODEL_DEPLOYMENT_NAME = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-5.2")  # Your model deployment name


@tool # (approval_mode="never_require")
def get_local_date_time(iana_timezone: str) -> str:
    """
    Get the current date and time for a given timezone.
    
    This is a LOCAL Python function that runs on the server - demonstrating how code-based agents
    can execute custom logic that prompt agents cannot access.
    
    Args:
        iana_timezone: The IANA timezone string (e.g., "America/Los_Angeles", "America/New_York", "Europe/London")
    
    Returns:
        The current date and time in the specified timezone.
    """
    try:
        tz = ZoneInfo(iana_timezone)
        current_time = datetime.now(tz)
        return f"The current date and time in {iana_timezone} is {current_time.strftime('%A, %B %d, %Y at %I:%M %p %Z')}"
    except Exception as e:
        return f"Error: Unable to get time for timezone '{iana_timezone}'. {str(e)}"


# Create the agent with a local Python tool

client = AzureOpenAIResponsesClient(
    project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
    deployment_name=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
    credential=DefaultAzureCredential(),
)

# <create_agent_with_tools>
agent = client.as_agent(
    name="WeatherAgent",
    instructions="You are a helpful assistant that can tell users the current date and time in any location. When a user asks about the time in a city or location, use the get_local_date_time tool with the appropriate IANA timezone string for that location.",
    tools=[get_local_date_time],
)
# </create_agent_with_tools>

# agent = ChatAgent(
#     chat_client=AzureAIAgentClient(
#         project_endpoint=PROJECT_ENDPOINT,
#         model_deployment_name=MODEL_DEPLOYMENT_NAME,
#         credential=DefaultAzureCredential(),
#     ),
#     instructions="You are a helpful assistant that can tell users the current date and time in any location. When a user asks about the time in a city or location, use the get_local_date_time tool with the appropriate IANA timezone string for that location.",
#     tools=[get_local_date_time],
# )

if __name__ == "__main__":
    from_agent_framework(agent).run()