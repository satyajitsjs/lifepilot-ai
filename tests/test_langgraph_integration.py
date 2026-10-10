"""Real LangGraph interrupt/resume check, skipped when optional dep isn't installed."""
import pytest


def test_langgraph_interrupt_and_resume():
    pytest.importorskip("langgraph")
    from app.approval_graph import build_graph
    from langgraph.types import Command
    graph=build_graph()
    config={"configurable":{"thread_id":"integration-approval-1"}}
    result=graph.invoke({"proposal_id":"integration-approval-1","summary":"Test pending action","approved":None},config=config)
    assert "__interrupt__" in result
    resumed=graph.invoke(Command(resume=False),config=config)
    assert resumed["approved"] is False
