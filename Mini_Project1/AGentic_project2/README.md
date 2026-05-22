# AI Agent Management Web App

Streamlit web app with three operational modules:

- Hospital Patient Management
- College Student Management
- Employee Cabs Management

Each module includes a shared Azure AI Foundry agent chat panel configured with:

- Endpoint: `https://abhiaifoundry1231.services.ai.azure.com/api/projects/proj-default`
- Agent: `abhi-demoagent222`
- Version: `1`

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
az login
streamlit run app.py
```

The app uses `DefaultAzureCredential`, so sign in with `az login` or configure another supported Azure credential before starting Streamlit. On a clean machine, the most common fix is to install Azure CLI, run:

```powershell
az login
```

Then restart Streamlit.

If your installed Azure AI Foundry SDK exposes a different agent invocation method, the app still runs and shows a clear agent error in the chat panel instead of breaking the full UI.
