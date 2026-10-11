"""Simule l'API Pennylane (outil comptable réel) pour tester le pattern
d'intégration de bout en bout, sans vrai compte Pennylane (qui nécessite soit
un abonnement payant, soit un accès partenaire sur demande).

Schéma calqué sur la vraie doc Pennylane (endpoint, body, auth) :
https://pennylane.readme.io/docs/supplier-invoicing
"""

from dataclasses import dataclass, field

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Pennylane (simulé)")

FAKE_TOKEN = "sandbox-token-alder-kitchens"


@dataclass
class EtatPennylane:
    prochain_id_fichier: int = 1
    prochain_id_facture: int = 1
    factures: dict = field(default_factory=dict)


etat = EtatPennylane()


def _verifier_token(authorization: str | None) -> None:
    if authorization != f"Bearer {FAKE_TOKEN}":
        raise HTTPException(status_code=401, detail="Token invalide")


class LigneFactureAPI(BaseModel):
    ledger_account_id: int
    currency_amount: str
    currency_tax: str
    vat_rate: str


class FactureFournisseurAPI(BaseModel):
    file_attachment_id: int
    supplier_id: int
    date: str
    deadline: str
    currency_amount_before_tax: str
    currency_tax: str
    currency_amount: str
    invoice_lines: list[LigneFactureAPI]


@app.post("/api/external/v2/file_attachments")
def uploader_piece_jointe(authorization: str = Header(None)):
    _verifier_token(authorization)
    id_fichier = etat.prochain_id_fichier
    etat.prochain_id_fichier += 1
    return {"id": id_fichier}


@app.post("/api/external/v2/supplier_invoices/import")
def importer_facture(facture: FactureFournisseurAPI, authorization: str = Header(None)):
    _verifier_token(authorization)
    id_facture = etat.prochain_id_facture
    etat.prochain_id_facture += 1
    etat.factures[id_facture] = facture.model_dump()
    print(f"[pennylane simulé] facture #{id_facture} importée : {facture.model_dump_json()}")
    return {"id": id_facture, "status": "imported"}


@app.get("/api/external/v2/supplier_invoices/{id_facture}")
def lire_facture(id_facture: int, authorization: str = Header(None)):
    _verifier_token(authorization)
    if id_facture not in etat.factures:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    return etat.factures[id_facture]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8800)
