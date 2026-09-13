import io
import json
import os
from typing import Any, Dict

import pdfplumber
import streamlit as st

try:
    from google import genai
except ImportError:
    genai = None


st.set_page_config(page_title="Financial Investment Analyzer", page_icon="📊", layout="wide")

st.title("📊 Financial Investment Analyzer")
st.caption("Upload an annual report PDF → extract financials → calculate ratios → get an AI-assisted investment report.")


def extract_pdf_text(file_bytes: bytes) -> str:
    """Extract text from all pages of a PDF using pdfplumber."""
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                text_parts.append(f"\n--- PAGE {page_number} ---\n{text}")
    return "\n".join(text_parts).strip()


def get_gemini_client():
    if genai is None:
        raise RuntimeError("The google-genai package is not installed. Run: pip install google-genai")
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Set GOOGLE_API_KEY in your environment or Streamlit secrets.")
    return genai.Client(api_key=api_key)


def call_gemini(prompt: str, model: str = "gemini-3.6-flash") -> str:
    """Call Gemini using the current model required by the API error message."""
    client = get_gemini_client()
    response = client.models.generate_content(model=model, contents=prompt)
    return response.text or ""


def extract_financials(report_text: str) -> Dict[str, Any]:
    prompt = f"""
You are a financial statement extraction assistant.
Read the annual report text below and extract the most recent fiscal-year values available.
Return ONLY valid JSON. Do not add markdown fences.

Required JSON shape:
{{
  "company_name": "string or null",
  "fiscal_year": "string or null",
  "revenue": number or null,
  "profit": number or null,
  "assets": number or null,
  "current_assets": number or null,
  "current_liabilities": number or null,
  "debt": number or null,
  "cash_flow": number or null,
  "equity": number or null,
  "risk_factors": ["risk 1", "risk 2"]
}}

Rules:
- Prefer consolidated financial statements when available.
- Use values for the latest fiscal year presented.
- Normalize all monetary values to the report's stated base unit, but do not convert currencies.
- "profit" should mean profit attributable to owners / net profit when clearly available.
- "debt" should mean total interest-bearing debt when available; otherwise use total borrowings.
- "cash_flow" should mean net cash flow from operating activities when available.
- "equity" should mean total shareholders' equity attributable to owners where available.
- Use null where the report does not provide a defensible value.
- Extract up to 8 material risk factors from the report's risk-management or risk-factor sections.

ANNUAL REPORT TEXT:
{report_text[:180000]}
"""
    raw = call_gemini(prompt)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start:end + 1])
        raise ValueError(f"Gemini did not return valid JSON: {exc}") from exc


def calculate_ratios(data: Dict[str, Any]) -> Dict[str, Any]:
    def safe_divide(a, b):
        if a is None or b in (None, 0):
            return None
        return a / b

    revenue = data.get("revenue")
    profit = data.get("profit")
    assets = data.get("assets")
    current_assets = data.get("current_assets")
    current_liabilities = data.get("current_liabilities")
    debt = data.get("debt")
    equity = data.get("equity")

    return {
        "roe": safe_divide(profit, equity),
        "roa": safe_divide(profit, assets),
        "current_ratio": safe_divide(current_assets, current_liabilities),
        "debt_ratio": safe_divide(debt, assets),
        "net_margin": safe_divide(profit, revenue),
    }


def interpret_ratios(data: Dict[str, Any], ratios: Dict[str, Any]) -> str:
    prompt = f"""
Act as a cautious equity research analyst. Interpret the extracted financial data and ratios below.
Do not invent missing facts. Clearly flag unavailable or potentially ambiguous data.
Give a practical investor-oriented assessment covering profitability, efficiency, liquidity, leverage,
risk factors, key positives, key concerns, and what an investor should verify next.
Do not provide personalized financial advice.

FINANCIAL DATA:
{json.dumps(data, indent=2)}

RATIOS:
{json.dumps(ratios, indent=2)}

Return a concise but substantive report in plain text with these sections:
1. Executive View
2. Ratio Interpretation
3. Risk Assessment
4. Investor Takeaways
5. Data Limitations
"""
    return call_gemini(prompt)


def fmt_number(value):
    if value is None:
        return "Not available"
    return f"{value:,.2f}"


def fmt_percent(value):
    if value is None:
        return "N/A"
    return f"{value * 100:.2f}%"


