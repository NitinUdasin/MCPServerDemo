"""
LangGraph Financial Data Node — MCP STDIO Transport
=====================================================
Compatible with langchain-mcp-adapters >= 0.1.0

All fixes:
  1. MultiServerMCPClient NOT used as context manager
  2. ratio tool returns list  → safe_get() handles both dict and list
  3. pnl / cashflow / balancesheet return pandas df.to_string()
     → parse_dataframe_string() converts to list[dict] correctly
"""

import asyncio
import json
import re
from typing import Any, Optional, TypedDict
import pandas as pd

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.graph import StateGraph, END
import logging
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_core.runnables import Runnable
from langchain_core.messages import HumanMessage


# ─────────────────────────────────────────────────────────────
# MCP Server STDIO Configuration
# ─────────────────────────────────────────────────────────────

MCP_CONFIG = { 
    "Financial Data Provider": {
        "transport": "stdio",
        "command": "C:\\Users\\nitin\\.local\\bin\\uv.exe",
        "args": [
            "run",
            "fastmcp",
            "run",
            "C:\\WorkSpace\\POC\\MCPServerDemo\\DataprovidersMCPServer.py"
       ]
    }
    }


# ─────────────────────────────────────────────────────────────
# State Schema
# ─────────────────────────────────────────────────────────────

class FinancialState(TypedDict, total=False):
    ticker:             str
    pnl_data:           Any
    cash_flow:          Any
    balance_sheet_data: Any
    ratios:             dict
    error:              Optional[str]
    lynch_score:        float
    lynch_fair_value:   float
    category :          str
    qualitative_lynch_analysis: str
    sector:         str



# ─────────────────────────────────────────────────────────────
# DataFrame String Parser
#
# Handles pandas df.to_string() / df.__repr__() output:
#
#   "                  Metric Mar 2015 Mar 2016  ... Mar 2023 Mar 2024 Mar 2025
#    0              Revenue -    5,392    7,299  ...   41,411   54,974   69,709
#    1         Sales Growth %      NaN   35.35%  ...   30.88%   32.75%   26.80%
#    ...
#    [23 rows x 12 columns]"
#
# Returns: list[dict]  e.g.
#   [{"Metric": "Revenue -", "Mar 2015": "5,392", ..., "Mar 2025": "69,709"}, ...]
# ─────────────────────────────────────────────────────────────

def parse_dataframe_string(text: str) -> list:
    """
    Convert a pandas DataFrame string (df.to_string / __repr__) into
    a list of row dicts keyed by column name.

    Handles:
      • Truncated middle columns shown as "..."
      • Leading integer row index on every data line
      • Comma-formatted numbers, % values, NaN
    """
    text = text.strip()

    # ── Remove [N rows x M columns] footer ───────────────────
    text = re.sub(r'\n\[\d+ rows x \d+ columns\]\s*$', '', text)
    lines = [l for l in text.split('\n') if l.strip()]
    if not lines:
        return []

    # ── Parse header → visible column names ──────────────────
    # Header example: "                  Metric Mar 2015 Mar 2016  ... Mar 2023 Mar 2024 Mar 2025"
    # Columns are "Metric" + "Mar YYYY" tokens; "..." is a placeholder for hidden cols.
    header = lines[0]
    header_no_dots = re.sub(r'\s*\.\.\.\s*', ' __DOTS__ ', header)
    tokens = re.findall(r'Metric|[A-Z][a-z]{2} \d{4}|__DOTS__|\b(?:Q[1-4] \d{4})\b', header_no_dots)
    col_names = [t for t in tokens if t != '__DOTS__']

    if not col_names:
        # Fallback: split header on 2+ spaces, drop "..."
        col_names = [c for c in re.split(r'\s{2,}', header.strip()) if c != '...']

    # ── Parse each data row ───────────────────────────────────
    records = []
    for line in lines[1:]:
        # Remove leading row index: "0   Revenue -   ..." → "Revenue -   ..."
        content = re.sub(r'^\s*\d+\s{2,}', '', line)
        # Remove "  ...  " truncation placeholder
        content = re.sub(r'\s{2,}\.\.\.\s{2,}', '  ', content)
        # Split on 2+ spaces
        parts = re.split(r'\s{2,}', content.strip())

        if len(parts) < 2:
            continue

        metric = parts[0].strip()
        values = parts[1:]

        row = {"Metric": metric}
        for i, col in enumerate(col_names[1:]):   # col_names[0] == "Metric"
            row[col] = values[i].strip() if i < len(values) else None

        if metric:
            records.append(row)

    return records


