"""Test rapide de l'entrypoint AgentCore, sans passer par le serveur de dev."""

import asyncio
from dataclasses import dataclass

from main import invoke


@dataclass
class FakeContext:
    session_id: str


async def main():
    # Cas 1 : risque faible, approbation automatique
    ctx1 = FakeContext(session_id="quick-test-1")
    result1 = await invoke({"raw_text": """
Facture n°F-8841 — Boucherie Fontaine
Destinataire : Alder Kitchens - Bastille
Bon de commande : BC-2026-0914
Lignes :
- Entrecôte de bœuf : 25 kg x 24,50€/kg
- Filet de poulet : 40 kg x 9,80€/kg
Montant total : 1004,50€
"""}, ctx1)
    print("Cas 1 (risque faible):", result1)

    # Cas 2 : risque élevé, interrompu puis repris avec une décision humaine
    ctx2 = FakeContext(session_id="quick-test-2")
    result2 = await invoke({"raw_text": """
Facture n°F-9012 — Nouveau Fournisseur Viandes SARL
Destinataire : Alder Kitchens - Lyon Part-Dieu
Bon de commande : BC-2026-0921
Lignes :
- Entrecôte de bœuf : 20 kg x 24,50€/kg
Montant total : 490,00€
"""}, ctx2)
    print("Cas 2 (premier appel, interrompu):", result2)

    result2_resume = await invoke(
        {"human_decision": {"decision": "rejetée", "commentaire": "test agentcore"}}, ctx2
    )
    print("Cas 2 (reprise):", result2_resume)


if __name__ == "__main__":
    asyncio.run(main())
