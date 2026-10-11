"""Partie 2 du test de persistance inter-process : nouveau process Python, reprend
l'exécution interrompue par test_persistence_part1.py en lisant l'état depuis le disque.
"""

from graph import graph
from langgraph.types import Command

config = {"configurable": {"thread_id": "test-persistance-inter-process"}}
result = graph.invoke(
    Command(resume={"decision": "rejetée", "commentaire": "test de persistance inter-process"}),
    config=config,
)

print(f"Reprise réussie depuis un nouveau process : décision finale = {result['decision_finale']}")