# ─────────────────────────────────────────────────────────────
# Generic MCP Result Normaliser
# ─────────────────────────────────────────────────────────────

def parse_tool_result(raw: Any, is_dataframe: bool = False) -> Any:
    """
    Normalise any MCP tool response.

    Handles:
      • dict                    → as-is
      • JSON string             → json.loads()
      • DataFrame string        → parse_dataframe_string()
      • list of content blocks  → unwrap {"type":"text","text":"..."}, then recurse
      • Double-encoded strings  → decode twice if needed
    """
    if isinstance(raw, dict):
        return raw

    if isinstance(raw, str):
        # Try to decode JSON (handles double-encoded strings)
        try:
            decoded = json.loads(raw)
            # If decoded to a string, it was double-encoded - recurse
            if isinstance(decoded, str):
                return parse_tool_result(decoded, is_dataframe=is_dataframe)
            return decoded
        except (json.JSONDecodeError, ValueError):
            pass
        # Not JSON, treat as DataFrame string if flagged
        if is_dataframe:
            return parse_dataframe_string(raw)
        # Try parsing as DataFrame string anyway
        return parse_dataframe_string(raw)

    if isinstance(raw, list):
        # MCP content-block envelope: [{"type": "text", "text": "..."}]
        for block in raw:
            if isinstance(block, dict) and "text" in block:
                return parse_tool_result(block["text"], is_dataframe=is_dataframe)
            if isinstance(block, dict) and "type" not in block:
                return block
        return raw   # already a plain list

    return raw


# ─────────────────────────────────────────────────────────────
# Safe getter — works for both dict and list payloads
# ─────────────────────────────────────────────────────────────

def safe_get(data: Any, key: str, default=None):
    if isinstance(data, dict):
        return data.get(key, default)
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and key in item:
                return item[key]
    return default


# ─────────────────────────────────────────────────────────────
# Metric extractors (work on list[dict] from parse_dataframe_string)
# ─────────────────────────────────────────────────────────────

def find_metric_row(records: Any, keyword: str) -> Optional[dict]:
    """Return the first row whose Metric contains keyword (case-insensitive)."""
    if not isinstance(records, list):
        return None
    for row in records:
        if isinstance(row, dict) and keyword.lower() in str(row.get("Metric", "")).lower():
            return row
    return None


def row_year_values(row: dict) -> list:
    """Return all year-column values from a row (skips the Metric key)."""
    return [v for k, v in row.items() if k != "Metric" and v not in (None, "")]


def to_float(val: Any) -> Optional[float]:
    """Convert a string like '1,279', '26.80%', 'NaN' to float or None."""
    try:
        s = str(val).replace(",", "").replace("%", "").strip()
        if s.lower() in ("nan", "none", ""):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def extract_eps_history(pnl_data: Any) -> list:
    row = find_metric_row(pnl_data, "EPS in Rs")
    return row_year_values(row) if row else []


def extract_sales_values(pnl_data: Any) -> list:
    row = find_metric_row(pnl_data, "Sales Growth")
    return row_year_values(row) if row else []


def calculate_eps_growth(eps_values: list) -> Optional[float]:
    numeric = [to_float(v) for v in eps_values if to_float(v) is not None]
    if len(numeric) >= 2:
        prev, latest = numeric[-2], numeric[-1]
        if prev and prev != 0:
            return round(((latest - prev) / abs(prev)) * 100, 2)
    return None


def extract_fcf(cash_flow: Any) -> Optional[float]:
    """FCF = Operating Cash Flow − |Capital Expenditure| (latest year)."""
    try:
        ocf_row   = find_metric_row(cash_flow, "Operating")
        capex_row = find_metric_row(cash_flow, "Capital Expenditure")

        def latest(row):
            if not row:
                return 0.0
            vals = [to_float(v) for v in row_year_values(row) if to_float(v) is not None]
            return vals[-1] if vals else 0.0

        return round(latest(ocf_row) - abs(latest(capex_row)), 2)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# Option 1 — client.get_tools()  ✅ Recommended
# ─────────────────────────────────────────────────────────────

