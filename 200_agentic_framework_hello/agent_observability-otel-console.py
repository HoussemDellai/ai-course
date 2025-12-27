from agent_framework.observability import configure_otel_providers
from dotenv import load_dotenv
import os
import asyncio

# logging src:
# https://learn.microsoft.com/en-us/semantic-kernel/concepts/enterprise-readiness/observability/telemetry-with-console?tabs=Powershell-CreateFile%2CEnvironmentFile&pivots=programming-language-python

import logging

from opentelemetry._logs import set_logger_provider
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import DropAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import set_tracer_provider



# Create a resource to represent the service/sample
resource = Resource.create({ResourceAttributes.SERVICE_NAME: "telemetry-agent-framework"})


def set_up_logging():
    exporter = ConsoleLogExporter()

    # Create and set a global logger provider for the application.
    logger_provider = LoggerProvider(resource=resource)
    # Log processors are initialized with an exporter which is responsible
    # for sending the telemetry data to a particular backend.
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    # Sets the global default logger provider
    set_logger_provider(logger_provider)

    # Create a logging handler to write logging records, in OTLP format, to the exporter.
    handler = LoggingHandler()
    # Add filters to the handler to only process records from semantic_kernel.
    handler.addFilter(logging.Filter())
    # handler.addFilter(logging.Filter("semantic_kernel"))
    # Attach the handler to the root logger. `getLogger()` with no arguments returns the root logger.
    # Events from all child loggers will be processed by this handler.
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def set_up_tracing():
    exporter = ConsoleSpanExporter()

    # Initialize a trace provider for the application. This is a factory for creating tracers.
    tracer_provider = TracerProvider(resource=resource)
    # Span processors are initialized with an exporter which is responsible
    # for sending the telemetry data to a particular backend.
    tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
    # Sets the global default tracer provider
    set_tracer_provider(tracer_provider)


def set_up_metrics():
    exporter = ConsoleMetricExporter()

    # Initialize a metric provider for the application. This is a factory for creating meters.
    meter_provider = MeterProvider(
        metric_readers=[PeriodicExportingMetricReader(exporter, export_interval_millis=5000)],
        resource=resource,
        views=[
            # Dropping all instrument names except for those starting with "semantic_kernel"
            # View(instrument_name="*", aggregation=DropAggregation()),
            View(instrument_name="*"),
            # View(instrument_name="semantic_kernel*"),
        ],
    )
    # Sets the global default meter provider
    set_meter_provider(meter_provider)


# This must be done before any other telemetry calls
set_up_logging()
set_up_tracing()
set_up_metrics()




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