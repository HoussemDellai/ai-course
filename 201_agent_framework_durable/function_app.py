import os
from agent_framework.azure import AzureOpenAIChatClient, AgentFunctionApp
from azure.identity import DefaultAzureCredential

endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
if not endpoint:
    raise ValueError("AZURE_OPENAI_ENDPOINT is not set.")
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")

# Create an AI agent following the standard Microsoft Agent Framework pattern
agent = AzureOpenAIChatClient(
    endpoint=endpoint,
    deployment_name=deployment_name,
    credential=DefaultAzureCredential()
).create_agent(
    instructions="You are a helpful assistant that can answer questions and provide information.",
    name="MyDurableAgent"
)

# Configure the function app to host the agent with durable thread management
app = AgentFunctionApp(agents=[agent])