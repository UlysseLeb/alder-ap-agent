"""Scénarios de test Phase 0 : routage conditionnel + interruption humaine en local.

Chaque cas pousse une facture texte libre dans le graphe. Si le risque est jugé
élevé, le graphe s'interrompt (interrupt()) et ce script simule la décision humaine
avant de reprendre l'exécution exactement où elle s'était arrêtée.
"""

from graph import graph
from langgraph.types import Command

CAS_DE_TEST = [
    {
        "nom": "Risque faible — facture conforme",
        "facture": """
Facture n°F-8841 — Boucherie Fontaine
Destinataire : Alder Kitchens - Bastille
Bon de commande : BC-2026-0914
Lignes :
- Entrecôte de bœuf : 25 kg x 24,50€/kg
- Filet de poulet : 40 kg x 9,80€/kg
Montant total : 1004,50€
""",
        "decision_humaine": None,
    },
    {
        "nom": "Risque élevé — fournisseur non référencé",
        "facture": """
Facture n°F-9012 — Nouveau Fournisseur Viandes SARL
Destinataire : Alder Kitchens - Lyon Part-Dieu
Bon de commande : BC-2026-0921
Lignes :
- Entrecôte de bœuf : 20 kg x 24,50€/kg
Montant total : 490,00€
""",
        "decision_humaine": {"decision": "rejetée", "commentaire": "Fournisseur jamais validé par le siège, à vérifier avant tout paiement."},
    },
    {
        "nom": "Risque élevé — écart de quantité et de prix",
        "facture": """
Facture n°F-9033 — Primeur Rhône
Destinataire : Alder Kitchens - Lyon Part-Dieu
Bon de commande : BC-2026-0920
Lignes :
- Tomates grappe : 45 kg x 4,80€/kg
- Salade batavia : 15 kg x 2,10€/kg
Montant total : 247,50€
""",
        "decision_humaine": {"decision": "approuvée", "commentaire": "Hausse de prix confirmée par le fournisseur (pénurie tomates), quantité en plus voulue pour l'événement du week-end."},
    },
    {
        "nom": "Risque élevé — facture en double",
        "facture": """
Facture n°F-9044 — Marée Express
Destinataire : Alder Kitchens - Bastille
Bon de commande : BC-2026-0915
Lignes :
- Filet de saumon : 18 kg x 19,90€/kg
- Crevettes roses : 10 kg x 22,00€/kg
Montant total : 578,20€
""",
        "decision_humaine": {"decision": "rejetée", "commentaire": "Déjà payée le mois dernier sous ce même bon de commande."},
    },
    {
        "nom": "Risque élevé — montant au-dessus du seuil malgré conformité",
        "facture": """
Facture n°F-9055 — Boucherie Fontaine
Destinataire : Alder Kitchens - Bastille
Bon de commande : BC-2026-0930
Lignes :
- Entrecôte de bœuf : 100 kg x 24,50€/kg
Montant total : 2450,00€
""",
        "decision_humaine": {"decision": "approuvée", "commentaire": "Commande confirmée pour l'événement traiteur du 30/09, volume inhabituel mais légitime."},
    },
]


def run_case(nom: str, facture: str, decision_humaine: dict | None, thread_id: str) -> None:
    print(f"\n=== {nom} ===")
    config = {"configurable": {"thread_id": thread_id}}

    result = graph.invoke({"raw_text": facture}, config=config)

    if "__interrupt__" in result:
        interruption = result["__interrupt__"][0]
        print(f"[interrupt] {interruption.value['question']}")
        print(f"  écarts : {interruption.value['ecarts']}")
        print(f"  justification risque : {interruption.value['justification_risque']}")
        assert decision_humaine is not None, "Ce cas devait être interrompu mais aucune décision humaine n'était prévue."
        result = graph.invoke(Command(resume=decision_humaine), config=config)
    else:
        assert decision_humaine is None, "Ce cas n'a pas été interrompu alors qu'une décision humaine était prévue."

    print(f"[résultat] risque={result['risque']} | décision={result['decision_finale']}")
    if result.get("ecarts"):
        for ecart in result["ecarts"]:
            print(f"  - {ecart}")


if __name__ == "__main__":
    for i, cas in enumerate(CAS_DE_TEST):
        run_case(cas["nom"], cas["facture"], cas["decision_humaine"], thread_id=f"cas-{i}")
