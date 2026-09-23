"""Module 08 - Dedicated AWS Cloud Console & Operations Simulator."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
import streamlit as st

from dashboard.theme import inject_theme, sidebar_chrome, T
from dashboard.components.header import page_header, ticker
from dashboard.components.metrics_card import ledger, kv_block
from dashboard.ui_utils import safe, inr

inject_theme("AWS Cloud Console · FareGuard")
sidebar_chrome()

from dashboard.api_client import FareGuardAPIClient  # noqa: E402
from cloud import cloud_manager  # Direct access for rich interactive simulations

client = FareGuardAPIClient()
cloud_info = safe(client, "get_cloud_status", {}) or {}
cloud_services = cloud_info.get("services", [])
deploy_target = cloud_info.get("deployment_target", "AWS Cloud-Native (ap-south-1)")
overall_mode = cloud_info.get("overall_mode", "HYBRID_SIMULATION_READY")
region = cloud_info.get("region", "ap-south-1")

page_header(
    index="Module 08 · AWS Cloud Console",
    title="Cloud Architecture & Live AWS Simulator",
    subtitle="Simulate IAM authentication, S3 object archival, SNS auditor broadcasts, SQS dead-letter ingestion, and CloudWatch metrics in real time.",
    badges=[("AWS ap-south-1", "solid"), ("Simulated / Live", "info"), ("Zero-Cost Demo", "alert")],
)

ticker([
    f"REGION: {region.upper()}",
    f"MODE: {overall_mode}",
    "IAM: STS ASSUMEROLE ACTIVE",
    "S3: AES-256 ENCRYPTED",
    "SNS: AUDITOR BROADCAST READY",
    "SQS: DLQ POISON-PILL BUFFER",
])

# Interactive Session State for AWS Simulation
if "aws_sim_step" not in st.session_state:
    st.session_state["aws_sim_step"] = 0
if "aws_sim_logs" not in st.session_state:
    st.session_state["aws_sim_logs"] = []
if "aws_auth_user" not in st.session_state:
    st.session_state["aws_auth_user"] = "auditor.bmtc@aws-fareguard.internal"
if "aws_authenticated" not in st.session_state:
    st.session_state["aws_authenticated"] = True

tabs = st.tabs([
    "Interactive AWS Walkthrough",
    "Service Status & Endpoints",
    "Live Payload Inspector",
    "Cloud Architecture Diagram",
])

# ==============================================================================
# TAB 1: INTERACTIVE AWS WALKTHROUGH (FOR TEACHERS & EXAMINERS)
# ==============================================================================
with tabs[0]:
    st.markdown("""
    <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 18px 24px; margin-bottom: 22px;">
      <h3 style="margin: 0 0 6px 0; color: #f8fafc; font-size: 1.15rem;">Live Operational Simulation: Edge ETM to Cloud Anomaly Resolution</h3>
      <p style="margin: 0; color: #94a3b8; font-size: 0.88rem; line-height: 1.5;">
        Demonstrate to your examiners the exact lifecycle of an anomaly event flowing through AWS services:
        <strong>IAM Authentication &rarr; Corrupted Telemetry Ingestion (SQS DLQ) &rarr; ML Artifact Storage (S3) &rarr; Auditor SMS/Email Broadcast (SNS) &rarr; CloudWatch Metric Telemetry</strong>.
      </p>
    </div>
    """, unsafe_allow_html=True)

    # Step Controller
    col_ctrl, col_stats = st.columns([1.8, 1.2], gap="large")

    with col_ctrl:
        st.markdown("#### Scenario Parameters")
        s_col1, s_col2 = st.columns(2)
        with s_col1:
            sel_route = st.selectbox("Simulated BMTC Route", ["500D (Silk Board - Hebbal)", "335E (Majestic - Kadugodi)", "G-4 (Brigade Rd - Bannerghatta)", "201-R (Kengeri - Domlur)"])
        with s_col2:
            sel_deficit = st.number_input("Injected Revenue Deficit (₹)", min_value=100.0, max_value=25000.0, value=1450.0, step=150.0)

        step_btn_col1, step_btn_col2, step_btn_col3 = st.columns([1, 1, 1])
        with step_btn_col1:
            run_step = st.button("Advance Next AWS Step", use_container_width=True, type="primary")
        with step_btn_col2:
            run_all = st.button("Execute Full Pipeline", use_container_width=True)
        with step_btn_col3:
            reset = st.button("Reset Simulator", use_container_width=True)

        if reset:
            st.session_state["aws_sim_step"] = 0
            st.session_state["aws_sim_logs"] = []
            st.rerun()

        if run_step:
            st.session_state["aws_sim_step"] = min(5, st.session_state["aws_sim_step"] + 1)
        if run_all:
            st.session_state["aws_sim_step"] = 5

    with col_stats:
        st.markdown("#### Cloud Execution Status")
        current_step = st.session_state["aws_sim_step"]
        steps_map = {
            0: ("STANDBY", "System Idle / Awaiting Anomaly", "warn"),
            1: ("IAM AUTHENTICATED", "AWS STS Token Active", "ok"),
            2: ("SQS INGESTED", "DLQ Filter & Event Buffer", "ok"),
            3: ("S3 COMMITTED", "Immutable Evidence Archive", "ok"),
            4: ("SNS BROADCAST", "Auditor Alert Dispatched", "ok"),
            5: ("CLOUDWATCH SYNCED", "Operational Metric Published", "ok"),
        }
        status_name, desc, tone = steps_map.get(current_step, ("UNKNOWN", "", "warn"))
        
        ledger([
            {"label": "Pipeline Step", "value": f"0{current_step} / 05"},
            {"label": "AWS Status", "value": status_name, "tone": tone},
            {"label": "Target Region", "value": region},
            {"label": "Encryption", "value": "AWS KMS / SSE-S3"},
        ])

    st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 24px 0;'>", unsafe_allow_html=True)

    # Visual Workflow Steps
    w1, w2, w3, w4, w5 = st.columns(5)
    def step_card(col, num, title, service, active, done):
        border = "#22c55e" if done else ("#38bdf8" if active else "rgba(255,255,255,0.08)")
        bg = "rgba(34, 197, 94, 0.08)" if done else ("rgba(56, 189, 248, 0.08)" if active else "rgba(255,255,255,0.02)")
        badge = "COMPLETED" if done else ("RUNNING" if active else "PENDING")
        badge_color = "#22c55e" if done else ("#38bdf8" if active else "#64748b")
        with col:
            st.markdown(f"""
            <div style="border: 1px solid {border}; background: {bg}; border-radius: 8px; padding: 12px; min-height: 125px; transition: all 0.3s ease;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                   <span style="font-family:monospace; font-size:11px; color:#94a3b8;">STEP 0{num}</span>
                   <span style="font-size:10px; font-weight:700; color:{badge_color}; text-transform:uppercase;">{badge}</span>
                </div>
                <div style="font-weight:700; font-size:13px; color:#f8fafc; margin-top:6px;">{title}</div>
                <div style="font-size:11px; color:#38bdf8; font-family:monospace; margin-top:2px;">{service}</div>
            </div>
            """, unsafe_allow_html=True)

    step_card(w1, 1, "IAM Auth", "AWS STS & IAM", current_step == 1, current_step > 1)
    step_card(w2, 2, "Telemetry DLQ", "Amazon SQS", current_step == 2, current_step > 2)
    step_card(w3, 3, "Artifact Store", "Amazon S3", current_step == 3, current_step > 3)
    step_card(w4, 4, "Auditor Alert", "Amazon SNS", current_step == 4, current_step > 4)
    step_card(w5, 5, "CloudWatch", "CloudWatch Metrics", current_step == 5, current_step >= 5)

    st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)

    # Detailed Step Explanations & Mock AWS Outputs
    if current_step >= 1:
        with st.expander("Step 1: AWS IAM Identity & Access Management (STS AssumeRole)", expanded=(current_step == 1)):
            st.markdown(f"""
            **What happens under the hood:**
            When a bus inspector, conductor device, or auditor logs into FareGuard, the backend initiates an `sts:AssumeRole` request to generate a least-privilege, temporary security token valid for 1 hour.
            """)
            c1, c2 = st.columns([1.5, 1])
            with c1:
                st.code(json.dumps({
                    "ResponseMetadata": {"RequestId": f"sts-req-{hash(sel_route) % 100000}", "HTTPStatusCode": 200},
                    "Credentials": {
                        "AccessKeyId": f"ASIA{str(abs(hash(sel_route)))[:12]}MEMBER",
                        "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                        "SessionToken": "AQoDYXdzEJr1...[Truncated IAM Session Token]...",
                        "Expiration": "2026-09-24T08:00:00Z"
                    },
                    "AssumedRoleUser": {
                        "AssumedRoleId": f"AROA{str(abs(hash(sel_route)))[:8]}:bmtc_auditor",
                        "Arn": f"arn:aws:sts::{region}:123456789012:assumed-role/FareGuardTransitInspector/{st.session_state['aws_auth_user']}"
                    }
                }, indent=2), language="json")
            with c2:
                st.markdown("**Attached IAM Policy Permissions:**")
                st.markdown("""
                - `s3:PutObject` -> `arn:aws:s3:::fareguard-cloud-artifacts/audits/*`
                - `sns:Publish` -> `arn:aws:sns:ap-south-1:*:fareguard-auditor-alerts`
                - `sqs:SendMessage` -> `arn:aws:sqs:ap-south-1:*:fareguard-telemetry-dlq`
                - `cloudwatch:PutMetricData` -> `FareGuard/TransitIntelligence`
                """)

    if current_step >= 2:
        with st.expander("Step 2: Amazon SQS Dead-Letter Queue (Fault-Tolerant Buffering)", expanded=(current_step == 2)):
            st.markdown("""
            **What happens under the hood:**
            Edge Electronic Ticket Machines (ETMs) occasionally transmit corrupted GPS pulses or checksum-violating passenger entries. Rather than dropping transactions, FareGuard routes poison pills directly to Amazon SQS Dead Letter Queue (DLQ).
            """)
            sqs_res = cloud_manager.sqs.push_malformed_event(
                raw_event={"route": sel_route.split()[0], "corrupt_bits": "0xFFE10", "timestamp": datetime.now(timezone.utc).isoformat()},
                reason="GPS Drift & Checksum mismatch detected on conductor device",
                source_component="bmtc_edge_etm_processor"
            )
            c1, c2 = st.columns([1.5, 1])
            with c1:
                st.code(json.dumps(sqs_res, indent=2), language="json")
            with c2:
                st.info(f"**Target Queue URL:**\n`https://sqs.{region}.amazonaws.com/123456789012/fareguard-telemetry-dlq`\n\n**Outcome:** Zero passenger ticket transactions lost during bus tunnel or signal dead-zones.")

    if current_step >= 3:
        with st.expander("Step 3: Amazon S3 Cloud Storage (Immutable Audit Dossier)", expanded=(current_step == 3)):
            st.markdown("""
            **What happens under the hood:**
            Once our Machine Learning models flag an anomaly corridor, FareGuard packages the entire evidence dossier (route graphs, expected demand, fare gap) and archives it into Amazon S3 with AES-256 encryption.
            """)
            alert_id = f"ALRT-{abs(hash(sel_route)) % 90000 + 10000}"
            s3_res = cloud_manager.s3.save_audit_snapshot(
                alert_id=alert_id,
                dossier_data={
                    "alert_id": alert_id,
                    "route": sel_route,
                    "revenue_deficit_inr": sel_deficit,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "FareGuard Edge Scanner",
                }
            )
            c1, c2 = st.columns([1.5, 1])
            with c1:
                st.code(json.dumps(s3_res, indent=2), language="json")
            with c2:
                st.success(f"**S3 Bucket:** `s3://fareguard-cloud-artifacts/`\n\n**Storage Class:** STANDARD / Glacier Transition (30 days)\n\n**Integrity:** SHA-256 ETag verified.")

    if current_step >= 4:
        with st.expander("Step 4: Amazon Simple Notification Service (Auditor SMS & Email Dispatch)", expanded=(current_step == 4)):
            st.markdown("""
            **What happens under the hood:**
            High-severity revenue leakage automatically triggers an Amazon SNS notification topic. Field transit inspectors receive instant SMS and dispatch emails with exact GPS coordinates and expected discrepancy.
            """)
            alert_id = f"ALRT-{abs(hash(sel_route)) % 90000 + 10000}"
            sns_res = cloud_manager.sns.publish_alert(
                alert_id=alert_id,
                route_id=sel_route.split()[0],
                risk_score=0.94,
                deficit_inr=sel_deficit,
                severity="HIGH_RISK",
                message=f"Live simulation: Rapid inspection recommended for corridor {sel_route}.",
            )
            c1, c2 = st.columns([1.5, 1])
            with c1:
                st.code(json.dumps(sns_res, indent=2), language="json")
            with c2:
                st.markdown(f"""
                <div style="background: rgba(196, 68, 31, 0.1); border: 1px solid #c4441f; border-radius: 6px; padding: 12px; font-family: monospace; font-size: 11px; color: #f8fafc;">
                  <strong>[SMS / PUSH NOTIFICATION SENT]</strong><br>
                  FARE GUARD CRITICAL DISPATCH<br>
                  Route: {sel_route.split()[0]}<br>
                  Deficit: ₹{sel_deficit:,.2f}<br>
                  Inspector: Unit 4 (Majestic Corridor)<br>
                  Topic: arn:aws:sns:{region}:...
                </div>
                """, unsafe_allow_html=True)

    if current_step >= 5:
        with st.expander("Step 5: Amazon CloudWatch (Observability, Telemetry & Alarms)", expanded=(current_step == 5)):
            st.markdown("""
            **What happens under the hood:**
            Custom metric vectors are dispatched to AWS CloudWatch under the namespace `FareGuard/TransitIntelligence`. If the aggregate deficit exceeds ₹10,000/hr, CloudWatch alarms transition to `ALARM` state.
            """)
            cw_res1 = cloud_manager.cloudwatch.put_metric("DiscrepancyINR", sel_deficit, "None")
            cw_res2 = cloud_manager.cloudwatch.put_metric("AnomaliesDetected", 1.0, "Count")
            c1, c2 = st.columns([1.5, 1])
            with c1:
                st.code(json.dumps({
                    "CloudWatchMetricDispatches": [cw_res1, cw_res2],
                    "Namespace": "FareGuard/TransitIntelligence",
                    "AlarmStatus": "ALARM" if sel_deficit > 5000 else "OK",
                    "Dimensions": [{"Name": "Route", "Value": sel_route.split()[0]}, {"Name": "Environment", "Value": "Production"}],
                }, indent=2), language="json")
            with c2:
                st.markdown(f"""
                **CloudWatch Dashboard Metrics:**
                - `FareGuard/DiscrepancyINR`: ₹{sel_deficit:,.2f}
                - `FareGuard/AnomaliesDetected`: +1
                - `Latency`: 12 ms
                """)
                st.success("Full End-to-End AWS Lifecycle Simulation Completed!")

# ==============================================================================
# TAB 2: SERVICE STATUS & ENDPOINTS
# ==============================================================================
with tabs[1]:
    st.markdown("### AWS Cloud Managed Services Table")
    if cloud_services:
        c_rows = []
        for i, cs in enumerate(cloud_services):
            s_name = cs.get("service", "Service")
            s_status = cs.get("status", "ONLINE")
            s_mode = cs.get("mode", "AWS_LIVE")
            latency = cs.get("ping_latency_ms", 10)
            endpoint = cs.get("endpoint", f"{region}.amazonaws.com")
            
            status_pill = (
                f'<span class="fg-pill" style="background:rgba(34,197,94,0.15);color:#22c55e;border:1px solid rgba(34,197,94,0.3);">{s_status}</span>'
                if s_status.upper() in ("ONLINE", "HEALTHY", "CONNECTED")
                else f'<span class="fg-pill" style="background:rgba(234,179,8,0.15);color:#eab308;border:1px solid rgba(234,179,8,0.3);">{s_status}</span>'
            )
            
            mode_pill = (
                f'<span style="font-family:monospace;font-size:11px;color:#38bdf8;">{s_mode}</span>'
            )

            c_rows.append(
                f'<tr style="--i:{i}">'
                f'<td><b>{s_name}</b></td>'
                f'<td>{status_pill}</td>'
                f'<td>{mode_pill}</td>'
                f'<td style="font-family:monospace;font-size:11px;color:#94a3b8;">{endpoint}</td>'
                f'<td class="num">{latency} ms</td>'
                f'</tr>'
            )

        st.markdown(
            '<table class="fg-table"><thead><tr>'
            '<th>Cloud Service</th><th>Operational Status</th><th>Runtime Mode</th><th>Active Endpoint</th><th>Latency</th>'
            '</tr></thead><tbody>' + "".join(c_rows) + '</tbody></table>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    st.markdown("### Cloud Environment Configuration")
    cfg_col1, cfg_col2 = st.columns(2)
    with cfg_col1:
        kv_block("AWS Runtime Specs", [
            ("AWS Region", region),
            ("Deployment Target", deploy_target),
            ("S3 Bucket", cloud_manager.s3.bucket_name),
            ("SNS Topic", cloud_manager.sns.topic_arn.split(":")[-1] if ":" in cloud_manager.sns.topic_arn else cloud_manager.sns.topic_arn),
        ])
    with cfg_col2:
        kv_block("Resilience & Observability", [
            ("SQS DLQ Name", cloud_manager.sqs.queue_url.split("/")[-1]),
            ("CloudWatch Namespace", cloud_manager.cloudwatch.namespace),
            ("Simulation Fallback", "Graceful zero-downtime enabled"),
            ("Credential Security", "KMS Encrypted / Zero Hardcoded Secrets"),
        ])

# ==============================================================================
# TAB 3: LIVE PAYLOAD INSPECTOR
# ==============================================================================
with tabs[2]:
    st.markdown("### Live Cloud Buffer & Dispatches")
    st.markdown("Inspect real-time telemetry packets that have been sent through the SNS, SQS, and S3 channels during this session.")
    
    p_col1, p_col2 = st.columns(2)
    with p_col1:
        st.markdown("#### Recent Amazon SNS Notifications")
        recent_sns = cloud_manager.sns.get_recent_dispatches(5)
        if recent_sns:
            for s in recent_sns:
                st.code(json.dumps(s, indent=2), language="json")
        else:
            st.info("No SNS alerts dispatched yet in this session. Trigger one from Tab 1!")

    with p_col2:
        st.markdown("#### Recent Amazon SQS DLQ Messages")
        recent_sqs = cloud_manager.sqs.get_recent_dlq_events(5)
        if recent_sqs:
            for q in recent_sqs:
                st.code(json.dumps(q, indent=2), language="json")
        else:
            st.info("No corrupted telemetry sent to DLQ yet. Trigger one from Tab 1!")

    st.markdown("<hr style='border-color:rgba(255,255,255,0.08);'>", unsafe_allow_html=True)
    st.markdown("#### CloudWatch Dispatched Metrics")
    recent_cw = cloud_manager.cloudwatch.get_recent_metrics(8)
    if recent_cw:
        cw_summary = [{"Timestamp": m.get("timestamp", "")[:19], "Metric": m.get("metric_name"), "Value": m.get("value"), "Unit": m.get("unit")} for m in recent_cw]
        st.dataframe(cw_summary, use_container_width=True)
    else:
        st.info("CloudWatch metric queue is ready.")

# ==============================================================================
# TAB 4: ARCHITECTURE DIAGRAM
# ==============================================================================
with tabs[3]:
    st.markdown("### FareGuard AWS Cloud-Native Architecture")
    st.markdown("""
    This diagram demonstrates how FareGuard fits into a municipal-scale transit authority (BMTC) deployment on Amazon Web Services:
    """)
    
    st.markdown("""
    ```
    +---------------------------------------------------------------------------------------------------+
    |                                   AWS CLOUD INFRASTRUCTURE (ap-south-1)                          |
    |                                                                                                   |
    |   +-------------------+          +---------------------+          +---------------------------+   |
    |   | Edge Bus ETM      |  HTTPS   | AWS API Gateway     |  Stream  | Amazon SQS                |   |
    |   | GPS / Cash Box    | -------> | / Ingestion Lambda  | -------> | Dead Letter Queue (DLQ)   |   |
    |   +-------------------+          +---------------------+          +---------------------------+   |
    |                                             |                                   |                 |
    |                                             v                                   v                 |
    |                                  +---------------------+          +---------------------------+   |
    |                                  | FareGuard Core      |          | Corrupted Telemetry Audit |   |
    |                                  | ML Inference Engine |          | Reconciliation            |   |
    |                                  +---------------------+          +---------------------------+   |
    |                                             |                                                     |
    |                   +-------------------------+-------------------------+                           |
    |                   |                         |                         |                           |
    |                   v                         v                         v                           |
    |        +--------------------+    +--------------------+    +--------------------+                 |
    |        | Amazon S3          |    | Amazon SNS         |    | Amazon CloudWatch  |                 |
    |        | Model Registry &   |    | Real-time SMS &    |    | Metrics, Logs &    |                 |
    |        | Audit Snapshots    |    | Auditor Dispatch   |    | Alarms (TPS, INR)  |                 |
    |        +--------------------+    +--------------------+    +--------------------+                 |
    +---------------------------------------------------------------------------------------------------+
    ```
    """)
    
    st.markdown("""
    #### Architectural Highlights for Examiners:
    1. **Decoupled Edge Ingestion**: Buses in high-density corridors or tunnels buffer telemetry; if network corruption occurs, **Amazon SQS DLQ** retains events without loss.
    2. **Auditable & Immutable Evidence**: Fare discrepancy dossiers stored in **Amazon S3** cannot be tampered with or modified by conductors.
    3. **Immediate Operational Action**: **Amazon SNS** bridges ML predictions to boots-on-the-ground bus inspectors in under 500ms.
    4. **Telemetry & Governance**: Centralized metrics in **AWS CloudWatch** give municipal transport managers a single pane of glass.
    """)
