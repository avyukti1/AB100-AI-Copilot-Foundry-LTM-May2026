from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import streamlit as st
from azure.identity import DefaultAzureCredential

try:
    from azure.ai.projects import AIProjectClient
except ImportError:  # pragma: no cover - visible in Streamlit UI
    AIProjectClient = None


ENDPOINT = "https://abhiaifoundry1231.services.ai.azure.com/api/projects/proj-default"
AGENT_NAME = "abhi-demoagent222"
AGENT_VERSION = "1"
LTM_LOGO_URL = "https://www.ltm.com/content/dam/ltimcorporatewebsite/refresh-images/LTM-Logo.svg"
APP_ROLES = {
    "Hospital Patient Management": ("Patient", "Doctor"),
    "College Student Management": ("Student", "Lecturer"),
    "Employee Cabs Management": ("Employee", "Cab Admin"),
}


@dataclass(frozen=True)
class AgentConfig:
    endpoint: str = ENDPOINT
    agent_name: str = AGENT_NAME
    agent_version: str = AGENT_VERSION


class FoundryAgent:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.project_client: Any | None = None
        self.openai_client: Any | None = None
        self.agent: Any | None = None
        self.last_errors: list[str] = []

    def connect(self) -> None:
        if AIProjectClient is None:
            raise RuntimeError("Missing package: install azure-ai-projects from requirements.txt.")

        self.project_client = AIProjectClient(
            endpoint=self.config.endpoint,
            credential=DefaultAzureCredential(),
            allow_preview=True,
        )
        self.openai_client = self.project_client.get_openai_client()
        self.agent = self._resolve_agent()

    def ask(self, prompt: str, context: str) -> str:
        self.last_errors = []
        if self.project_client is None:
            self.connect()

        enriched_prompt = (
            "You are embedded in an operations management web app. "
            "Use the module data and answer with concise, practical guidance.\n\n"
            f"Module context:\n{context}\n\nUser question:\n{prompt}"
        )

        shared_response = self._ask_with_shared_project_endpoint(enriched_prompt)
        if shared_response:
            return shared_response

        agent_response = self._ask_with_agent_endpoint(enriched_prompt)
        if agent_response:
            return agent_response

        return self._ask_with_openai_client(enriched_prompt)

    def _resolve_agent(self) -> Any | None:
        agents = getattr(self.project_client, "agents", None)
        if agents is None:
            return None

        for method_name in ("get_version", "get"):
            method = getattr(agents, method_name, None)
            if method is None:
                continue
            for kwargs in (
                {"agent_name": self.config.agent_name, "agent_version": self.config.agent_version},
                {"agent_name": self.config.agent_name},
            ):
                try:
                    return method(**kwargs)
                except TypeError:
                    continue
                except Exception:
                    continue
        return None

    def _ask_with_agent_endpoint(self, prompt: str) -> str | None:
        try:
            agent_client = self.project_client.get_openai_client(agent_name=self.config.agent_name)
            session = self._create_versioned_session()
            kwargs: dict[str, Any] = {"input": prompt}
            if session is not None and getattr(session, "agent_session_id", None):
                kwargs["extra_body"] = {"agent_session_id": session.agent_session_id}

            response = agent_client.responses.create(**kwargs)
            return getattr(response, "output_text", None) or self._extract_response_text(response)
        except Exception as exc:
            self._record_error("Dedicated agent endpoint", exc)
            return None

    def _create_versioned_session(self) -> Any | None:
        beta_agents = getattr(getattr(self.project_client, "beta", None), "agents", None)
        if beta_agents is None:
            return None

        try:
            return beta_agents.create_session(
                agent_name=self.config.agent_name,
                body={
                    "version_indicator": {
                        "type": "version_ref",
                        "agent_version": self.config.agent_version,
                    }
                },
                isolation_key="streamlit-user",
            )
        except Exception as exc:
            self._record_error("Versioned agent session", exc)
            return None

    def _ask_with_shared_project_endpoint(self, prompt: str) -> str | None:
        try:
            response = self.openai_client.responses.create(
                input=prompt,
                extra_body={
                    "agent_reference": {
                        "name": self.config.agent_name,
                        "type": "agent_reference",
                    }
                },
            )
            return getattr(response, "output_text", None) or self._extract_response_text(response)
        except Exception as exc:
            self._record_error("Shared project endpoint", exc)
            return None

    def _ask_with_openai_client(self, prompt: str) -> str:
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME") or os.getenv("AZURE_OPENAI_DEPLOYMENT")
        if not deployment:
            return self._format_failure_message()

        response = self.openai_client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": "You are a helpful management operations AI agent."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or "No response returned."

    def _agent_id(self) -> str:
        if self.agent is None:
            return self.config.agent_name
        return (
            getattr(self.agent, "id", None)
            or getattr(self.agent, "agent_id", None)
            or self.config.agent_name
        )

    @staticmethod
    def _extract_response_text(response: Any) -> str | None:
        output = getattr(response, "output", None) or []
        chunks: list[str] = []
        for item in output:
            content = getattr(item, "content", None) or []
            for content_item in content:
                text = getattr(content_item, "text", None)
                if text:
                    chunks.append(text)
        return "\n".join(chunks) if chunks else None

    def _record_error(self, step: str, exc: Exception) -> None:
        message = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
        self.last_errors.append(f"{step}: {exc.__class__.__name__}: {message}")

    def _format_failure_message(self) -> str:
        auth_error = any("DefaultAzureCredential failed to retrieve a token" in error for error in self.last_errors)
        if auth_error:
            return (
                "Azure authentication is not configured on this machine. `DefaultAzureCredential` could not find "
                "Azure CLI login, VS Code Azure login, service principal environment variables, or managed identity.\n\n"
                "Fast fix: install Azure CLI, run `az login`, then restart Streamlit. Alternative: set "
                "`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, and `AZURE_CLIENT_SECRET` for a service principal.\n\n"
                "Agent call details:\n- " + "\n- ".join(self.last_errors)
            )

        details = "\n- ".join(self.last_errors) if self.last_errors else "No detailed exception was returned."
        return (
            "Connected to the project client, but the configured Azure AI Foundry agent call did not complete.\n\n"
            "Agent call details:\n- " + details
        )

    @staticmethod
    def _extract_latest_text(messages: Any) -> str:
        data = getattr(messages, "data", messages)
        for message in data:
            if getattr(message, "role", None) != "assistant":
                continue
            content_items = getattr(message, "content", [])
            extracted: list[str] = []
            for item in content_items:
                text = getattr(getattr(item, "text", None), "value", None)
                if text:
                    extracted.append(text)
                elif isinstance(item, dict):
                    value = item.get("text", {}).get("value") if isinstance(item.get("text"), dict) else None
                    if value:
                        extracted.append(value)
            if extracted:
                return "\n".join(extracted)
        return "The agent completed, but no assistant text was returned."


