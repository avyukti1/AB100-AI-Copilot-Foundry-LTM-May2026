import argparse
import json
import os
import sys
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4


DEFAULT_QUESTION = "I need to solve the equation 3x + 11 = 14. Can you help me?"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass(frozen=True)
class DemoMessage:
    role: str
    content: str


def load_env_file(path: str) -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def solve_linear_demo(question: str) -> str:
    return textwrap.dedent(
        f"""
        I received: {question}

        Demo solution:
        3x + 11 = 14
        3x = 14 - 11
        3x = 3
        x = 1

        In Azure mode, this same flow creates a real Foundry agent, thread,
        message, and run using your PROJECT_ENDPOINT and MODEL_DEPLOYMENT_NAME.
        """
    ).strip()


def run_demo(question: str) -> int:
    agent_id = f"demo-agent-{uuid4().hex[:8]}"
    thread_id = f"demo-thread-{uuid4().hex[:8]}"
    message_id = f"demo-message-{uuid4().hex[:8]}"
    run_id = f"demo-run-{uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    conversation = [
        DemoMessage("user", question),
        DemoMessage("assistant", solve_linear_demo(question)),
    ]

    print("Azure AI Foundry Agent Sample - local demo mode")
    print(f"Created agent:  {agent_id}")
    print(f"Created thread: {thread_id}")
    print(f"Created message: {message_id}")
    print(f"Created run: {run_id}")
    print(f"Run status: completed at {created_at}")
    print()
    print("Conversation")
    print("------------")

    for item in conversation:
        print(f"[{item.role}] {item.content}")
        print()

    return 0


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def run_azure(question: str) -> int:
    try:
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise RuntimeError(
            "Azure SDK packages are not installed. Run: python -m pip install -r requirements.txt"
        ) from exc

    endpoint = require_env("PROJECT_ENDPOINT")
    model_deployment_name = require_env("MODEL_DEPLOYMENT_NAME")

    project_client = AIProjectClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(),
    )

    with project_client:
        agent = project_client.agents.create_agent(
            model=model_deployment_name,
            name="training-foundry-agent",
            instructions=(
                "You are a concise training assistant. Explain each answer clearly "
                "and use plain text formatting that reads well in a terminal."
            ),
        )
        print(f"Created agent, ID: {agent.id}")

        thread = project_client.agents.threads.create()
        print(f"Created thread, ID: {thread.id}")

        message = project_client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=question,
        )
        print(f"Created message, ID: {message['id']}")

        run = project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=agent.id,
        )
        print(f"Run finished with status: {run.status}")

        if run.status == "failed":
            print(f"Run failed: {run.last_error}")
            return 1

        print()
        print("Conversation")
        print("------------")
        for thread_message in project_client.agents.messages.list(thread_id=thread.id):
            print_message(thread_message)

        project_client.agents.delete_agent(agent.id)
        print(f"Deleted agent, ID: {agent.id}")

    return 0


def run_azure_openai(question: str) -> int:
    endpoint = require_env("AZURE_OPENAI_ENDPOINT").rstrip("/")
    deployment_name = require_env("AZURE_OPENAI_DEPLOYMENT_NAME")

    print("Azure AI Foundry Agent Sample - Azure OpenAI mode")
    print(f"Endpoint: {endpoint}")
    print(f"Deployment: {deployment_name}")
    print("API key: loaded from AZURE_OPENAI_API_KEY")
    print()

    answer = ask_azure_openai(question)

    print("Conversation")
    print("------------")
    print(f"[user] {question}")
    print()
    print(f"[assistant] {answer}")
    print()

    return 0


def ask_azure_openai(question: str) -> str:
    endpoint = require_env("AZURE_OPENAI_ENDPOINT").rstrip("/")
    deployment_name = require_env("AZURE_OPENAI_DEPLOYMENT_NAME")
    api_key = require_env("AZURE_OPENAI_API_KEY")

    request_body = {
        "model": deployment_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a concise Azure AI training assistant. Show clear steps "
                    "and keep the answer terminal-friendly."
                ),
            },
            {"role": "user", "content": question},
        ],
        "temperature": 0.2,
    }

    data = json.dumps(request_body).encode("utf-8")
    request = urllib.request.Request(
        f"{endpoint}/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json",
            "api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Azure OpenAI request failed with HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Azure OpenAI request failed: {exc.reason}") from exc

    return payload["choices"][0]["message"]["content"]


def print_message(message: object) -> None:
    role = getattr(message, "role", "unknown")
    content_items = getattr(message, "content", [])

    for item in content_items:
        text = getattr(getattr(item, "text", None), "value", None)
        if text is None:
            text = str(item)
        print(f"[{role}] {text}")
        print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Azure AI Foundry Agent sample")
    parser.add_argument(
        "--mode",
        choices=("demo", "azure", "azure-openai"),
        default="demo",
        help=(
            "Use demo for local simulation, azure for the real Foundry Agent Service, "
            "or azure-openai for a direct Azure OpenAI deployment call."
        ),
    )
    parser.add_argument(
        "--question",
        default=DEFAULT_QUESTION,
        help="User message to send to the sample agent.",
    )
    return parser


def main() -> int:
    load_env_file(os.path.join(PROJECT_ROOT, ".env"))
    args = build_parser().parse_args()

    try:
        if args.mode == "azure":
            return run_azure(args.question)
        if args.mode == "azure-openai":
            return run_azure_openai(args.question)
        return run_demo(args.question)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
