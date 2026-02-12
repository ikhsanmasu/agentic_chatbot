from app.agents.database import DatabaseAgent, create_database_agent
from app.agents.planner.agent import PlannerAgent
from app.core.llm import create_llm
from app.core.llm.base import BaseLLM


def create_planner_agent(
    llm: BaseLLM | None = None,
    database_agent: DatabaseAgent | None = None,
) -> PlannerAgent:
    planner_llm = llm or create_llm(config_group="llm_planner")
    planner_database_agent = database_agent or create_database_agent()
    return PlannerAgent(llm=planner_llm, database_agent=planner_database_agent)


__all__ = ["PlannerAgent", "create_planner_agent"]
