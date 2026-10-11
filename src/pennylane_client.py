"""Client pour l'API Pennylane (ou, ici, son simulateur local). Pousse une
facture approuvée vers la compta, pour que le virement réel soit géré par
l'outil comptable, pas par notre agent lui même.
"""

import datetime

import requests

from mock_data import PENNYLANE_LEDGER_ACCOUNT_ID, PENNYLANE_SUPPLIER_IDS

BASE_URL = "http://127.0.0.1:8800"
TOKEN = "sandbox-token-alder-kitchens"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def pousser_facture_approuvee(fournisseur: str, montant_total: float, numero_bon_commande: str) -> int:
    """Pousse une facture approuvée vers Pennylane. Retourne l'id de la facture créée."""
    supplier_id = PENNYLANE_SUPPLIER_IDS.get(fournisseur)
    if supplier_id is None:
        raise ValueError(f"Pas de supplier_id Pennylane connu pour '{fournisseur}'.")

    # Pas de pièce jointe réelle dans ce projet (pas de PDF/image systématiquement
    # disponible à ce stade du graphe) : on simule quand même l'upload requis par
    # l'API pour respecter le vrai flux en deux temps.
    reponse_fichier = requests.post(f"{BASE_URL}/api/external/v2/file_attachments", headers=HEADERS)
    reponse_fichier.raise_for_status()
    file_attachment_id = reponse_fichier.json()["id"]

    aujourdhui = datetime.date.today().isoformat()
    echeance = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    montant = f"{montant_total:.2f}"

    payload = {
        "file_attachment_id": file_attachment_id,
        "supplier_id": supplier_id,
        "date": aujourdhui,
        "deadline": echeance,
        "currency_amount_before_tax": montant,
        "currency_tax": "0.00",
        "currency_amount": montant,
        "invoice_lines": [
            {
                "ledger_account_id": PENNYLANE_LEDGER_ACCOUNT_ID,
                "currency_amount": montant,
                "currency_tax": "0.00",
                "vat_rate": "FR_0",
            }
        ],
    }
    reponse = requests.post(f"{BASE_URL}/api/external/v2/supplier_invoices/import", json=payload, headers=HEADERS)
    reponse.raise_for_status()
    return reponse.json()["id"]
