import os
import asyncio
from pydantic_ai.mcp import MCPServerStdio

# from pydantic_ai.models.openai import OpenAIChatModel
# from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from bdi import BDI
from dotenv import load_dotenv
import pathlib

load_dotenv()

# model = OpenAIChatModel(
#     "gemma3:1b", provider=OllamaProvider(base_url=os.getenv("OLLAMA_BASE_URL"))
# )
model = GroqModel(
    "moonshotai/kimi-k2-instruct-0905",
    provider=GroqProvider(api_key=os.getenv("PROVIDER_API_KEY")),
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
        for i in range(5):
            print(f"\n===== Cycle {i + 1} =====")
            await agent.bdi_cycle()
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
