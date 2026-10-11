"""Génère de vraies images de facture (PNG), pour tester l'extraction par vision
plutôt que du texte tapé à la main (Phase 3 : vraie extraction de facture).
"""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).parent / "sample_invoices"
OUT_DIR.mkdir(exist_ok=True)


@dataclass
class LigneFacture:
    produit: str
    quantite: float
    unite: str
    prix_unitaire: float

    @property
    def total(self) -> float:
        return self.quantite * self.prix_unitaire


def dessiner_facture(
    nom_fichier: str,
    numero: str,
    fournisseur: str,
    restaurant: str,
    bon_de_commande: str,
    lignes: list[LigneFacture],
) -> None:
    largeur, hauteur = 900, 1100
    img = Image.new("RGB", (largeur, hauteur), "white")
    draw = ImageDraw.Draw(img)

    # Polices système, fallback sur la police par défaut si indisponible.
    try:
        police_titre = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
        police_normale = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
        police_petite = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except OSError:
        police_titre = police_normale = police_petite = ImageFont.load_default()

    y = 50
    draw.text((50, y), "FACTURE", font=police_titre, fill="black")
    draw.text((largeur - 250, y + 5), numero, font=police_normale, fill="black")
    y += 60
    draw.line([(50, y), (largeur - 50, y)], fill="black", width=2)
    y += 30

    draw.text((50, y), "Fournisseur", font=police_petite, fill="gray")
    y += 25
    draw.text((50, y), fournisseur, font=police_normale, fill="black")
    y += 45

    draw.text((50, y), "Destinataire", font=police_petite, fill="gray")
    y += 25
    draw.text((50, y), restaurant, font=police_normale, fill="black")
    y += 45

    draw.text((50, y), "Bon de commande", font=police_petite, fill="gray")
    y += 25
    draw.text((50, y), bon_de_commande, font=police_normale, fill="black")
    y += 60

    # Tableau des lignes.
    colonnes_x = [50, 420, 540, 660, 780]
    entetes = ["Produit", "Quantité", "Unité", "Prix unitaire", "Total"]
    for x, texte in zip(colonnes_x, entetes):
        draw.text((x, y), texte, font=police_petite, fill="gray")
    y += 30
    draw.line([(50, y), (largeur - 50, y)], fill="black", width=1)
    y += 15

    montant_total = 0.0
    for ligne in lignes:
        draw.text((colonnes_x[0], y), ligne.produit, font=police_normale, fill="black")
        draw.text((colonnes_x[1], y), f"{ligne.quantite:g}", font=police_normale, fill="black")
        draw.text((colonnes_x[2], y), ligne.unite, font=police_normale, fill="black")
        draw.text((colonnes_x[3], y), f"{ligne.prix_unitaire:.2f}€", font=police_normale, fill="black")
        draw.text((colonnes_x[4], y), f"{ligne.total:.2f}€", font=police_normale, fill="black")
        montant_total += ligne.total
        y += 35

    y += 20
    draw.line([(50, y), (largeur - 50, y)], fill="black", width=2)
    y += 20
    draw.text((colonnes_x[3], y), "Montant total", font=police_normale, fill="black")
    draw.text((colonnes_x[4], y), f"{montant_total:.2f}€", font=police_normale, fill="black")

    chemin = OUT_DIR / nom_fichier
    img.save(chemin)
    print(f"Généré : {chemin} (montant total calculé : {montant_total:.2f}€)")


if __name__ == "__main__":
    dessiner_facture(
        "facture_conforme.png",
        numero="F-8841",
        fournisseur="Boucherie Fontaine",
        restaurant="Alder Kitchens - Bastille",
        bon_de_commande="BC-2026-0914",
        lignes=[
            LigneFacture("Entrecôte de bœuf", 25, "kg", 24.50),
            LigneFacture("Filet de poulet", 40, "kg", 9.80),
        ],
    )

    dessiner_facture(
        "facture_fournisseur_inconnu.png",
        numero="F-9012",
        fournisseur="Nouveau Fournisseur Viandes SARL",
        restaurant="Alder Kitchens - Lyon Part-Dieu",
        bon_de_commande="BC-2026-0921",
        lignes=[
            LigneFacture("Entrecôte de bœuf", 20, "kg", 24.50),
        ],
    )
