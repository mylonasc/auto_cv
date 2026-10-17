"""Instrument the normal CLI pipeline; accepts the same arguments as autocv.py."""

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from autocv import main as cli_main


def initialize_tracing():
    # Optional packages and exporter setup are confined to explicit execution.
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.langchain import LangchainInstrumentor
    from opentelemetry.instrumentation.ollama import OllamaInstrumentor

    provider = TracerProvider(resource=Resource.create({"service.name": "auto-cv"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"), insecure=True)))
    trace.set_tracer_provider(provider)
    LangchainInstrumentor().instrument()
    OllamaInstrumentor().instrument()
    return provider


def main():
    provider = initialize_tracing()
    try:
        cli_main()
    finally:
        provider.force_flush()
        provider.shutdown()


if __name__ == "__main__":
    main()
