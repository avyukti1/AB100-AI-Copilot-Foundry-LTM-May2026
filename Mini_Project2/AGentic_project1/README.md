# Azure AI Foundry Agent Sample

A small Python sample that demonstrates the Azure AI Foundry Agent lifecycle:

1. create an agent
2. create a conversation thread
3. send a user message
4. run the agent
5. print the conversation result

The project has two modes:

- `demo`: runs locally without Azure credentials or network access.
- `azure`: uses Azure AI Foundry Agent Service with `azure-ai-projects` and `azure-identity`.
- `azure-openai`: uses an Azure OpenAI deployment directly with an API key.

## Run Locally

```powershell
python .\src\foundry_agent_sample.py --mode demo
```

## Run Against Azure AI Foundry

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Sign in:

```powershell
az login
```

Set your Foundry project endpoint and model deployment name:

```powershell
$env:PROJECT_ENDPOINT="https://<your-foundry-resource>.services.ai.azure.com/api/projects/<your-project>"
$env:MODEL_DEPLOYMENT_NAME="<your-model-deployment-name>"
python .\src\foundry_agent_sample.py --mode azure
```

You can copy the expected environment variable names from `.env.example`.

## Run Against Azure OpenAI

Use this mode when you have an Azure OpenAI endpoint such as:

```text
https://<resource-name>.openai.azure.com/openai/v1
```

Set your endpoint, deployment name, and API key:

```powershell
$env:AZURE_OPENAI_ENDPOINT="https://<resource-name>.openai.azure.com/openai/v1"
$env:AZURE_OPENAI_DEPLOYMENT_NAME="<deployment-name>"
$env:AZURE_OPENAI_API_KEY="<api-key>"
python .\src\foundry_agent_sample.py --mode azure-openai
```

This mode demonstrates an agent-like assistant loop using your Azure OpenAI model deployment. It does not create a persistent Foundry Agent Service agent.

## Run Streamlit App

```powershell
streamlit run .\streamlit_app.py
```

Then open the local URL shown in the terminal. The app reads Azure OpenAI settings from `.env`.

## Files

- `src/foundry_agent_sample.py` - runnable sample app
- `requirements.txt` - Azure SDK packages for cloud mode
- `.env.example` - required environment variable template
