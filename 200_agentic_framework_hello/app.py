import asyncio
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import AzureCliCredential

agent = AzureOpenAIChatClient(
    api_key='',
    endpoint='',
    deployment_name='',
    api_version='',
)

# agent = AzureOpenAIChatClient(credential=AzureCliCredential()).create_agent(
#     instructions="You are good at telling jokes.",
#     name="Joker"
# )