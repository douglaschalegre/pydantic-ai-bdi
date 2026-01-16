import asyncio
from pydantic_ai.mcp import MCPServerStdio
from antigravity import AntigravityModel, AntigravityProvider
from bdi import BDI
from dotenv import load_dotenv
import pathlib

load_dotenv()

# Create Antigravity provider and model
# First run will trigger OAuth flow to authenticate with Google
provider = AntigravityProvider()

# Choose your model - options include:
# Antigravity quota (shared, may hit rate limits faster):
# - "claude-sonnet-4-5": Claude Sonnet 4.5
# - "claude-sonnet-4-5-thinking": Claude Sonnet 4.5 with extended thinking
# - "claude-opus-4-5-thinking": Claude Opus 4.5 with extended thinking
# - "gemini-3-pro": Gemini 3 Pro
# - "gemini-3-pro-high": Gemini 3 Pro (high thinking)
# - "gemini-3-flash": Gemini 3 Flash
#
# Gemini CLI quota (separate quota pool, less likely to be rate limited):
# - "gemini-2.5-flash": Gemini 2.5 Flash (recommended for testing)
# - "gemini-2.5-pro": Gemini 2.5 Pro
model = AntigravityModel(
    "gemini-2.5-flash",  # Using Gemini 2.5 Flash (separate quota, less rate limiting)
    provider=provider,
)

git_server = MCPServerStdio(
    "uvx", args=["mcp-server-git"], tool_prefix="git", timeout=60
)
repo_path = str(pathlib.Path(__file__).parent.resolve())
fs = MCPServerStdio(
    "npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", repo_path],
    tool_prefix="fs",
    timeout=60,
)
MCP_SERVERS = [git_server, fs]

agent = BDI(
    model,
    desires=[
        "I need a report of the commit history of the pydantic-ai-bdi repository for a presentation. The repository path is /Users/douglas/code/masters/pydantic-ai-bdi"
    ],
    intentions=[
        "Check the commit history of the pydantic-ai-bdi repository",
        "Summarize the commit history",
        "Create a presentation of the commit history",
        "Summarize the latest advancements in the pydantic-ai-bdi repository",
    ],
    verbose=True,
    enable_human_in_the_loop=True,
    log_file_path="./bdi_agent_log.md",
    mcp_servers=MCP_SERVERS,
)


async def main():
    """Example BDI agent using an external MCP server for tools."""
    async with agent.run_mcp_servers():
        cycle = 0
        while True:
            cycle += 1
            print(f"\n===== Cycle {cycle} =====")
            status = await agent.bdi_cycle()
            if status in ["stopped", "interrupted"]:
                print(f"Agent cycle ended with status: {status}")
                break
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
