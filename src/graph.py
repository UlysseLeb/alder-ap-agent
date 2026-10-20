"""Graphe LangGraph de validation de factures fournisseurs — Alder Kitchens (Phase 0).

Flux : extract_invoice -> validate_po -> score_risk -> (auto_approve | human_approval) -> notify

extract_invoice et score_risk sont des appels LLM (extraction de texte libre, puis
jugement sur des écarts qui ne sont pas toujours binaires — saisonnalité des produits
frais par exemple). validate_po est un calcul déterministe : comparer des quantités et
des prix à un bon de commande est un calcul exact, pas un jugement, donc pas délégué au LLM.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional, TypedDict

from dotenv import load_dotenv

load_dotenv()  # charge LANGSMITH_TRACING / LANGSMITH_API_KEY / LANGSMITH_PROJECT depuis .env — tracing automatique, aucun autre code à toucher

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
checkpointer = SqliteSaver(conn)
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from mock_data import BONS_DE_COMMANDE, FACTURES_DEJA_TRAITEES, FOURNISSEURS_REFERENCES, SEUIL_MONTANT_ELEVE
from pennylane_client import pousser_facture_approuvee

MODEL_ID = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
REGION = "eu-west-3"

# Piste d'audit : un enregistrement append-only par facture traitée, jamais réécrit.
# Fichier local en Phase 0 (voir .gitignore) ; deviendra une vraie table en Phase 1.
AUDIT_LOG_PATH = Path(__file__).resolve().parent / "audit_log.jsonl"

# Garde-fou : factures = texte non fiable (n'importe quel fournisseur peut en écrire
# une). guardrail_config bloque les tentatives d'injection de prompt détectées en
# entrée (filtre PROMPT_ATTACK, testé avec 3 attaques distinctes, voir
# test_adversarial_injection*.py).
GUARDRAIL_ID = "97j0cwpultuj"
GUARDRAIL_VERSION = "1"

model = ChatBedrockConverse(
    model=MODEL_ID,
    region_name=REGION,
    temperature=0,
    guardrail_config={
        "guardrail_identifier": GUARDRAIL_ID,
        "guardrail_version": GUARDRAIL_VERSION,
        "trace": "enabled",
    },
)


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
    justification: str = Field(description="Short explanation of the decision, in English")


# --- État du graphe ---


class InvoiceState(TypedDict):
    raw_text: Optional[str]  # texte libre (ex: email) — exclusif avec image_base64
    image_base64: Optional[str]  # image de la facture (PNG/JPEG) encodée en base64 — exclusif avec raw_text
    extraction: Optional[dict]  # dict (pas FactureExtraite) : le checkpointer sérialise le state en msgpack
    ecarts: list[str]
    risque: Optional[str]
    justification_risque: Optional[str]
    decision_finale: Optional[str]
    commentaire_humain: Optional[str]
    pennylane_invoice_id: Optional[int]


# --- Nœuds ---


def extract_invoice(state: InvoiceState) -> dict:
    consigne = (
        "Extrait les données structurées de cette facture fournisseur. "
        "Le numéro de bon de commande est toujours au format BC-AAAA-NNNN."
    )
    if state.get("image_base64"):
        # Vraie facture (image), lue par vision plutôt que du texte tapé à la main.
        message = HumanMessage(
            content=[
                {"type": "text", "text": consigne},
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": state["image_base64"]},
                },
            ]
        )
        entree = [message]
    else:
        entree = f"{consigne}\n\nFacture :\n{state['raw_text']}"

    llm = model.with_structured_output(FactureExtraite)
    extraction: FactureExtraite = llm.invoke(entree)
    return {"extraction": extraction.model_dump()}


def validate_po(state: InvoiceState) -> dict:
    extraction = FactureExtraite(**state["extraction"])
    ecarts: list[str] = []

    if extraction.numero_bon_commande in FACTURES_DEJA_TRAITEES:
        ecarts.append(
            f"Duplicate invoice: purchase order {extraction.numero_bon_commande} "
            "has already been invoiced and processed."
        )

    bon = BONS_DE_COMMANDE.get(extraction.numero_bon_commande)
    if bon is None:
        ecarts.append(f"Purchase order {extraction.numero_bon_commande} not found in the ERP.")
        return {"ecarts": ecarts}

    fournisseurs_ok = FOURNISSEURS_REFERENCES.get(extraction.restaurant, set())
    if extraction.fournisseur not in fournisseurs_ok:
        ecarts.append(
            f"Supplier '{extraction.fournisseur}' is not on file for {extraction.restaurant}."
        )
    elif extraction.fournisseur != bon["fournisseur"]:
        ecarts.append(
            f"Purchase order {extraction.numero_bon_commande} was issued for "
            f"'{bon['fournisseur']}', not for '{extraction.fournisseur}'."
        )

    lignes_bon = {ligne["produit"]: ligne for ligne in bon["lignes"]}
    for ligne in extraction.lignes:
        ligne_bon = lignes_bon.get(ligne.produit)
        if ligne_bon is None:
            ecarts.append(f"Product '{ligne.produit}' is not on the purchase order.")
            continue
        if abs(ligne.quantite - ligne_bon["quantite"]) / ligne_bon["quantite"] > 0.10:
            ecarts.append(
                f"Quantity discrepancy on '{ligne.produit}': {ligne.quantite} {ligne.unite} "
                f"invoiced vs {ligne_bon['quantite']} {ligne_bon['unite']} ordered."
            )
        if abs(ligne.prix_unitaire - ligne_bon["prix_unitaire"]) / ligne_bon["prix_unitaire"] > 0.15:
            ecarts.append(
                f"Price discrepancy on '{ligne.produit}': €{ligne.prix_unitaire}/{ligne.unite} "
                f"invoiced vs €{ligne_bon['prix_unitaire']}/{ligne.unite} on the purchase order."
            )

    if extraction.montant_total > SEUIL_MONTANT_ELEVE:
        ecarts.append(
            f"Total amount (€{extraction.montant_total}) above the threshold of "
            f"€{SEUIL_MONTANT_ELEVE}."
        )

    return {"ecarts": ecarts}


def score_risk(state: InvoiceState) -> dict:
    extraction = FactureExtraite(**state["extraction"])
    ecarts = state["ecarts"]

    if not ecarts:
        return {"risque": "faible", "justification_risque": "No discrepancy found against the purchase order."}

    llm = model.with_structured_output(EvaluationRisque)
    evaluation: EvaluationRisque = llm.invoke(
        "You assess the risk of a supplier invoice for a restaurant chain before payment. "
        "Price discrepancies on fresh products can be legitimate (seasonality, raw material "
        "prices): a small price discrepancy alone is not necessarily high risk. On the other "
        "hand, an unlisted supplier, a large quantity discrepancy, a duplicate invoice, or an "
        "amount far above the usual threshold are serious signals.\n\n"
        f"Invoice from {extraction.fournisseur} for {extraction.restaurant}, "
        f"total amount €{extraction.montant_total}.\n"
        f"Discrepancies detected:\n" + "\n".join(f"- {e}" for e in ecarts)
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


def push_to_pennylane(state: InvoiceState) -> dict:
    # Seules les factures approuvées (auto ou humaine) partent en compta.
    # Une facture rejetée n'a rien à faire dans Pennylane.
    if "approuvée" not in state["decision_finale"]:
        return {}
    extraction = FactureExtraite(**state["extraction"])
    id_facture = pousser_facture_approuvee(
        fournisseur=extraction.fournisseur,
        montant_total=extraction.montant_total,
        numero_bon_commande=extraction.numero_bon_commande,
    )
    return {"pennylane_invoice_id": id_facture}


def notify(state: InvoiceState) -> dict:
    pennylane_id = state.get("pennylane_invoice_id")
    suffixe = f" | Pennylane #{pennylane_id}" if pennylane_id else ""
    print(
        f"[notify] {state['extraction']['numero_bon_commande']} — "
        f"{state['decision_finale']} (risque: {state['risque']}){suffixe}"
    )
    _enregistrer_piste_audit(state, pennylane_id)
    return {}


def _enregistrer_piste_audit(state: InvoiceState, pennylane_id: Optional[int]) -> None:
    """Ajoute une ligne à audit_log.jsonl : la trace de la décision prise par l'agent sur
    cette facture, indépendante du print (lisible par un humain) et du log applicatif —
    pensée pour être relue plus tard, pas seulement observée en direct."""
    extraction = state["extraction"]
    enregistrement = {
        "horodatage": datetime.now(timezone.utc).isoformat(),
        "numero_bon_commande": extraction["numero_bon_commande"],
        "fournisseur": extraction["fournisseur"],
        "restaurant": extraction["restaurant"],
        "montant_total": extraction["montant_total"],
        "ecarts": state["ecarts"],
        "risque": state["risque"],
        "justification_risque": state["justification_risque"],
        "decision_finale": state["decision_finale"],
        "commentaire_humain": state.get("commentaire_humain"),
        "pennylane_invoice_id": pennylane_id,
    }
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(enregistrement, ensure_ascii=False) + "\n")


# --- Construction du graphe ---

builder = StateGraph(InvoiceState)
builder.add_node("extract_invoice", extract_invoice)
builder.add_node("validate_po", validate_po)
builder.add_node("score_risk", score_risk)
builder.add_node("auto_approve", auto_approve)
builder.add_node("human_approval", human_approval)
builder.add_node("push_to_pennylane", push_to_pennylane)
builder.add_node("notify", notify)

builder.add_edge(START, "extract_invoice")
builder.add_edge("extract_invoice", "validate_po")
builder.add_edge("validate_po", "score_risk")
builder.add_conditional_edges("score_risk", route_risk, ["auto_approve", "human_approval"])
builder.add_edge("auto_approve", "push_to_pennylane")
builder.add_edge("human_approval", "push_to_pennylane")
builder.add_edge("push_to_pennylane", "notify")
builder.add_edge("notify", END)

graph = builder.compile(checkpointer=checkpointer)
