"""Teste l'extraction d'une facture directement depuis une image (vision),
plutôt que depuis du texte tapé à la main. Script isolé pour valider le pattern
multimodal avant de l'intégrer dans extract_invoice (Phase 3).
"""

import base64
from pathlib import Path

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field


class LigneFacture(BaseModel):
    produit: str
    quantite: float
    unite: str
    prix_unitaire: float


class FactureExtraite(BaseModel):
    fournisseur: str
    restaurant: str = Field(description="Nom du restaurant Alder Kitchens destinataire")
    numero_bon_commande: str
    montant_total: float
    lignes: list[LigneFacture]


model = ChatBedrockConverse(
    model="eu.anthropic.claude-haiku-4-5-20251001-v1:0",
    region_name="eu-west-3",
    temperature=0,
)


def extraire_depuis_image(chemin_image: Path) -> FactureExtraite:
    image_b64 = base64.b64encode(chemin_image.read_bytes()).decode()
    message = HumanMessage(
        content=[
            {"type": "text", "text": "Extrait les données structurées de cette facture fournisseur. "
             "Le numéro de bon de commande est toujours au format BC-AAAA-NNNN."},
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": image_b64},
            },
        ]
    )
    llm = model.with_structured_output(FactureExtraite)
    return llm.invoke([message])


if __name__ == "__main__":
    for nom in ["facture_conforme.png", "facture_fournisseur_inconnu.png"]:
        chemin = Path(__file__).parent / "sample_invoices" / nom
        resultat = extraire_depuis_image(chemin)
        print(f"\n=== {nom} ===")
        print(resultat.model_dump_json(indent=2))
