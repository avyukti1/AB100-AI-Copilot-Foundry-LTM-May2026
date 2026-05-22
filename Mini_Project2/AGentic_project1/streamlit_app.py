import os
import sys

import streamlit as st


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from foundry_agent_sample import ask_azure_openai, load_env_file


load_env_file(os.path.join(PROJECT_ROOT, ".env"))

st.set_page_config(
    page_title="Azure AI Foundry Agent Chat",
    page_icon="",
    layout="centered",
)

st.title("Azure AI Foundry Agent Chat")
st.caption("Powered by your Azure OpenAI deployment from the project .env file.")

with st.sidebar:
    st.subheader("Configuration")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")
    has_key = bool(os.getenv("AZURE_OPENAI_API_KEY"))

    st.text_input("Endpoint", value=endpoint, disabled=True)
    st.text_input("Deployment", value=deployment, disabled=True)
    st.checkbox("API key loaded", value=has_key, disabled=True)

    if st.button("Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hi bro, ask me something and I will call your Azure OpenAI deployment.",
        }
    ]


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


prompt = st.chat_input("Ask your Foundry/Azure OpenAI agent...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Calling Azure OpenAI..."):
            try:
                answer = ask_azure_openai(prompt)
            except Exception as exc:
                answer = f"Error: {exc}"
            st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