def seed_state() -> None:
    if "patients" not in st.session_state:
        st.session_state.patients = [
            {"Patient ID": "P-1001", "Name": "Aarav Mehta", "Age": 42, "Department": "Cardiology", "Doctor": "Dr. Rao", "Status": "Admitted"},
            {"Patient ID": "P-1002", "Name": "Neha Sharma", "Age": 31, "Department": "Orthopedics", "Doctor": "Dr. Iyer", "Status": "Observation"},
            {"Patient ID": "P-1003", "Name": "Kabir Singh", "Age": 58, "Department": "Neurology", "Doctor": "Dr. Khan", "Status": "Discharge Ready"},
        ]

    if "students" not in st.session_state:
        st.session_state.students = [
            {"Student ID": "S-2201", "Name": "Riya Nair", "Course": "B.Tech CSE", "Year": "3rd", "Attendance %": 91, "Status": "Active"},
            {"Student ID": "S-2202", "Name": "Manav Patel", "Course": "MBA", "Year": "1st", "Attendance %": 76, "Status": "Needs Review"},
            {"Student ID": "S-2203", "Name": "Sara Khan", "Course": "BCA", "Year": "2nd", "Attendance %": 88, "Status": "Active"},
        ]

    if "cab_requests" not in st.session_state:
        st.session_state.cab_requests = [
            {"Request ID": "C-501", "Employee": "Anika Das", "Pickup": "Indiranagar", "Drop": "Campus A", "Time": "08:30", "Status": "Scheduled"},
            {"Request ID": "C-502", "Employee": "Vikram Joshi", "Pickup": "Whitefield", "Drop": "Campus B", "Time": "09:00", "Status": "Driver Assigned"},
            {"Request ID": "C-503", "Employee": "Priya Menon", "Pickup": "HSR Layout", "Drop": "Airport", "Time": "18:15", "Status": "Pending"},
        ]

    if "agent_messages" not in st.session_state:
        st.session_state.agent_messages = {}

    if "users" not in st.session_state:
        st.session_state.users = {
            "Hospital Patient Management": [
                {
                    "Name": "Demo Patient",
                    "Email": "patient@ltm.com",
                    "Role": "Patient",
                    "Password Hash": hash_password("patient123"),
                },
                {
                    "Name": "Demo Doctor",
                    "Email": "doctor@ltm.com",
                    "Role": "Doctor",
                    "Password Hash": hash_password("doctor123"),
                },
            ],
            "College Student Management": [
                {
                    "Name": "Demo Student",
                    "Email": "student@ltm.com",
                    "Role": "Student",
                    "Password Hash": hash_password("student123"),
                },
                {
                    "Name": "Demo Lecturer",
                    "Email": "lecturer@ltm.com",
                    "Role": "Lecturer",
                    "Password Hash": hash_password("lecturer123"),
                },
            ],
            "Employee Cabs Management": [
                {
                    "Name": "Demo Employee",
                    "Email": "employee@ltm.com",
                    "Role": "Employee",
                    "Password Hash": hash_password("employee123"),
                },
                {
                    "Name": "Demo Cab Admin",
                    "Email": "cabadmin@ltm.com",
                    "Role": "Cab Admin",
                    "Password Hash": hash_password("cabadmin123"),
                },
            ],
        }

    if "signed_in_users" not in st.session_state:
        st.session_state.signed_in_users = {}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def current_user(app_name: str) -> dict[str, str] | None:
    return st.session_state.signed_in_users.get(app_name)