async def financial_data_node_async(state: FinancialState) -> FinancialState:
    """
    Async LangGraph node.
    Does NOT use MultiServerMCPClient as a context manager (0.1.0+ compatible).
    """
    ticker = state.get("ticker", "")
    if not ticker:
        return {**state, "error": "No ticker provided in state."}

    client   = MultiServerMCPClient(MCP_CONFIG)
    tools    = await client.get_tools()
    tool_map = {t.name: t for t in tools}

    async def call_tool(name: str, is_dataframe: bool = False, **kwargs) -> Any:
        if name not in tool_map:
            return {"error": f"Tool '{name}' not found."}
        try:
            raw = await tool_map[name].ainvoke(kwargs)
            return parse_tool_result(raw, is_dataframe=is_dataframe)
        except Exception as e:
            return {"error": str(e)}

    # pnl / cashflow / balancesheet → DataFrame strings
    # ratio                         → JSON dict/list
    profit_loss, cash_flow, balancesheet, ratio = await asyncio.gather(
        call_tool("get_profitLoss",   is_dataframe=True,  tickerName=ticker),
        call_tool("get_cashFlows",    is_dataframe=True,  tickerName=ticker),
        call_tool("get_balancesheet", is_dataframe=True,  tickerName=ticker),
        call_tool("get_Ratio",        is_dataframe=False, tickerName=ticker),
    )

    eps_values   = extract_eps_history(profit_loss)
    sales_values = extract_sales_values(profit_loss)
    eps_growth   = calculate_eps_growth(eps_values)
    fcf          = extract_fcf(cash_flow)

    return {
        **state,
        "pnl_data":           profit_loss,
        "cash_flow":          cash_flow,
        "balance_sheet_data": balancesheet,
        "ratios": {
            "pe_ratio":        safe_get(ratio, "StockPE"),
            "eps_history":     eps_values,
            "debt_to_equity":  safe_get(ratio, "Debttoequity"),
            "fcf":             fcf,
            "revenue_growths": sales_values,
            "peg":             safe_get(ratio, "PEGRatio"),
            "marketCap":       safe_get(ratio, "MarketCap"),
            "price":           safe_get(ratio, "CurrentPrice"),
            "book_value":      safe_get(ratio, "BookValue"),
            "roe":             safe_get(ratio, "ROE"),
            "eps_growth":      eps_growth,
        },
    }


# # ─────────────────────────────────────────────────────────────
# # Option 2 — client.session() + load_mcp_tools()  ✅ Alternative
# # ─────────────────────────────────────────────────────────────

# async def financial_data_node_session_async(state: FinancialState) -> FinancialState:
#     ticker = state.get("ticker", "")
#     if not ticker:
#         return {**state, "error": "No ticker provided in state."}

#     client = MultiServerMCPClient(MCP_CONFIG)

#     async with client.session("financial_data_provider") as session:
#         tools    = await load_mcp_tools(session)
#         tool_map = {t.name: t for t in tools}

#         async def call_tool(name: str, is_dataframe: bool = False, **kwargs) -> Any:
#             if name not in tool_map:
#                 return {"error": f"Tool '{name}' not found."}
#             try:
#                 raw = await tool_map[name].ainvoke(kwargs)
#                 return parse_tool_result(raw, is_dataframe=is_dataframe)
#             except Exception as e:
#                 return {"error": str(e)}

#         profit_loss, cash_flow, balancesheet, ratio = await asyncio.gather(
#             call_tool("get_profitLoss",   is_dataframe=True,  tickerName=ticker),
#             call_tool("get_cashFlows",    is_dataframe=True,  tickerName=ticker),
#             call_tool("get_balancesheet", is_dataframe=True,  tickerName=ticker),
#             call_tool("get_Ratio",        is_dataframe=False, tickerName=ticker),
#         )

#     eps_values   = extract_eps_history(profit_loss)
#     sales_values = extract_sales_values(profit_loss)
#     eps_growth   = calculate_eps_growth(eps_values)
#     fcf          = extract_fcf(cash_flow)

#     return {
#         **state,
#         "pnl_data":           profit_loss,
#         "cash_flow":          cash_flow,
#         "balance_sheet_data": balancesheet,
#         "ratios": {
#             "pe_ratio":        safe_get(ratio, "StockPE"),
#             "eps_history":     eps_values,
#             "debt_to_equity":  safe_get(ratio, "Debttoequity"),
#             "fcf":             fcf,
#             "revenue_growths": sales_values,
#             "peg":             safe_get(ratio, "PEGRatio"),
#             "marketCap":       safe_get(ratio, "MarketCap"),
#             "price":           safe_get(ratio, "CurrentPrice"),
#             "book_value":      safe_get(ratio, "BookValue"),
#             "roe":             safe_get(ratio, "ROE"),
#             "eps_growth":      eps_growth,
#         },
#     }


# ─────────────────────────────────────────────────────────────
# Sync wrappers
# ─────────────────────────────────────────────────────────────

def financial_data_node(state: FinancialState) -> FinancialState:
    return asyncio.run(financial_data_node_async(state))

# def financial_data_node_session(state: FinancialState) -> FinancialState:
#     return asyncio.run(financial_data_node_session_async(state))



