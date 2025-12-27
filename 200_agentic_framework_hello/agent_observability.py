from agent_framework.observability import configure_otel_providers
from dotenv import load_dotenv
import os
import asyncio

if os.path.exists(".env"):
    load_dotenv(override=True)

os.environ["ENABLE_INSTRUMENTATION"] = "true"
os.environ["ENABLE_CONSOLE_EXPORTERS"] = "true"
# os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4317"

# Enable console output for local development
# Enable console output for debugging
# Set ENABLE_CONSOLE_EXPORTERS=true
# Set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
configure_otel_providers(
        enable_sensitive_data=True, # development only
        vs_code_extension_port=4317,  # Connects to AI Toolkit
    )
# configure_otel_providers(enable_console_exporters=True)

from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient

# Create the agent - telemetry is automatically enabled
agent = ChatAgent(
    chat_client=AzureOpenAIChatClient(
        deployment_name="gpt-4o-mini",
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        endpoint=os.environ["AZURE_OPENAI_ENDPOINT"]
    ),
    name="Joker",
    instructions="You are good at telling jokes."
)

# Run the agent
async def main():
    result = await agent.run("Tell me a joke about a pirate.")
    print(result.text)

if __name__ == "__main__":
    asyncio.run(main())