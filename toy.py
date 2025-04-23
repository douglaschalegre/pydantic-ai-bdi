from bdi import BDI
import asyncio


async def main():
    """Example BDI agent using an external MCP server for tools."""

    agent = BDI(
        "openai:gpt-4o",
        desires=["Keep the room temperature comfortably between 20°C and 24°C"],
        intentions=[
            "Maintain the room temperature within the target range (20°C-24°C).",
            "Activate heating immediately if the temperature falls below 20°C.",
            "Activate cooling immediately if the temperature rises above 24°C.",
            "Prioritize energy-efficient adjustments when activating HVAC.",
            "Regularly check HVAC system health to ensure reliable operation.",
        ],
    )

    for i in range(5):
        print(f"\n===== Cycle {i + 1} =====")
        await agent.bdi_cycle()
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