def valuation_collection(state: dict) -> dict:
    """
    Perform financial analysis on stock data and calculate key metrics.

    Args:
        state (dict): A dictionary containing stock data under the key "pnl_data".
                      The "pnl_data" value is a list[dict] with rows containing:
                      - "Metric": Row label (e.g., "EPS in Rs", "Dividend Payout %")
                      - Year columns: "Mar 2015", "Mar 2016", etc.
        state["ratios"]["price"]: Current stock price.

    Returns:
        dict: Updated state with additional keys:
              - "lynch_score"
              - "lynch_fair_value"
    """
    # Validate input
    if "pnl_data" not in state:
        raise KeyError("Input 'state' must contain a 'pnl_data' key with list[dict].")

    pnl_data = state["pnl_data"]

    # Helper to find row by keyword and extract year values
    def find_metric_values(keyword: str) -> list:
        for row in pnl_data:
            if isinstance(row, dict) and keyword.lower() in str(row.get("Metric", "")).lower():
                return [v for k, v in row.items() if k != "Metric" and v not in (None, "")]
        return []

    # Helper to convert values to float
    def to_float(val: Any) -> Optional[float]:
        try:
            s = str(val).replace(",", "").replace("%", "").strip()
            if s.lower() in ("nan", "none", ""):
                return None
            return float(s)
        except (ValueError, TypeError):
            return None

    eps_values_raw = find_metric_values("EPS in Rs")
    dividend_payout_raw = find_metric_values("Dividend Payout %")

    if not eps_values_raw:
        raise KeyError("EPS in Rs row not found in pnl_data")
    if not dividend_payout_raw:
        raise KeyError("Dividend Payout % row not found in pnl_data")

    eps_values = [to_float(v) for v in eps_values_raw]
    dividend_payout = [to_float(v) for v in dividend_payout_raw]

    # Filter out None values
    eps_values = [v for v in eps_values if v is not None]
    dividend_payout = [v for v in dividend_payout if v is not None]

    stock_price = state["ratios"]["price"]
    # Handle missing or invalid stock price
    if stock_price is None:
        raise ValueError("Current stock price must be provided.")
    if stock_price <= 0:
        raise ValueError("Stock price must be greater than zero.")

    # --- Step 1: EPS CAGR ---
    start_eps = eps_values[0]
    end_eps = eps_values[-1]
    n_years = len(eps_values) - 1

    if start_eps == 0 or end_eps == 0 or n_years <= 0:
        eps_cagr = 0
    else:
        eps_cagr = ((end_eps / start_eps) ** (1 / n_years) - 1) * 100

    # --- Step 2: Dividend Payout CAGR ---
    if len(dividend_payout) < 2:
        div_cagr = 0
    else:
        start_div = dividend_payout[0]
        end_div = dividend_payout[-1]

        if start_div == 0 or end_div == 0:
            div_cagr = 0
        else:
            div_cagr = ((end_div / start_div) ** (1 / n_years) - 1) * 100

    # --- Step 3: PE Ratio and Lynch Score ---
    pe_ratio = stock_price / end_eps if end_eps != 0 else 0
    lynch_score = (eps_cagr + div_cagr) / pe_ratio if pe_ratio != 0 else 0
    lynch_fair_value = end_eps * (eps_cagr + div_cagr) / 100  # Normalize percentage to decimal

    # --- Logging ---
    logging.info(f"EPS CAGR       : {eps_cagr:.2f}%")
    logging.info(f"Dividend CAGR  : {div_cagr:.2f}%")
    logging.info(f"PE Ratio       : {pe_ratio:.2f}")
    logging.info(f"Lynch Score    : {lynch_score:.2f}")
    logging.info(f"Lynch Last EPS : Rs.{end_eps:.2f}")
    logging.info(f"Lynch Fair Value: Rs.{lynch_fair_value:.2f}")

    # Return updated state
    return {**state, "lynch_score": lynch_score, "lynch_fair_value": lynch_fair_value}

def classify_with_llm(state: FinancialState) -> FinancialState:

    try: 
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

        llm = ChatOllama(model="deepseek-r1:8b")
        
        ratios = state["ratios"]
        prompt = f"""
        Based on the following data, classify the stock using Peter Lynch's six categories:        
        Market Cap: {ratios["marketCap"]}
        EPS History: {ratios['eps_history']}
        Book Value: {ratios['book_value']}
        Current Price: {ratios['price']}
        Growth Rate: {ratios['revenue_growths']}

        Categories:
        - Slow Grower
        - Stalwart
        - Fast Grower
        - Cyclical
        - Turnaround
        - Asset Play

        Respond with just the best-fit category.
        """

        logging.info("Invoking LLM with prompt: %s", prompt)

        result = llm.invoke(prompt)

        logging.info("LLM Response: %s", result.content.strip())

        
        return {**state, "category": result.content.strip()}

    except ValueError as ve:
        # Log validation errors
        logging.error("Validation Error: %s", str(ve))
        raise  # Re-raise the exception after logging

    except Exception as e:
        # Log unexpected errors
        logging.error("An error occurred while classifying the stock: %s", str(e), exc_info=True)
        
        raise


