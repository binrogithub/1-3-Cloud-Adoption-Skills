#!/usr/bin/env python3
import argparse
from pathlib import Path
import textwrap


REQUIREMENTS = """\
traceloop-sdk==0.36.1
openai==2.33.0
python-dotenv==1.2.1
"""


ENV_EXAMPLE = """\
HUAWEI_MAAS_API_BASE=https://api-ap-southeast-1.modelarts-maas.com/openai/v1
HUAWEI_MAAS_API_KEY=replace-with-your-maas-api-key
HUAWEI_MAAS_MODEL=glm-5.1

OPENLLMETRY_EXPORTER=console
TRACELOOP_APP_NAME=huawei-maas-agent-demo
TRACELOOP_TRACE_CONTENT=false
TRACELOOP_TELEMETRY=false

# Optional when OPENLLMETRY_EXPORTER=otlp
# TRACELOOP_BASE_URL=http://localhost:4318
# TRACELOOP_API_KEY=
"""


AGENT = r'''#!/usr/bin/env python3
import argparse
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from traceloop.sdk import Traceloop
from traceloop.sdk.decorators import task, workflow
from traceloop.sdk.instruments import Instruments


def init_openllmetry() -> None:
    os.environ.setdefault("TRACELOOP_TRACE_CONTENT", "false")
    app_name = os.getenv("TRACELOOP_APP_NAME", "huawei-maas-agent-demo")
    exporter_mode = os.getenv("OPENLLMETRY_EXPORTER", "console").lower()
    common = {
        "app_name": app_name,
        "disable_batch": True,
        "telemetry_enabled": os.getenv("TRACELOOP_TELEMETRY", "false").lower() == "true",
        "instruments": {Instruments.OPENAI},
        "resource_attributes": {
            "service.name": app_name,
            "agent.name": os.getenv("AGENT_NAME", "maas-demo-agent"),
            "llm.provider": "huawei-cloud-maas",
        },
    }
    if exporter_mode == "console":
        Traceloop.init(exporter=ConsoleSpanExporter(), **common)
        return
    if exporter_mode == "otlp":
        Traceloop.init(
            api_endpoint=os.environ["TRACELOOP_BASE_URL"],
            api_key=os.getenv("TRACELOOP_API_KEY"),
            **common,
        )
        return
    raise ValueError("OPENLLMETRY_EXPORTER must be 'console' or 'otlp'")


def maas_client() -> tuple[OpenAI, str]:
    api_key = os.getenv("HUAWEI_MAAS_API_KEY")
    if not api_key or api_key == "replace-with-your-maas-api-key":
        raise RuntimeError("HUAWEI_MAAS_API_KEY is not set")
    base_url = os.getenv("HUAWEI_MAAS_API_BASE")
    if not base_url:
        raise RuntimeError("HUAWEI_MAAS_API_BASE is not set")
    model = os.getenv("HUAWEI_MAAS_MODEL", "glm-5.1")
    return OpenAI(api_key=api_key, base_url=base_url), model


@task(name="call_huawei_maas")
def call_huawei_maas(prompt: str) -> str:
    client, model = maas_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a concise integration-test agent."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_completion_tokens=128,
    )
    message = response.choices[0].message
    return message.content or getattr(message, "reasoning_content", "") or ""


@workflow(name="huawei_maas_agent_workflow")
def run_agent(prompt: str) -> str:
    return call_huawei_maas(prompt)


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default="Say exactly: Huawei MaaS Agent OK")
    args = parser.parse_args()
    init_openllmetry()
    try:
        print(run_agent(args.prompt))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


README = """\
# Huawei MaaS Agent Demo With OpenLLMetry

This demo calls Huawei Cloud MaaS through an OpenAI-compatible client and uses OpenLLMetry to emit OpenTelemetry traces.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
vi .env
```

## Run

```bash
.venv/bin/python agent.py --prompt "Say exactly: Huawei MaaS Agent OK"
```

With `OPENLLMETRY_EXPORTER=console`, spans print to the terminal. For a web UI, export to Traceloop Cloud or an OTLP backend such as Jaeger, Grafana Tempo, Datadog, or Honeycomb.

Security default: `TRACELOOP_TRACE_CONTENT=false`.
"""


def write_file(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists; pass --force to overwrite")
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a safe OpenLLMetry + Huawei MaaS Agent demo.")
    parser.add_argument("output_dir")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    out = Path(args.output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    write_file(out / "requirements.txt", REQUIREMENTS, args.force)
    write_file(out / ".env.example", ENV_EXAMPLE, args.force)
    write_file(out / "agent.py", AGENT, args.force)
    write_file(out / "README.md", README, args.force)
    (out / "agent.py").chmod(0o755)
    print(f"Created demo at {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
