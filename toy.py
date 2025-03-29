from bdi import BDI, Belief, BeliefSet, Desire, Intention
from datetime import datetime
from typing import List
import asyncio
from util import bcolors


async def main():
    """Example of a smart home temperature control BDI agent."""

    # Create the agent
    agent = BDI("openai:gpt-4")

    async def temperature_handler(data: dict, beliefs: BeliefSet) -> None:
        """Define perception handler for temperature"""
        if "temperature" in data:
            beliefs.add(
                Belief(
                    name="room_temperature",
                    value=data["temperature"],
                    source="temperature_sensor",
                    timestamp=datetime.now().timestamp(),
                )
            )

    async def temperature_desire_generator(beliefs: BeliefSet) -> List[Desire]:
        """Define desire generator for temperature control"""
        temp_belief = beliefs.get("room_temperature")
        if temp_belief:
            temp = temp_belief.value
            if temp < 20:
                return [
                    Desire(
                        id="increase_temp",
                        description="Increase room temperature to comfortable level",
                        priority=0.8,
                        preconditions=["has_heating_control"],
                    )
                ]
            elif temp > 24:
                return [
                    Desire(
                        id="decrease_temp",
                        description="Decrease room temperature to comfortable level",
                        priority=0.8,
                        preconditions=["has_cooling_control"],
                    )
                ]
        return []

    async def temperature_intention_selector(
        desires: List[Desire], beliefs: BeliefSet
    ) -> List[Intention]:
        """Define intention selector for temperature adjustment"""
        intentions = []
        for desire in desires:
            if desire.id == "increase_temp":
                intentions.append(
                    Intention(
                        desire_id=desire.id,
                        steps=[
                            "check_heating_system",
                            "calculate_temp_increase",
                            "adjust_heating",
                        ],
                    )
                )
            elif desire.id == "decrease_temp":
                intentions.append(
                    Intention(
                        desire_id=desire.id,
                        steps=[
                            "check_cooling_system",
                            "calculate_temp_decrease",
                            "adjust_cooling",
                        ],
                    )
                )
        return intentions

    # Register the handlers
    agent.register_perception_handler(temperature_handler)
    agent.register_desire_generator(temperature_desire_generator)
    agent.register_intention_selector(temperature_intention_selector)

    # Simulate temperature readings and run BDI cycles
    temperatures = [25.5, 19.5, 22.0]  # Sample temperature readings

    for temp in temperatures:
        print(f"\nProcessing temperature: {temp}°C")

        # Run a BDI cycle with the new temperature reading
        await agent.bdi_cycle({"temperature": temp})


if __name__ == "__main__":
    asyncio.run(main())
