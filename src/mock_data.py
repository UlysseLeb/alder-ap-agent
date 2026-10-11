"""Données mockées : ERP de Alder Kitchens (bons de commande + fournisseurs référencés).

En Phase 0, ces données remplacent un vrai ERP. Elles seront exposées via
AWS Bedrock AgentCore Gateway en Phase 1.
"""

FOURNISSEURS_REFERENCES = {
    "Alder Kitchens - Bastille": {
        "Boucherie Fontaine",
        "Marée Express",
        "Primeur du Marais",
        "Brasseries Distrib",
    },
    "Alder Kitchens - Lyon Part-Dieu": {
        "Boucherie Fontaine",
        "Poissonnerie du Lac",
        "Primeur Rhône",
        "Brasseries Distrib",
    },
}

BONS_DE_COMMANDE = {
    "BC-2026-0914": {
        "restaurant": "Alder Kitchens - Bastille",
        "fournisseur": "Boucherie Fontaine",
        "date": "2026-09-14",
        "lignes": [
            {"produit": "Entrecôte de bœuf", "quantite": 25, "unite": "kg", "prix_unitaire": 24.50},
            {"produit": "Filet de poulet", "quantite": 40, "unite": "kg", "prix_unitaire": 9.80},
        ],
    },
    "BC-2026-0915": {
        "restaurant": "Alder Kitchens - Bastille",
        "fournisseur": "Marée Express",
        "date": "2026-09-15",
        "lignes": [
            {"produit": "Filet de saumon", "quantite": 18, "unite": "kg", "prix_unitaire": 19.90},
            {"produit": "Crevettes roses", "quantite": 10, "unite": "kg", "prix_unitaire": 22.00},
        ],
    },
    "BC-2026-0920": {
        "restaurant": "Alder Kitchens - Lyon Part-Dieu",
        "fournisseur": "Primeur Rhône",
        "date": "2026-09-20",
        "lignes": [
            {"produit": "Tomates grappe", "quantite": 30, "unite": "kg", "prix_unitaire": 3.20},
            {"produit": "Salade batavia", "quantite": 15, "unite": "kg", "prix_unitaire": 2.10},
        ],
    },
    "BC-2026-0921": {
        "restaurant": "Alder Kitchens - Lyon Part-Dieu",
        "fournisseur": "Boucherie Fontaine",
        "date": "2026-09-21",
        "lignes": [
            {"produit": "Entrecôte de bœuf", "quantite": 20, "unite": "kg", "prix_unitaire": 24.50},
        ],
    },
    "BC-2026-0930": {
        "restaurant": "Alder Kitchens - Bastille",
        "fournisseur": "Boucherie Fontaine",
        "date": "2026-09-30",
        "lignes": [
            {"produit": "Entrecôte de bœuf", "quantite": 100, "unite": "kg", "prix_unitaire": 24.50},
        ],
    },
}

# Seuil de montant total au-dessus duquel une facture est jugée potentiellement risquée,
# même si elle correspond parfaitement à son bon de commande.
SEUIL_MONTANT_ELEVE = 1500.0

# Numéros de bons de commande déjà rattachés à une facture traitée (pour détecter les doublons).
FACTURES_DEJA_TRAITEES = {"BC-2026-0915"}

# Mapping fournisseur -> supplier_id côté Pennylane (fictif, pour simuler l'API).
PENNYLANE_SUPPLIER_IDS = {
    "Boucherie Fontaine": 98001,
    "Marée Express": 98002,
    "Primeur du Marais": 98003,
    "Brasseries Distrib": 98004,
    "Poissonnerie du Lac": 98005,
    "Primeur Rhône": 98006,
}

# Compte comptable générique "achats de marchandises" côté Pennylane (fictif).
PENNYLANE_LEDGER_ACCOUNT_ID = 601002
