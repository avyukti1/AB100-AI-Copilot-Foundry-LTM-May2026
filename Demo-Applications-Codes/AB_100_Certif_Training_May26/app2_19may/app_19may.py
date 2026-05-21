import streamlit as st
from openai import OpenAI

st.set_page_config(
    page_title="Banking AI Assistant",
    page_icon="🏦",
    layout="wide"
)

client = OpenAI(
    base_url=st.secrets["AZURE_OPENAI_BASE_URL"],
    api_key=st.secrets["AZURE_OPENAI_API_KEY"]
)

DEPLOYMENT_NAME = st.secrets["AZURE_OPENAI_DEPLOYMENT"]

SYSTEM_PROMPT = """
You are an Enterprise Banking AI Assistant.

You help users with:
- Bank account queries
- Loan guidance
- Credit card support
- EMI explanation
- KYC process
- UPI/payment issues
- Fraud awareness
- Internet/mobile banking help

Rules:
- Do not ask for OTP, PIN, CVV, password, card number, or sensitive data.
- Do not provide investment recommendations.
- Do not fabricate account balances or personal banking data.
- For sensitive issues, advise contacting official bank support.
- Keep answers professional, clear, and step-by-step.

Response format:
1. Summary
2. Explanation
3. Recommended Action
4. Escalation Suggestion
"""

st.title("🏦 Banking AI Assistant")
st.caption("Powered by Azure AI Foundry + Azure OpenAI")

with st.sidebar:
    st.header("Demo Questions")

    demo_question = st.selectbox(
        "Select a banking query",
        [
            "How do I check home loan eligibility?",
            "My UPI transaction failed but amount was debited.",
            "How can I block my lost debit card?",
            "Explain fixed deposit in simple words.",
            "What documents are required for KYC update?",
            "How is EMI calculated?",
            "How to report suspicious banking activity?"
        ]
    )

    use_demo = st.button("Use Selected Question")

    st.divider()
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

if use_demo:
    st.session_state.messages.append({
        "role": "user",
        "content": demo_question
    })

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_input = st.chat_input("Ask your banking question...")

if user_input:
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    with st.chat_message("user"):
        st.markdown(user_input)

if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner("Banking AI Assistant is thinking..."):
            try:
                response = client.chat.completions.create(
                    model=DEPLOYMENT_NAME,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        *st.session_state.messages
                    ],
                    temperature=0.3,
                    max_tokens=900
                )

                answer = response.choices[0].message.content
                st.markdown(answer)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer
                })

            except Exception as e:
                st.error("Something went wrong.")
                st.code(str(e))