def generate_report_markdown(data: Dict[str, Any], ratios: Dict[str, Any], interpretation: str) -> str:
    risks = data.get("risk_factors") or []
    risk_text = "\n".join(f"- {risk}" for risk in risks) if risks else "- No risk factors extracted."

    return f"""# Financial Investment Report

**Company:** {data.get('company_name') or 'Not identified'}  
**Fiscal year:** {data.get('fiscal_year') or 'Not identified'}

## Extracted Financials

| Metric | Value |
|---|---:|
| Revenue | {fmt_number(data.get('revenue'))} |
| Profit | {fmt_number(data.get('profit'))} |
| Assets | {fmt_number(data.get('assets'))} |
| Current Assets | {fmt_number(data.get('current_assets'))} |
| Current Liabilities | {fmt_number(data.get('current_liabilities'))} |
| Debt | {fmt_number(data.get('debt'))} |
| Equity | {fmt_number(data.get('equity'))} |
| Operating Cash Flow | {fmt_number(data.get('cash_flow'))} |

## Calculated Ratios

| Ratio | Value |
|---|---:|
| ROE | {fmt_percent(ratios.get('roe'))} |
| ROA | {fmt_percent(ratios.get('roa'))} |
| Current Ratio | {fmt_number(ratios.get('current_ratio'))} |
| Debt Ratio | {fmt_percent(ratios.get('debt_ratio'))} |
| Net Margin | {fmt_percent(ratios.get('net_margin'))} |

## Risk Factors

{risk_text}

## Gemini Interpretation

{interpretation}

---
Generated from the uploaded annual report. This tool is for educational analysis and is not personalized investment advice.
"""


uploaded = st.file_uploader("Upload an Annual Report PDF", type=["pdf"])

if uploaded:
    if st.button("Analyze Annual Report", type="primary", use_container_width=True):
        try:
            with st.spinner("Extracting text from PDF…"):
                report_text = extract_pdf_text(uploaded.getvalue())
            if not report_text:
                st.error("No readable text was found in the PDF. A scanned PDF may require OCR first.")
                st.stop()

            st.success(f"Extracted approximately {len(report_text):,} characters from the report.")
            with st.expander("Preview extracted text"):
                st.text(report_text[:12000])

            with st.spinner("Gemini is extracting financial data and risk factors…"):
                financials = extract_financials(report_text)

            ratios = calculate_ratios(financials)

            with st.spinner("Gemini is interpreting the ratios…"):
                interpretation = interpret_ratios(financials, ratios)

            st.session_state["financials"] = financials
            st.session_state["ratios"] = ratios
            st.session_state["interpretation"] = interpretation
            st.session_state["report_text"] = report_text
            st.success("Analysis complete.")

        except Exception as exc:
            st.error(f"Analysis failed: {exc}")


financials = st.session_state.get("financials")
ratios = st.session_state.get("ratios")
interpretation = st.session_state.get("interpretation")

if financials and ratios is not None and interpretation:
    st.divider()
    st.subheader(financials.get("company_name") or "Investment Analysis")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ROE", fmt_percent(ratios.get("roe")))
    c2.metric("ROA", fmt_percent(ratios.get("roa")))
    c3.metric("Current Ratio", fmt_number(ratios.get("current_ratio")))
    c4.metric("Debt Ratio", fmt_percent(ratios.get("debt_ratio")))
    c5.metric("Net Margin", fmt_percent(ratios.get("net_margin")))

    st.subheader("Extracted Financials")
    st.dataframe(
        {
            "Metric": ["Revenue", "Profit", "Assets", "Current Assets", "Current Liabilities", "Debt", "Equity", "Operating Cash Flow"],
            "Value": [
                fmt_number(financials.get("revenue")),
                fmt_number(financials.get("profit")),
                fmt_number(financials.get("assets")),
                fmt_number(financials.get("current_assets")),
                fmt_number(financials.get("current_liabilities")),
                fmt_number(financials.get("debt")),
                fmt_number(financials.get("equity")),
                fmt_number(financials.get("cash_flow")),
            ],
        },
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Risk Factors")
    for risk in financials.get("risk_factors") or []:
        st.write(f"• {risk}")

    st.subheader("Gemini Investment Interpretation")
    st.markdown(interpretation)

    report = generate_report_markdown(financials, ratios, interpretation)
    st.download_button(
        "Download Investment Report (Markdown)",
        data=report,
        file_name=f"{financials.get('company_name', 'investment_report').replace(' ', '_')}_investment_report.md",
        mime="text/markdown",
        use_container_width=True,
    )

with st.expander("Setup / API key"):
    st.markdown(
        "Set `GOOGLE_API_KEY` as an environment variable or in Streamlit secrets. "
        "Install dependencies with `pip install -r requirements.txt`."
    )