def find_user(app_name: str, email: str, role: str) -> dict[str, str] | None:
    normalized_email = email.strip().lower()
    for user in st.session_state.users.get(app_name, []):
        if user["Email"].lower() == normalized_email and user["Role"] == role:
            return user
    return None


def dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(records)


def render_header() -> None:
    st.set_page_config(page_title="AI Agent Management Hub", page_icon="AI", layout="wide")
    st.markdown(
        """
        <style>
            :root {
                --ltm-navy: #0f2742;
                --ltm-blue: #2563eb;
                --ltm-teal: #0f766e;
                --ltm-mint: #d9f99d;
                --ltm-ink: #0f172a;
                --ltm-muted: #64748b;
                --ltm-card: rgba(255, 255, 255, 0.92);
                --ltm-border: rgba(15, 39, 66, 0.12);
            }

            .stApp {
                background:
                    linear-gradient(135deg, rgba(15, 39, 66, 0.95) 0%, rgba(37, 99, 235, 0.76) 36%, rgba(15, 118, 110, 0.72) 100%),
                    radial-gradient(circle at 18% 22%, rgba(217, 249, 157, 0.36), transparent 30%),
                    linear-gradient(180deg, #f8fafc 0%, #e0f2fe 100%);
                color: var(--ltm-ink);
            }

            .stApp::before {
                content: "LTM Organization";
                position: fixed;
                right: -28px;
                bottom: 22px;
                z-index: 0;
                font-size: clamp(42px, 8vw, 118px);
                font-weight: 800;
                color: rgba(255, 255, 255, 0.13);
                letter-spacing: 0;
                pointer-events: none;
                transform: rotate(-7deg);
                white-space: nowrap;
            }

            .block-container {
                position: relative;
                z-index: 1;
                padding-top: 2rem;
            }

            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, rgba(15, 39, 66, 0.98), rgba(17, 94, 89, 0.96));
                border-right: 1px solid rgba(255, 255, 255, 0.16);
            }

            [data-testid="stSidebar"] * {
                color: #f8fafc;
            }

            [data-testid="stSidebar"] code {
                color: #111827 !important;
                background: #ffffff !important;
                border: 1px solid rgba(15, 39, 66, 0.16);
                border-radius: 8px;
                padding: 0.85rem;
                white-space: pre-wrap;
                word-break: break-word;
            }

            [data-testid="stSidebar"] pre {
                background: #ffffff !important;
                border-radius: 8px;
            }

            h1, h2, h3 {
                color: #ffffff;
                letter-spacing: 0;
            }

            .stCaptionContainer, .stMarkdown p {
                color: rgba(255, 255, 255, 0.86);
            }

            [data-testid="stMetric"],
            [data-testid="stForm"],
            [data-testid="stDataFrame"],
            [data-testid="stChatMessage"],
            [data-testid="stVerticalBlockBorderWrapper"] {
                background: var(--ltm-card);
                border: 1px solid var(--ltm-border);
                border-radius: 8px;
                box-shadow: 0 18px 45px rgba(15, 23, 42, 0.14);
            }

            [data-testid="stMetric"] {
                padding: 1rem;
            }

            [data-testid="stMetric"] label,
            [data-testid="stMetric"] [data-testid="stMetricValue"],
            [data-testid="stForm"] label,
            [data-testid="stDataFrame"] {
                color: var(--ltm-ink);
            }

            [data-testid="stForm"] {
                padding: 1rem;
            }

            .stButton > button,
            [data-testid="stFormSubmitButton"] button {
                background: linear-gradient(135deg, var(--ltm-blue), var(--ltm-teal));
                border: 0;
                color: #ffffff;
                border-radius: 8px;
                font-weight: 700;
                box-shadow: 0 10px 25px rgba(37, 99, 235, 0.28);
            }

            .stButton > button:hover,
            [data-testid="stFormSubmitButton"] button:hover {
                color: #ffffff;
                border: 0;
                filter: brightness(1.05);
            }

            .stTextInput input,
            .stNumberInput input,
            .stSelectbox div[data-baseweb="select"],
            .stTimeInput input {
                background: #ffffff;
                border-color: rgba(15, 39, 66, 0.2);
                color: var(--ltm-ink);
                border-radius: 8px;
            }

            [data-testid="stChatInput"] {
                background: rgba(255, 255, 255, 0.94);
                border-radius: 8px;
            }

            [data-testid="stChatInput"] textarea,
            [data-testid="stChatInput"] textarea::placeholder {
                color: #0f172a !important;
            }

            [data-testid="stChatMessage"] {
                padding: 0.85rem;
            }

            [data-testid="stChatMessage"],
            [data-testid="stChatMessage"] *,
            [data-testid="stChatMessage"] p {
                color: #0f172a !important;
            }

            [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
                background: #eff6ff;
                border-color: rgba(37, 99, 235, 0.18);
            }

            [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
                background: #f8fafc;
                border-color: rgba(15, 118, 110, 0.2);
            }

            .ai-agent-panel-title {
                color: #ffffff !important;
                margin-bottom: 0.15rem;
            }

            .ai-agent-panel-caption {
                color: #e0f2fe !important;
                font-size: 0.95rem;
                margin-bottom: 0.8rem;
            }

            [data-testid="stAlert"] {
                border-radius: 8px;
            }

            .ltm-brand-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 1rem;
                margin-bottom: 1.25rem;
                padding: 1rem 1.1rem;
                background: rgba(255, 255, 255, 0.92);
                border: 1px solid rgba(255, 255, 255, 0.36);
                border-radius: 8px;
                box-shadow: 0 18px 45px rgba(15, 23, 42, 0.16);
            }

            .ltm-brand-header img {
                width: min(190px, 42vw);
                height: auto;
                display: block;
            }

            .ltm-brand-eyebrow {
                color: var(--ltm-navy);
                font-size: 0.82rem;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0;
                text-align: right;
            }

            .ltm-sidebar-logo {
                padding: 0.85rem;
                margin: 0.25rem 0 1rem;
                background: rgba(255, 255, 255, 0.96);
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.18);
            }

            .ltm-sidebar-logo img {
                width: 150px;
                height: auto;
                display: block;
            }

            .agent-config-panel {
                background: #ffffff;
                border: 1px solid rgba(15, 23, 42, 0.18);
                border-radius: 8px;
                padding: 0.85rem;
                color: #020617 !important;
                font-family: "Consolas", "Courier New", monospace;
                font-size: 0.82rem;
                font-weight: 700;
                line-height: 1.55;
                white-space: pre-wrap;
                word-break: break-word;
                box-shadow: 0 12px 26px rgba(15, 23, 42, 0.16);
            }

            [data-testid="stSidebar"] .agent-config-panel,
            [data-testid="stSidebar"] .agent-config-panel * {
                color: #020617 !important;
            }

            .auth-status-panel,
            .auth-demo-panel {
                background: rgba(255, 255, 255, 0.94);
                border: 1px solid rgba(15, 39, 66, 0.14);
                border-radius: 8px;
                padding: 1rem;
                margin: 0.75rem 0 1rem;
                box-shadow: 0 14px 34px rgba(15, 23, 42, 0.12);
            }

            .auth-status-panel,
            .auth-status-panel *,
            .auth-demo-panel,
            .auth-demo-panel * {
                color: #0f172a !important;
            }

            .auth-pill {
                display: inline-block;
                margin-top: 0.35rem;
                padding: 0.22rem 0.55rem;
                border-radius: 999px;
                background: #d9f99d;
                color: #164e63 !important;
                font-size: 0.78rem;
                font-weight: 800;
            }

            @media (max-width: 720px) {
                .ltm-brand-header {
                    align-items: flex-start;
                    flex-direction: column;
                }

                .ltm-brand-eyebrow {
                    text-align: left;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="ltm-brand-header">
            <img src="{LTM_LOGO_URL}" alt="LTM logo">
            <div class="ltm-brand-eyebrow">AI Agent Management Hub</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.title("AI Agent Management Hub")
    st.caption(f"Azure AI Foundry agent: {AGENT_NAME} | version {AGENT_VERSION}")


def metric_row(records: list[dict[str, Any]], labels: tuple[str, str, str], values: tuple[Any, Any, Any]) -> None:
    columns = st.columns(3)
    for column, label, value in zip(columns, labels, values):
        column.metric(label, value)


def render_access_portal(app_name: str) -> bool:
    user = current_user(app_name)
    if user:
        left, right = st.columns([3, 1])
        with left:
            st.markdown(
                f"""
                <div class="auth-status-panel">
                    <strong>Signed in as {user["Name"]}</strong><br>
                    {user["Email"]}<br>
                    <span class="auth-pill">{user["Role"]}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with right:
            st.write("")
            st.write("")
            if st.button("Sign out", key=f"sign_out_{app_name}"):
                st.session_state.signed_in_users.pop(app_name, None)
                st.rerun()
        return True

    st.subheader(f"{app_name} Access")
    st.caption("Sign in or create an account for the selected role.")

    sign_in_tab, sign_up_tab = st.tabs(["Sign in", "Sign up"])
    roles = APP_ROLES[app_name]

    with sign_in_tab:
        with st.form(f"signin_{app_name}"):
            role = st.selectbox("Role", roles, key=f"signin_role_{app_name}")
            email = st.text_input("Email", key=f"signin_email_{app_name}")
            password = st.text_input("Password", type="password", key=f"signin_password_{app_name}")
            submitted = st.form_submit_button("Sign in")
            if submitted:
                user = find_user(app_name, email, role)
                if user and user["Password Hash"] == hash_password(password):
                    st.session_state.signed_in_users[app_name] = {
                        "Name": user["Name"],
                        "Email": user["Email"],
                        "Role": user["Role"],
                    }
                    st.success("Signed in successfully.")
                    st.rerun()
                else:
                    st.error("Invalid email, password, or role.")

        st.markdown(
            """
            <div class="auth-demo-panel">
                <strong>Demo accounts</strong><br>
                Patient: patient@ltm.com / patient123<br>
                Doctor: doctor@ltm.com / doctor123<br>
                Student: student@ltm.com / student123<br>
                Lecturer: lecturer@ltm.com / lecturer123<br>
                Employee: employee@ltm.com / employee123<br>
                Cab Admin: cabadmin@ltm.com / cabadmin123
            </div>
            """,
            unsafe_allow_html=True,
        )

    with sign_up_tab:
        with st.form(f"signup_{app_name}"):
            role = st.selectbox("Role", roles, key=f"signup_role_{app_name}")
            name = st.text_input("Full name", key=f"signup_name_{app_name}")
            email = st.text_input("Email", key=f"signup_email_{app_name}")
            phone = st.text_input("Phone", key=f"signup_phone_{app_name}")
            password = st.text_input("Create password", type="password", key=f"signup_password_{app_name}")
            confirm_password = st.text_input("Confirm password", type="password", key=f"signup_confirm_{app_name}")
            submitted = st.form_submit_button("Create account")
            if submitted:
                if not name.strip() or not email.strip() or not password:
                    st.error("Name, email, and password are required.")
                elif password != confirm_password:
                    st.error("Passwords do not match.")
                elif find_user(app_name, email, role):
                    st.error("An account already exists for this email and role.")
                else:
                    new_user = {
                        "Name": name.strip(),
                        "Email": email.strip().lower(),
                        "Phone": phone.strip(),
                        "Role": role,
                        "Password Hash": hash_password(password),
                    }
                    st.session_state.users[app_name].append(new_user)
                    st.session_state.signed_in_users[app_name] = {
                        "Name": new_user["Name"],
                        "Email": new_user["Email"],
                        "Role": new_user["Role"],
                    }
                    st.success("Account created and signed in.")
                    st.rerun()

    return False


def hospital_app() -> tuple[str, str]:
    st.subheader("Hospital Patient Management")
    patients = st.session_state.patients
    admitted = sum(1 for row in patients if row["Status"] == "Admitted")
    ready = sum(1 for row in patients if row["Status"] == "Discharge Ready")
    metric_row(patients, ("Total Patients", "Admitted", "Discharge Ready"), (len(patients), admitted, ready))

    with st.form("patient_form", clear_on_submit=True):
        cols = st.columns([1, 1, 1, 1])
        name = cols[0].text_input("Patient name")
        age = cols[1].number_input("Age", min_value=0, max_value=120, value=35)
        department = cols[2].selectbox("Department", ["Cardiology", "Neurology", "Orthopedics", "Pediatrics", "Emergency"])
        doctor = cols[3].text_input("Doctor", value="Dr. ")
        status = st.selectbox("Status", ["Admitted", "Observation", "Discharge Ready", "Outpatient"])
        if st.form_submit_button("Add patient"):
            patients.append({
                "Patient ID": f"P-{1001 + len(patients)}",
                "Name": name or "Unnamed Patient",
                "Age": age,
                "Department": department,
                "Doctor": doctor,
                "Status": status,
            })
            st.success("Patient added.")

    st.dataframe(dataframe(patients), width="stretch", hide_index=True)
    context = dataframe(patients).to_csv(index=False)
    return "Hospital Patient Management", context


def college_app() -> tuple[str, str]:
    st.subheader("College Student Management")
    students = st.session_state.students
    avg_attendance = round(sum(row["Attendance %"] for row in students) / len(students), 1)
    review_count = sum(1 for row in students if row["Status"] == "Needs Review")
    metric_row(students, ("Total Students", "Average Attendance", "Needs Review"), (len(students), f"{avg_attendance}%", review_count))

    with st.form("student_form", clear_on_submit=True):
        cols = st.columns([1, 1, 1, 1])
        name = cols[0].text_input("Student name")
        course = cols[1].selectbox("Course", ["B.Tech CSE", "BCA", "MBA", "B.Com", "B.Sc"])
        year = cols[2].selectbox("Year", ["1st", "2nd", "3rd", "4th"])
        attendance = cols[3].number_input("Attendance %", min_value=0, max_value=100, value=85)
        status = st.selectbox("Status", ["Active", "Needs Review", "Inactive", "Graduated"])
        if st.form_submit_button("Add student"):
            students.append({
                "Student ID": f"S-{2201 + len(students)}",
                "Name": name or "Unnamed Student",
                "Course": course,
                "Year": year,
                "Attendance %": attendance,
                "Status": status,
            })
            st.success("Student added.")

    st.dataframe(dataframe(students), width="stretch", hide_index=True)
    context = dataframe(students).to_csv(index=False)
    return "College Student Management", context


def cabs_app() -> tuple[str, str]:
    st.subheader("Employee Cabs Management")
    requests = st.session_state.cab_requests
    pending = sum(1 for row in requests if row["Status"] == "Pending")
    scheduled_today = len(requests)
    next_window = (datetime.now() + timedelta(minutes=45)).strftime("%H:%M")
    metric_row(requests, ("Cab Requests", "Pending", "Next Dispatch Window"), (scheduled_today, pending, next_window))

    with st.form("cab_form", clear_on_submit=True):
        cols = st.columns([1, 1, 1, 1])
        employee = cols[0].text_input("Employee")
        pickup = cols[1].text_input("Pickup")
        drop = cols[2].text_input("Drop")
        trip_time = cols[3].time_input("Time")
        status = st.selectbox("Status", ["Pending", "Scheduled", "Driver Assigned", "Completed", "Cancelled"])
        if st.form_submit_button("Add cab request"):
            requests.append({
                "Request ID": f"C-{501 + len(requests)}",
                "Employee": employee or "Unnamed Employee",
                "Pickup": pickup or "Office",
                "Drop": drop or "Home",
                "Time": trip_time.strftime("%H:%M"),
                "Status": status,
            })
            st.success("Cab request added.")

    st.dataframe(dataframe(requests), width="stretch", hide_index=True)
    context = f"Date: {date.today().isoformat()}\n" + dataframe(requests).to_csv(index=False)
    return "Employee Cabs Management", context


@st.cache_resource(show_spinner=False)
def get_agent() -> FoundryAgent:
    return FoundryAgent(AgentConfig())


def render_agent_panel(module_name: str, context: str) -> None:
    st.markdown('<h3 class="ai-agent-panel-title">AI Agent</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ai-agent-panel-caption">Ask for summaries, risk flags, scheduling help, or next actions.</div>',
        unsafe_allow_html=True,
    )
    key = module_name
    messages = st.session_state.agent_messages.setdefault(key, [])

    for message in messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    prompt = st.chat_input(f"Ask {AGENT_NAME} about {module_name.lower()}")
    if not prompt:
        return

    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Calling Azure AI Foundry agent..."):
            try:
                answer = get_agent().ask(prompt, context)
            except Exception as exc:
                answer = (
                    "I could not reach the Azure AI Foundry agent. "
                    f"Check Azure login, permissions, SDK version, and endpoint. Details: {exc}"
                )
            st.write(answer)
    messages.append({"role": "assistant", "content": answer})


def main() -> None:
    render_header()
    seed_state()

    st.sidebar.markdown(
        f"""
        <div class="ltm-sidebar-logo">
            <img src="{LTM_LOGO_URL}" alt="LTM logo">
        </div>
        """,
        unsafe_allow_html=True,
    )
    app_choice = st.sidebar.radio(
        "Applications",
        ["Hospital Patient Management", "College Student Management", "Employee Cabs Management"],
    )
    st.sidebar.divider()
    st.sidebar.write("Agent configuration")
    st.sidebar.markdown(
        f"""
        <div class="agent-config-panel">endpoint = {ENDPOINT}
agent = {AGENT_NAME}
version = {AGENT_VERSION}</div>
        """,
        unsafe_allow_html=True,
    )

    main_col, agent_col = st.columns([2, 1], gap="large")
    with main_col:
        has_access = render_access_portal(app_choice)
        if has_access:
            if app_choice == "Hospital Patient Management":
                module_name, context = hospital_app()
            elif app_choice == "College Student Management":
                module_name, context = college_app()
            else:
                module_name, context = cabs_app()

    with agent_col:
        if current_user(app_choice):
            render_agent_panel(module_name, context)
        else:
            st.subheader("AI Agent")
            st.info("Sign in or create an account to use the AI agent for this application.")


if __name__ == "__main__":
    main()
