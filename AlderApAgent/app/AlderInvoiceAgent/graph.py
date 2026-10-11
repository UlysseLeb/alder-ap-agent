"""Graphe LangGraph de validation de factures fournisseurs — Alder Kitchens.

Flux : extract_invoice -> validate_po -> score_risk -> (auto_approve | human_approval) -> notify

extract_invoice et score_risk sont des appels LLM (extraction de texte libre, puis
jugement sur des écarts qui ne sont pas toujours binaires — saisonnalité des produits
frais par exemple). validate_po est un calcul déterministe : comparer des quantités et
des prix à un bon de commande est un calcul exact, pas un jugement, donc pas délégué au LLM.

Le checkpointer n'est pas créé ici : c'est main.py qui le fournit à builder.compile(),
pour pouvoir le partager avec le reste de l'app AgentCore (cf. module-level checkpointer).
"""

from typing import Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from model.load import load_model
from mock_data import BONS_DE_COMMANDE, FACTURES_DEJA_TRAITEES, FOURNISSEURS_REFERENCES, SEUIL_MONTANT_ELEVE

model = load_model()


# --- Schémas structurés pour les sorties LLM ---


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


class EvaluationRisque(BaseModel):
    risque: Literal["faible", "eleve"]
    justification: str = Field(description="Explication courte de la décision, en français")


# --- État du graphe ---


class InvoiceState(TypedDict):
    raw_text: str
    extraction: Optional[dict]  # dict (pas FactureExtraite) : le checkpointer sérialise le state en msgpack
    ecarts: list[str]
    risque: Optional[str]
    justification_risque: Optional[str]
    decision_finale: Optional[str]
    commentaire_humain: Optional[str]


# --- Nœuds ---


def extract_invoice(state: InvoiceState) -> dict:
    llm = model.with_structured_output(FactureExtraite)
    extraction: FactureExtraite = llm.invoke(
        "Extrait les données structurées de cette facture fournisseur. "
        "Le numéro de bon de commande est toujours au format BC-AAAA-NNNN.\n\n"
        f"Facture :\n{state['raw_text']}"
    )
    return {"extraction": extraction.model_dump()}


def validate_po(state: InvoiceState) -> dict:
    extraction = FactureExtraite(**state["extraction"])
    ecarts: list[str] = []

    if extraction.numero_bon_commande in FACTURES_DEJA_TRAITEES:
        ecarts.append(
            f"Facture en double : le bon de commande {extraction.numero_bon_commande} "
            "a déjà fait l'objet d'une facture traitée."
        )

    bon = BONS_DE_COMMANDE.get(extraction.numero_bon_commande)
    if bon is None:
        ecarts.append(f"Bon de commande {extraction.numero_bon_commande} introuvable dans l'ERP.")
        return {"ecarts": ecarts}

    fournisseurs_ok = FOURNISSEURS_REFERENCES.get(extraction.restaurant, set())
    if extraction.fournisseur not in fournisseurs_ok:
        ecarts.append(
            f"Fournisseur '{extraction.fournisseur}' non référencé pour {extraction.restaurant}."
        )
    elif extraction.fournisseur != bon["fournisseur"]:
        ecarts.append(
            f"Le bon de commande {extraction.numero_bon_commande} a été émis pour "
            f"'{bon['fournisseur']}', pas pour '{extraction.fournisseur}'."
        )

    lignes_bon = {ligne["produit"]: ligne for ligne in bon["lignes"]}
    for ligne in extraction.lignes:
        ligne_bon = lignes_bon.get(ligne.produit)
        if ligne_bon is None:
            ecarts.append(f"Produit '{ligne.produit}' absent du bon de commande.")
            continue
        if abs(ligne.quantite - ligne_bon["quantite"]) / ligne_bon["quantite"] > 0.10:
            ecarts.append(
                f"Écart de quantité sur '{ligne.produit}' : {ligne.quantite} {ligne.unite} "
                f"facturés vs {ligne_bon['quantite']} {ligne_bon['unite']} commandés."
            )
        if abs(ligne.prix_unitaire - ligne_bon["prix_unitaire"]) / ligne_bon["prix_unitaire"] > 0.15:
            ecarts.append(
                f"Écart de prix sur '{ligne.produit}' : {ligne.prix_unitaire}€/{ligne.unite} "
                f"facturé vs {ligne_bon['prix_unitaire']}€/{ligne.unite} au bon de commande."
            )

    if extraction.montant_total > SEUIL_MONTANT_ELEVE:
        ecarts.append(
            f"Montant total ({extraction.montant_total}€) au-dessus du seuil de "
            f"{SEUIL_MONTANT_ELEVE}€."
        )

    return {"ecarts": ecarts}


