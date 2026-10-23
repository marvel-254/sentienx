"""Command palette (port of OpenStock's SearchCommand + cmdk) for Streamlit.

Streamlit has no native Cmd+K overlay, so v1 is a search box plus an
action registry. The registry pattern keeps call sites stable if a
custom component upgrades the UX later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass(frozen=True)
class Action:
    id: str
    label: str
    keywords: tuple
    handler: Callable[[], None]
    hint: str = ""


class ActionRegistry:
    def __init__(self):
        self._actions: Dict[str, Action] = {}

    def register(self, action: Action) -> None:
        self._actions[action.id] = action

    def all(self) -> List[Action]:
        return list(self._actions.values())

    def search(self, query: str, limit: int = 8) -> List[Action]:
        """Rank actions by label/keyword match. Empty query returns all."""
        query = (query or "").strip().lower()
        if not query:
            return self.all()[:limit]
        scored = []
        for action in self._actions.values():
            haystacks = [action.label.lower()] + [k.lower() for k in action.keywords]
            best = -1
            for h in haystacks:
                if query in h:
                    best = max(best, 100 - h.find(query))
            if best >= 0:
                scored.append((best, action))
        scored.sort(key=lambda pair: -pair[0])
        return [a for _, a in scored[:limit]]

    def run(self, action_id: str) -> bool:
        action = self._actions.get(action_id)
        if not action:
            return False
        action.handler()
        return True


def render_streamlit(registry: ActionRegistry, key: str = "palette"):
    """Search box + result picker. Returns the selected Action, if any."""
    import streamlit as st

    query = st.text_input("Search symbols, pages, actions", "", key=key)
    results = registry.search(query)
    if not results:
        return None
    labels = {
        f"{a.label}{(' - ' + a.hint) if a.hint else ''}": a for a in results
    }
    choice = st.selectbox(
        "Results",
        list(labels.keys()),
        key=f"{key}-results",
        label_visibility="collapsed",
    )
    return labels.get(choice)
