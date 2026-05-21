import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DIRECT_LINE_SECRET = os.getenv("DIRECT_LINE_SECRET")

DIRECT_LINE_BASE_URL = "https://directline.botframework.com/v3/directline"


def start_conversation():
    headers = {
        "Authorization": f"Bearer {DIRECT_LINE_SECRET}"
    }

    response = requests.post(
        f"{DIRECT_LINE_BASE_URL}/conversations",
        headers=headers
    )

    response.raise_for_status()
    return response.json()


def send_message(conversation_id, message):
    headers = {
        "Authorization": f"Bearer {DIRECT_LINE_SECRET}",
        "Content-Type": "application/json"
    }

    payload = {
        "type": "message",
        "from": {
            "id": "streamlit-user",
            "name": "Streamlit User"
        },
        "text": message
    }

    response = requests.post(
        f"{DIRECT_LINE_BASE_URL}/conversations/{conversation_id}/activities",
        headers=headers,
        json=payload
    )

    response.raise_for_status()


def get_bot_response(conversation_id, watermark=None):
    headers = {
        "Authorization": f"Bearer {DIRECT_LINE_SECRET}"
    }

    url = f"{DIRECT_LINE_BASE_URL}/conversations/{conversation_id}/activities"

    if watermark:
        url += f"?watermark={watermark}"

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()


st.set_page_config(
    page_title="Enterprise HR Assistant",
    page_icon="🤖"
)

st.title("Enterprise HR Assistant")
st.caption("Copilot Studio Agent integrated with Streamlit")

if "conversation_id" not in st.session_state:
    conversation = start_conversation()
    st.session_state.conversation_id = conversation["conversationId"]
    st.session_state.watermark = None
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_input = st.chat_input("Ask HR related questions...")

if user_input:
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    with st.chat_message("user"):
        st.write(user_input)

    send_message(st.session_state.conversation_id, user_input)

    with st.chat_message("assistant"):
        with st.spinner("HR Assistant is replying..."):
            activities = get_bot_response(
                st.session_state.conversation_id,
                st.session_state.watermark
            )

            st.session_state.watermark = activities.get("watermark")

            bot_replies = []

            for activity in activities.get("activities", []):
                if activity.get("from", {}).get("id") != "streamlit-user":
                    if activity.get("type") == "message":
                        text = activity.get("text")
                        if text:
                            bot_replies.append(text)

            if bot_replies:
                reply = "\n\n".join(bot_replies)
            else:
                reply = "No response received from HR Assistant."

            st.write(reply)

            st.session_state.messages.append({
                "role": "assistant",
                "content": reply
            })