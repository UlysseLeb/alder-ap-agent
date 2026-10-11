"""Teste le graphe complet avec une vraie image de facture en entrée,
au lieu du texte tapé à la main (Phase 3)."""

import base64
from pathlib import Path

from graph import graph
from langgraph.types import Command


def image_vers_base64(nom: str) -> str:
    chemin = Path(__file__).parent / "sample_invoices" / nom
    return base64.b64encode(chemin.read_bytes()).decode()


if __name__ == "__main__":
    # Cas 1 : facture conforme, image uniquement, pas de texte.
    config = {"configurable": {"thread_id": "vision-cas-1"}}
    result = graph.invoke({"image_base64": image_vers_base64("facture_conforme.png")}, config=config)
    print("=== facture_conforme.png ===")
    print(f"risque={result['risque']} | décision={result['decision_finale']}")

    # Cas 2 : fournisseur non référencé, image uniquement, doit s'interrompre.
    config = {"configurable": {"thread_id": "vision-cas-2"}}
    result = graph.invoke({"image_base64": image_vers_base64("facture_fournisseur_inconnu.png")}, config=config)
    print("\n=== facture_fournisseur_inconnu.png ===")
    assert "__interrupt__" in result, "Ce cas devait s'interrompre."
    print("interruption :", result["__interrupt__"][0].value["question"])
    result = graph.invoke(
        Command(resume={"decision": "rejetée", "commentaire": "test extraction vision"}), config=config
    )
    print(f"résultat après reprise : risque={result['risque']} | décision={result['decision_finale']}")
