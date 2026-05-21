import os
import time
import requests
import streamlit as st
from dotenv import load_dotenv
import msal

load_dotenv()

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
COPILOT_URL = os.getenv("COPILOT_URL")

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = ["https://api.powerplatform.com/.default"]


def get_access_token():
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET
    )

    result = app.acquire_token_for_client(scopes=SCOPE)

    if "access_token" not in result:
        st.error(result)
        raise Exception("Could not get access token")

    return result["access_token"]


def start_conversation(token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.post(COPILOT_URL, headers=headers, json={})
    response.raise_for_status()
    return response.json()


def send_message(token, conversation_id, message):
    url = COPILOT_URL.replace(
        "/conversations?api-version=2022-03-01-preview",
        f"/conversations/{conversation_id}/activities?api-version=2022-03-01-preview"
    )

    payload = {
        "type": "message",
        "from": {"id": "streamlit-user"},
        "text": message
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


st.set_page_config(page_title="Enterprise HR Assistant", page_icon="🤖")

st.title("Enterprise HR Assistant")
st.caption("Powered by Copilot Studio + Streamlit")

if "token" not in st.session_state:
    st.session_state.token = get_access_token()

if "conversation" not in st.session_state:
    st.session_state.conversation = start_conversation(st.session_state.token)

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_input = st.chat_input("Ask HR assistant...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.write(user_input)

    conversation_id = st.session_state.conversation.get("conversationId") or st.session_state.conversation.get("id")

    with st.chat_message("assistant"):
        with st.spinner("HR Assistant is thinking..."):
            try:
                result = send_message(
                    st.session_state.token,
                    conversation_id,
                    user_input
                )

                bot_reply = str(result)

                st.write(bot_reply)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": bot_reply
                })

            except Exception as e:
                st.error(f"Error: {e}")