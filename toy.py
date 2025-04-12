from bdi import BDI, Belief, BeliefSet
from datetime import datetime
from typing import Dict, Any
import asyncio
from dataclasses import dataclass
import random
from pydantic_ai.tools import RunContext


async def main():
    """Example of a smart home temperature control BDI agent."""

    # Create the agent
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

    @dataclass
    class Temperature:
        value: float
        unit: str = "C"

    class TemperatureDatabase:
        @classmethod
        def get_current_temperature(cls) -> Temperature:
            value = random.randint(15, 30)
            print(f"DEBUG: Generated random temperature: {value}")
            return Temperature(value)

        @classmethod
        def check_heating_system(cls) -> Dict[str, Any]:
            return {"status": "operational", "efficiency": 0.85}

        @classmethod
        def check_cooling_system(cls) -> Dict[str, Any]:
            return {"status": "operational", "efficiency": 0.9}

        @classmethod
        def adjust_hvac(cls, mode: str, target_temp: float) -> Dict[str, Any]:
            return {
                "success": True,
                "mode": mode,
                "target_temperature": target_temp,
                "estimated_time_minutes": 5,
            }

    # Register handlers using the new decorators
    @agent.perception_handler
    async def temperature_handler(data: Temperature, beliefs: BeliefSet) -> None:
        """Define perception handler for temperature"""
        print(f"DEBUG: Data received in temperature_handler: {data}")
        beliefs.add(
            Belief(
                name="room_temperature",
                value=data,
                source="temperature_sensor",
                timestamp=datetime.now().timestamp(),
            )
        )

    @agent.bdi_tool(
        name="fetch_temperature",
        description="Fetch current temperature from sensors",
        phases=["perception", "intention"],
        result_type=Temperature,
    )
    async def fetch_temperature(ctx: RunContext[TemperatureDatabase]) -> Temperature:
        """Fetch the current temperature from the temperature database."""
        temp = ctx.deps.get_current_temperature()
        return temp

    @agent.bdi_tool(
        name="check_heating_system",
        description="Check if the heating system is operational",
        phases=["desire", "intention"],
        result_type=dict,
    )
    async def check_heating_system(
        ctx: RunContext[TemperatureDatabase],
    ) -> Dict[str, Any]:
        """Check the status of the heating system."""
        status = ctx.deps.check_heating_system()
        return status

    @agent.bdi_tool(
        name="check_cooling_system",
        description="Check if the cooling system is operational",
        phases=["desire", "intention"],
        result_type=dict,
    )
    async def check_cooling_system(
        ctx: RunContext[TemperatureDatabase],
    ) -> Dict[str, Any]:
        """Check the status of the cooling system."""
        status = ctx.deps.check_cooling_system()
        return status

    @agent.bdi_tool(
        name="calculate_temp_adjustment",
        description="Calculate the required temperature adjustment",
        phases=["intention"],
        result_type=dict,
    )
    async def calculate_temp_adjustment(
        ctx: RunContext[TemperatureDatabase],
        current_temp: float,
        target_temp: float,
        mode: str,
    ) -> Dict[str, Any]:
        """Calculate the temperature adjustment needed."""
        adjustment = abs(target_temp - current_temp)
        return {
            "current_temp": current_temp,
            "target_temp": target_temp,
            "adjustment": adjustment,
            "mode": mode,
        }

    @agent.bdi_tool(
        name="adjust_hvac",
        description="Adjust the HVAC system temperature",
        phases=["intention"],
        result_type=dict,
    )
    async def adjust_hvac(
        ctx: RunContext[TemperatureDatabase], mode: str, target_temp: float
    ) -> Dict[str, Any]:
        """Adjust the HVAC system to the target temperature."""
        result = ctx.deps.adjust_hvac(mode, target_temp)
        return result

    # Set up the agent
    agent.deps = TemperatureDatabase()

    # Run the BDI cycle
    await agent.bdi_cycle()


if __name__ == "__main__":
    asyncio.run(main())
