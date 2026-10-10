"""LangGraph HITL approval. DB proposals remain authoritative and durable across process restarts."""
from __future__ import annotations
from typing import TypedDict

try:
    from langgraph.graph import StateGraph, START, END
    from langgraph.types import Command, interrupt
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:
    StateGraph=START=END=Command=interrupt=InMemorySaver=None

class ApprovalState(TypedDict):
    proposal_id: str
    summary: str
    approved: bool | None


def ask_human(state:ApprovalState):
    answer=interrupt({"proposal_id":state["proposal_id"],"summary":state["summary"],"question":"Approve these actions?"})
    return {"approved":bool(answer)}


def build_graph():
    if StateGraph is None: return None
    builder=StateGraph(ApprovalState)
    builder.add_node("human_review",ask_human)
    builder.add_edge(START,"human_review")
    builder.add_edge("human_review",END)
    return builder.compile(checkpointer=InMemorySaver())

_graph=build_graph()

def pause(proposal_id:str,summary:str):
    if _graph is None: return "db-approval-only"
    _graph.invoke({"proposal_id":proposal_id,"summary":summary,"approved":None},
                  config={"configurable":{"thread_id":proposal_id}})
    return "langgraph-interrupted"

def resume(proposal_id:str,summary:str,approved:bool):
    if _graph is None: return approved
    config={"configurable":{"thread_id":proposal_id}}
    checkpoint=_graph.get_state(config)
    if not checkpoint.values:
        pause(proposal_id,summary) # Recreate interrupted state after restart.
    output=_graph.invoke(Command(resume=approved),config=config)
    return output.get("approved") is approved
