"""Rejoue les 5 cas de test de Phase 0 contre le vrai agent déployé sur AgentCore
Runtime, pour générer de vraies traces à évaluer (Phase 2).
"""

import uuid

from invoke_remote import call

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
        "nom": "Risque élevé — montant au-dessus du seuil",
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

if __name__ == "__main__":
    for cas in CAS_DE_TEST:
        session_id = str(uuid.uuid4())
        print(f"\n=== {cas['nom']} (session {session_id}) ===")
        result = call({"raw_text": cas["facture"]}, session_id)
        print("  premier appel :", result.get("status"))

        if cas["decision_humaine"] is not None:
            assert result.get("status") == "pending_human_approval", "Ce cas devait s'interrompre."
            result = call({"human_decision": cas["decision_humaine"]}, session_id)
            print("  reprise :", result)
        else:
            assert result.get("status") == "done", "Ce cas ne devait pas s'interrompre."
            print("  résultat :", result)
