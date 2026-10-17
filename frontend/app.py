import os

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Grievance Triage Desk", page_icon="🗂️", layout="wide")
api = st.sidebar.text_input("Backend URL", os.getenv("API_URL", "http://127.0.0.1:8001")).rstrip("/")

with st.sidebar:
    st.subheader("Staff access")
    with st.form("staff_login"):
        username = st.text_input("Staff username")
        password = st.text_input("Staff password", type="password")
        login = st.form_submit_button("Sign in")
    if login:
        try:
            response = requests.get(f"{api}/stats", auth=(username, password), timeout=10)
            if response.ok:
                st.session_state["staff_credentials"] = (username, password)
                st.success("Staff signed in.")
            elif response.status_code == 503:
                st.error("Staff access is not configured on the backend.")
            else:
                st.error("Staff username or password is incorrect.")
        except requests.RequestException as exc:
            st.error(f"Backend error: {exc}")
    if st.session_state.get("staff_credentials") and st.button("Sign out"):
        del st.session_state["staff_credentials"]
        st.rerun()

staff_credentials = st.session_state.get("staff_credentials")
st.title("Grievance Triage Desk")
st.caption("Submit a complaint and securely track its status")
tab_names = ["File a complaint", "Track status"]
if staff_credentials:
    tab_names.extend(["Officer queue", "Stats"])
tabs = st.tabs(tab_names)

with tabs[0]:
    st.info("This desk accepts consumer-finance complaints, including bank accounts, cards, loans, credit reports, debt, transactions, and money transfers.")
    mode = st.radio("Input type", ["Typed text", "Image/PDF"], horizontal=True)
    with st.form("intake"):
        text = st.text_area("Complaint", height=160) if mode == "Typed text" else ""
        file = st.file_uploader(
            "Upload scan", type=["png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp", "pdf"]
        ) if mode == "Image/PDF" else None
        submit = st.form_submit_button("Submit complaint", type="primary")
    if submit and mode == "Typed text" and not text.strip():
        st.warning("Enter complaint details before submitting.")
    elif submit:
        try:
            if mode == "Typed text":
                response = requests.post(f"{api}/grievances", data={"text": text}, timeout=120)
            elif file:
                response = requests.post(
                    f"{api}/grievances",
                    files={"file": (file.name, file.getvalue(), file.type or "application/octet-stream")},
                    timeout=120,
                )
            else:
                response = None
            if response is None:
                st.warning("Choose a file first.")
            elif response.ok:
                item = response.json()
                st.success(f"Complaint #{item['id']} submitted. Current status: Pending.")
                st.warning("Save this tracking code. It is shown only once and is required to check status.")
                st.code(item["tracking_code"])
                st.write("Predicted department:", item["predicted_department"], "| confidence:", f"{item['confidence']:.1%}")
                st.write("Needs officer review:", item["needs_review"], "| reason:", item["review_reason"])
                if item["input_type"] == "file":
                    st.text_area("Extracted text", item["extracted_text"], height=140)
                st.dataframe(pd.DataFrame(item["top3"]), hide_index=True, use_container_width=True)
            else:
                try:
                    detail = response.json().get("detail", response.text)
                except ValueError:
                    detail = response.text
                if response.status_code == 400:
                    st.warning(detail)
                else:
                    st.error(detail)
        except requests.RequestException as exc:
            st.error(f"Backend error: {exc}")

with tabs[1]:
    with st.form("track_complaint"):
        grievance_id = st.number_input("Complaint ID", min_value=1, step=1)
        tracking_code = st.text_input("Tracking code", type="password")
        track = st.form_submit_button("Check status", type="primary")
    if track:
        tracking_code = tracking_code.strip()
        if len(tracking_code) < 20:
            st.warning("Enter the tracking code shown when the complaint was submitted.")
        else:
            try:
                response = requests.get(
                    f"{api}/grievances/{int(grievance_id)}/status",
                    headers={"X-Tracking-Code": tracking_code},
                    timeout=20,
                )
                if response.ok:
                    item = response.json()
                    st.metric("Status", item["status"].title())
                    st.write("Department:", item["final_department"] or "Not yet assigned")
                    if item["resolution_note"]:
                        st.write("Update from staff:", item["resolution_note"])
                    st.caption(f"Last updated: {item['updated_at']}")
                elif response.status_code == 404:
                    st.error("Complaint not found. Check the ID and tracking code.")
                else:
                    st.error(response.text)
            except requests.RequestException as exc:
                st.error(f"Backend error: {exc}")

if staff_credentials:
    queue, stats = tabs[2:]
    with queue:
        status_filter, review_filter, department_filter = st.columns(3)
        selected_status = status_filter.selectbox("Status", ["All", "Pending", "Solved", "Rejected"])
        selected_review = review_filter.selectbox("Review", ["All", "Needs review", "Auto-routed"])
        department = department_filter.text_input("Department")
        params = {}
        if selected_status != "All":
            params["status"] = selected_status.lower()
        if selected_review == "Needs review":
            params["needs_review"] = "true"
        elif selected_review == "Auto-routed":
            params["needs_review"] = "false"
        if department.strip():
            params["department"] = department.strip()
        try:
            response = requests.get(f"{api}/grievances", params=params, auth=staff_credentials, timeout=20)
            response.raise_for_status()
            rows = response.json()
            if rows:
                st.dataframe(pd.DataFrame([
                    {"ID": item["id"], "Status": item["status"].title(), "Predicted": item["predicted_department"],
                     "Final": item["final_department"], "Confidence": round(item["confidence"], 3),
                     "Needs review": item["needs_review"], "Text": item["extracted_text"][:150]}
                    for item in rows
                ]), hide_index=True, use_container_width=True)
                chosen = st.selectbox("Select complaint", rows,
                                      format_func=lambda item: f"#{item['id']} — {item['status'].title()} — {item['predicted_department']}")
                st.write(chosen["extracted_text"] or "(No extracted text)")
                st.write("Original prediction:", chosen["original_prediction"])
                with st.form("staff_update"):
                    department_update = st.text_input("Final department", value=chosen.get("final_department") or "")
                    status_update = st.selectbox("Complaint status", ["pending", "solved", "rejected"],
                                                 index=["pending", "solved", "rejected"].index(chosen["status"]))
                    resolution_note = st.text_area("Note for complainant", value=chosen.get("resolution_note") or "")
                    save = st.form_submit_button("Save update", type="primary")
                if save:
                    update_response = requests.patch(
                        f"{api}/grievances/{chosen['id']}",
                        json={"department": department_update, "status": status_update,
                              "resolution_note": resolution_note},
                        auth=staff_credentials,
                        timeout=20,
                    )
                    if update_response.ok:
                        st.success("Complaint updated; original prediction retained.")
                        st.rerun()
                    else:
                        st.error(update_response.text)
            else:
                st.info("No matching complaints.")
        except requests.RequestException as exc:
            st.error(f"Backend error: {exc}")

    with stats:
        try:
            response = requests.get(f"{api}/stats", auth=staff_credentials, timeout=20)
            response.raise_for_status()
            summary = response.json()
            total, review, corrected = st.columns(3)
            total.metric("Total", summary["total"])
            review.metric("Needs review", f"{summary['needs_review_pct']}%")
            corrected.metric("Corrected", f"{summary['corrected_pct']}%")
            st.dataframe(pd.DataFrame(summary["counts_by_department"]), hide_index=True, use_container_width=True)
        except requests.RequestException as exc:
            st.error(f"Backend error: {exc}")
