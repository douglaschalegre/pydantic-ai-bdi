import os
import asyncio
from pydantic_ai.mcp import MCPServerStdio

# from pydantic_ai.models.openai import OpenAIChatModel
# from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from bdi import BDI
from dotenv import load_dotenv

load_dotenv()

# model = OpenAIChatModel(
#     "gemma3:1b", provider=OllamaProvider(base_url=os.getenv("OLLAMA_BASE_URL"))
# )
model = GroqModel(
    "llama-3.1-8b-instant", provider=GroqProvider(api_key=os.getenv("PROVIDER_API_KEY"))
)
git_server = MCPServerStdio(
    "uvx", args=["mcp-server-git"], tool_prefix="git", timeout=60
)

agent = BDI(
    model,
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


async def main():
    """Example BDI agent using an external MCP server for tools."""
    async with agent.run_mcp_servers():
        for i in range(5):
            print(f"\n===== Cycle {i + 1} =====")
            await agent.bdi_cycle()
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
