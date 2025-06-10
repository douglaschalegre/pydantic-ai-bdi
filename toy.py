from pydantic_ai.mcp import MCPServerStdio
from bdi import BDI
import asyncio


async def main():
    """Example BDI agent using an external MCP server for tools."""
    git_server = MCPServerStdio(
        "uvx",
        args=["mcp-server-git"],
        tool_prefix="git",
    )
    agent = BDI(
        "openai:gpt-4o",
        desires=[
            "I need a report of the commit history of the pydantic-ai repository for a presentation"
        ],
        intentions=[
            "Check the commit history of the pydantic-ai repository",
            "Summarize the commit history",
            "Create a presentation of the commit history",
            "Summarize the latest advancements in the pydantic-ai repository",
        ],
        verbose=True,
        enable_human_in_the_loop=True,
        mcp_servers=[git_server],
    )

    for i in range(5):
        print(f"\n===== Cycle {i + 1} =====")
        await agent.bdi_cycle()
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
