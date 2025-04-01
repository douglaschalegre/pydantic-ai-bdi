from bdi import BDI, Belief, BeliefSet, Desire, Intention, IntentionStep
from datetime import datetime
from typing import List, Dict, Any
import asyncio
from dataclasses import dataclass
import random
from pydantic_ai.tools import RunContext


async def main():
    """Example of a smart home temperature control BDI agent."""

    # Create the agent
    agent = BDI("openai:gpt-4o")

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

    @agent.desire_generator
    async def temperature_desire_generator(beliefs: BeliefSet) -> List[Desire]:
        """Define desire generator for temperature control"""
        temp_belief = beliefs.get("room_temperature")
        if temp_belief:
            temp: Temperature = temp_belief.value
            if temp.value <= 21:
                return [
                    Desire(
                        id="increase_temp",
                        description="Increase room temperature to comfortable level",
                        priority=0.8,
                        preconditions=["has_heating_control"],
                    )
                ]
            elif temp.value >= 23:
                return [
                    Desire(
                        id="decrease_temp",
                        description="Decrease room temperature to comfortable level",
                        priority=0.8,
                        preconditions=["has_cooling_control"],
                    )
                ]
        return []

    @agent.intention_selector
    async def temperature_intention_selector(
        desires: List[Desire], beliefs: BeliefSet
    ) -> List[Intention]:
        """Define intention selector for temperature adjustment"""
        intentions = []
        for desire in desires:
            if desire.id == "increase_temp":
                current_temp: Temperature = beliefs.get("room_temperature").value
                intentions.append(
                    Intention(
                        desire_id=desire.id,
                        steps=[
                            IntentionStep(
                                description="Check heating system status",
                                tool_name="check_heating_system",
                                tool_params={},
                            ),
                            IntentionStep(
                                description="Calculate required temperature adjustment",
                                tool_name="calculate_temp_adjustment",
                                tool_params={
                                    "current_temp": current_temp.value,
                                    "target_temp": 22.0,
                                    "mode": "heating",
                                },
                            ),
                            IntentionStep(
                                description="Adjust heating system",
                                tool_name="adjust_hvac",
                                tool_params={"mode": "heating", "target_temp": 22.0},
                            ),
                        ],
                    )
                )
            elif desire.id == "decrease_temp":
                current_temp: Temperature = beliefs.get("room_temperature").value
                intentions.append(
                    Intention(
                        desire_id=desire.id,
                        steps=[
                            IntentionStep(
                                description="Check cooling system status",
                                tool_name="check_cooling_system",
                                tool_params={},
                            ),
                            IntentionStep(
                                description="Calculate required temperature adjustment",
                                tool_name="calculate_temp_adjustment",
                                tool_params={
                                    "current_temp": current_temp.value,
                                    "target_temp": 22.0,
                                    "mode": "cooling",
                                },
                            ),
                            IntentionStep(
                                description="Adjust cooling system",
                                tool_name="adjust_hvac",
                                tool_params={"mode": "cooling", "target_temp": 22.0},
                            ),
                        ],
                    )
                )
        return intentions

    @agent.bdi_tool(
        name="fetch_temperature",
        description="Fetch current temperature from sensors",
        phases=["perception"],
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
    await agent.bdi_cycle()


if __name__ == "__main__":
    asyncio.run(main())
