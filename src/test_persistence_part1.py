"""Partie 1 du test de persistance inter-process : déclenche une interruption, puis le script se termine.
Le process Python s'arrête complètement entre les deux scripts, comme une Lambda qui redémarre.
"""

from graph import graph

FACTURE = """
Facture n°F-9012 — Nouveau Fournisseur Viandes SARL
Destinataire : Alder Kitchens - Lyon Part-Dieu
Bon de commande : BC-2026-0921
Lignes :
- Entrecôte de bœuf : 20 kg x 24,50€/kg
Montant total : 490,00€
"""

config = {"configurable": {"thread_id": "test-persistance-inter-process"}}
result = graph.invoke({"raw_text": FACTURE}, config=config)

assert "__interrupt__" in result, "Ce cas devait s'interrompre."
print("Interruption déclenchée et sauvegardée sur disque. Le process va maintenant se terminer.")
print(f"  question : {result['__interrupt__'][0].value['question']}")