def score_risk(state: InvoiceState) -> dict:
    extraction = FactureExtraite(**state["extraction"])
    ecarts = state["ecarts"]

    if not ecarts:
        return {"risque": "faible", "justification_risque": "Aucun écart détecté avec le bon de commande."}

    llm = model.with_structured_output(EvaluationRisque)
    evaluation: EvaluationRisque = llm.invoke(
        "Tu évalues le risque d'une facture fournisseur pour une chaîne de restaurants avant paiement. "
        "Les écarts de prix sur les produits frais peuvent être légitimes (saisonnalité, cours des "
        "matières premières) : un léger écart de prix seul n'est pas forcément un risque élevé. "
        "En revanche, un fournisseur non référencé, un écart de quantité important, une facture en "
        "double, ou un montant très supérieur au seuil habituel sont des signaux sérieux.\n\n"
        f"Facture de {extraction.fournisseur} pour {extraction.restaurant}, "
        f"montant total {extraction.montant_total}€.\n"
        f"Écarts détectés :\n" + "\n".join(f"- {e}" for e in ecarts)
    )
    return {"risque": evaluation.risque, "justification_risque": evaluation.justification}


def route_risk(state: InvoiceState) -> Literal["auto_approve", "human_approval"]:
    return "auto_approve" if state["risque"] == "faible" else "human_approval"


def auto_approve(state: InvoiceState) -> dict:
    return {"decision_finale": "approuvée automatiquement"}


def human_approval(state: InvoiceState) -> dict:
    extraction = FactureExtraite(**state["extraction"])
    reponse = interrupt(
        {
            "question": "Facture à risque élevé : approuver ou rejeter ?",
            "fournisseur": extraction.fournisseur,
            "restaurant": extraction.restaurant,
            "montant_total": extraction.montant_total,
            "ecarts": state["ecarts"],
            "justification_risque": state["justification_risque"],
        }
    )
    decision = reponse.get("decision", "rejetée")
    commentaire = reponse.get("commentaire", "")
    return {
        "decision_finale": f"{decision} par validation humaine",
        "commentaire_humain": commentaire,
    }


def notify(state: InvoiceState) -> dict:
    print(
        f"[notify] {state['extraction']['numero_bon_commande']} : "
        f"{state['decision_finale']} (risque: {state['risque']})"
    )
    return {}


# --- Construction du graphe (non compilé : main.py fournit le checkpointer) ---

builder = StateGraph(InvoiceState)
builder.add_node("extract_invoice", extract_invoice)
builder.add_node("validate_po", validate_po)
builder.add_node("score_risk", score_risk)
builder.add_node("auto_approve", auto_approve)
builder.add_node("human_approval", human_approval)
builder.add_node("notify", notify)

builder.add_edge(START, "extract_invoice")
builder.add_edge("extract_invoice", "validate_po")
builder.add_edge("validate_po", "score_risk")
builder.add_conditional_edges("score_risk", route_risk, ["auto_approve", "human_approval"])
builder.add_edge("auto_approve", "notify")
builder.add_edge("human_approval", "notify")
builder.add_edge("notify", END)
