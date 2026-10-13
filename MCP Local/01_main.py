from fastmcp import FastMCP
import random


mcp=FastMCP()

@mcp.tool()
def roll_dice():
    ''' genrating random number form 1 to 6'''
    num=random.randint(1,6)
    return num


@mcp.tool()
def add(a,b):
    ''' Adding two number'''
    return a+b

if __name__ == "__main__":
    mcp.run()