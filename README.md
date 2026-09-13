# Finance Investment App — Exercise 7

Streamlit application that analyzes a company's annual report PDF.

## Workflow

1. User uploads an annual report PDF.
2. `pdfplumber` extracts the text.
3. Gemini extracts revenue, profit, assets, current assets/liabilities, debt, equity, operating cash flow, and risk factors.
4. Python calculates ROE, ROA, Current Ratio, Debt Ratio, and Net Margin.
5. Gemini interprets the ratios and extracted risk factors.
6. Streamlit presents the financial dashboard and downloadable investment report.

## Run locally

```bash
pip install -r requirements.txt
```

Set the API key:

**Windows PowerShell**
```powershell
$env:GOOGLE_API_KEY="your-google-api-key"
```

**macOS/Linux**
```bash
export GOOGLE_API_KEY="your-google-api-key"
```

Then:

```bash
streamlit run app.py
```

For Streamlit Cloud, add `GOOGLE_API_KEY` under **App settings → Secrets**.

> Educational analysis only. The generated output is not personalized investment advice.
