import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="AI Helpdesk Agent", page_icon="🤖", layout="wide")

client = OpenAI(
    base_url=st.secrets["AZURE_OPENAI_BASE_URL"],
    api_key=st.secrets["AZURE_OPENAI_API_KEY"]
)

DEPLOYMENT_NAME = st.secrets["AZURE_OPENAI_DEPLOYMENT"]

st.title("AI Helpdesk Agent")
st.caption("Powered by Azure AI Foundry + Azure OpenAI")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "system",
            "content": """
You are an enterprise IT Helpdesk AI Agent.
Help users with laptop issues, password reset, VPN, Outlook, Teams, Azure access,
software installation, and ticket classification.

For every answer provide:
1. Problem Summary
2. Possible Cause
3. Step-by-step Resolution
4. Priority: Low / Medium / High
5. Suggested Ticket Category
"""
        }
    ]

with st.sidebar:
    st.header("Sample Questions")
    sample = st.selectbox(
        "Choose a helpdesk issue",
        [
            "My VPN is not connecting.",
            "I forgot my Windows password.",
            "Outlook is not receiving emails.",
            "Microsoft Teams camera is not working.",
            "I need access to Azure AI Foundry.",
            "My laptop is running very slow."
        ]
    )

    if st.button("Use Sample"):
        st.session_state.user_input = sample

    if st.button("Clear Chat"):
        st.session_state.messages = st.session_state.messages[:1]
        st.rerun()

for msg in st.session_state.messages[1:]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Describe your IT issue...")

if "user_input" in st.session_state:
    user_input = st.session_state.user_input
    del st.session_state.user_input

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("AI Helpdesk Agent is analyzing..."):
            response = client.chat.completions.create(
                model=DEPLOYMENT_NAME,
                messages=st.session_state.messages,
                temperature=0.3,
                max_tokens=800
            )

            answer = response.choices[0].message.content
            st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})