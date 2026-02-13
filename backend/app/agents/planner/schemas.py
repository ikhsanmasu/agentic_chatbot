from dataclasses import dataclass

DATABASE_ROUTE = "database"
GENERAL_ROUTE = "general"
VECTOR_ROUTE = "vector"
VALID_ROUTE_TARGETS = {DATABASE_ROUTE, GENERAL_ROUTE, VECTOR_ROUTE}


@dataclass
class RoutingDecision:
    target_agent: str
    reasoning: str
    routed_input: str

    @classmethod
    def from_payload(cls, payload: dict, fallback_input: str) -> "RoutingDecision":
        raw_target_agent = str(payload.get("agent", GENERAL_ROUTE)).strip().lower()
        target_agent = raw_target_agent if raw_target_agent in VALID_ROUTE_TARGETS else GENERAL_ROUTE

        reasoning = str(payload.get("reasoning", "")).strip()
        routed_input = str(
            payload.get("routed_input") or payload.get("rewritten_query") or fallback_input
        ).strip()

        return cls(
            target_agent=target_agent,
            reasoning=reasoning,
            routed_input=routed_input or fallback_input,
        )

    @property
    def agent(self) -> str:
        # Backward-compatible alias.
        return self.target_agent

    @property
    def rewritten_query(self) -> str:
        # Backward-compatible alias.
        return self.routed_input


# Backward-compatible alias for existing imports.
PlannerDecision = RoutingDecision
