import random
from fastmcp import FastMCP

mcp = FastMCP(name="Demo app")

@mcp.tool
def add(a:int, b:int)-> int : 
    """add two numbers"""
    return a+b

if __name__=="__main__": 
    mcp.run()
