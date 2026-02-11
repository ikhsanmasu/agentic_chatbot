from dataclasses import dataclass


@dataclass
class PlannerDecision:
    agent: str  # "database" or "general"
    reasoning: str
    rewritten_query: str
