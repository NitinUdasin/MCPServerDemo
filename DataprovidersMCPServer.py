"""
MCP Server for providing financial data from various data sources.
This server exposes tools to retrieve balance sheets, cash flows, profit and loss statements,
quarterly results, and stock ratios for specified ticker symbols.
"""

from fastmcp import FastMCP
from Dataprovider  import Dataproviders
import pandas as pd

# Initialize the MCP server with a descriptive name
mcp = FastMCP(name="Financial Data Provider")

# Initialize the data provider logic
dataprovider = Dataproviders()

@mcp.tool
def get_balancesheet(tickerName: str)->pd.DataFrame:
    """
    Retrieve the balance sheet for a given ticker symbol.
    
    Args:
        tickerName (str): The symbol of the company (e.g., 'AAPL', 'MSFT').
    """
    return dataprovider.get_balancesheet(tickerName)

@mcp.tool
def get_cashFlows(tickerName: str)->pd.DataFrame:
    """
    Retrieve the cash flow statement for a given ticker symbol.
    
    Args:
        tickerName (str): The symbol of the company.
    """
    return dataprovider.get_cashFlows(tickerName)

@mcp.tool
def get_profitLoss(tickerName: str)->pd.DataFrame:
    """
    Retrieve the profit and loss (income) statement for a given ticker symbol.
    
    Args:
        tickerName (str): The symbol of the company.
    """
    return dataprovider.get_profitLoss(tickerName)

@mcp.tool
def get_quarterlyresults(tickerName: str)->pd.DataFrame:
    """
    Retrieve the quarterly financial results for a given ticker symbol.
    
    Args:
        tickerName (str): The symbol of the company.
    """
    return dataprovider.get_quarterlyresults(tickerName)

@mcp.tool
def get_Ratio(tickerName: str):
    """
    Retrieve key stock ratios for a given ticker symbol.
    
    Args:
        tickerName (str): The symbol of the company.
    """
    return dataprovider.get_Ratio(tickerName)


if __name__ == "__main__": 
    # Start the MCP server
    mcp.run()