def qualitative_lynch_node(state: FinancialState) -> FinancialState:
    """
    Performs qualitative Peter Lynch Tenbagger analysis on a company.
    Expects 'company_name', 'sector', 'description', and 'ratios' with 'marketCap'.
    """
    try:
        company = state.get("company_name", "")
        sector = state.get("sector", "")
        market_cap = state.get("ratios", {}).get("marketCap", None)
        description = state.get("description", "")

        logging.info(f"All value is set in qualitative_lynch_node")

        if market_cap is None:
            raise KeyError("ratios.marketCap is missing or null")

        prompt = f"""
        You are an investment analyst evaluating companies using Peter Lynch's Tenbagger criteria.

        Analyze the following:
        - Company: {company}
        - Sector: {sector}
        - Market Cap: {market_cap} RS
        - Description: {description}

        Please answer the following:
        1. Is this a small or lesser-known company (market cap < 2000 crore)? Return as true/false.
        2. Is the business considered "boring" (e.g., dull but essential)? Return as true/false.
        3. Does it operate in a niche or emerging industry? Return as true/false.
        4. Finally, summarize whether it's a good candidate for Tenbagger potential, with a short reason.

        Return your answer in **strict JSON** format as:
        {{
            "is_small_cap": true/false,
            "is_boring": true/false,
            "is_niche": true/false,
            "tenbagger_potential_reason": "..."
        }}
        """

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
        llm = ChatOllama(model="deepseek-r1:8b")
        logging.info(f"Invoking LLM with prompt:\n{prompt}")
        response = llm.invoke([HumanMessage(content=prompt)])
        raw_response = response.content.strip()
        logging.info(f"LLM Response: {raw_response}")

        # Strip markdown-style triple backticks and optional "json" tag
        cleaned_response = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_response, flags=re.MULTILINE).strip()

        try:
            analysis = json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM response is not valid JSON. Error: {e}")

        return {**state, "qualitative_lynch_analysis": analysis}

    except KeyError as e:
        logging.error(f"KeyError: {e}")
        return {**state, "error": f"Missing key: {e}"}

    except ValueError as e:
        logging.error(f"ValueError: {e}")
        return {**state, "error": str(e)}

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return {**state, "error": f"Unexpected error: {e}"}
    

# ─────────────────────────────────────────────────────────────
# LangGraph Graph Builder
# ─────────────────────────────────────────────────────────────


def build_financial_graph(use_session: bool = False):
    #node_fn = financial_data_node_session if use_session else financial_data_node
    node_fn = financial_data_node
    graph = StateGraph(FinancialState)
    graph.add_node("fetch_financial_data", financial_data_node_async)
    graph.add_node("valuation_collection", valuation_collection)
    graph.add_node("classify_with_llm", classify_with_llm)
    graph.add_node("qualitative_lynch_node", qualitative_lynch_node)

    graph.set_entry_point("fetch_financial_data")
    graph.add_edge("fetch_financial_data", "valuation_collection")
    graph.add_edge("valuation_collection", "classify_with_llm")
    graph.add_edge("classify_with_llm", "qualitative_lynch_node")
    graph.add_edge("qualitative_lynch_node", END)
    return graph.compile()


# ─────────────────────────────────────────────────────────────
# Run Example
# ─────────────────────────────────────────────────────────────

async def main():
    ticker = "DEEPAKFERT"
    app = build_financial_graph()
    result = await app.ainvoke({"ticker": ticker,"company_name": "Deepak Frtlsrs and Ptrchmcls Corp Ltd","sector": "Fertilizers / Chemicals"})

    print("Ratios:")
    print(json.dumps(result.get("ratios"), indent=2, default=str))
    print("\nLynch Metrics:")
    print(f"  lynch_score: {result.get('lynch_score')}")
    print(f"  lynch_fair_value: {result.get('lynch_fair_value')}")
    print(f"  category: {result.get('category')}")
    print(f"  qualitative_lynch_analysis: {result.get('qualitative_lynch_analysis')}")

    print(result)


if __name__ == "__main__":
    asyncio.run(main())
