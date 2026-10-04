# Alder AP Agent — conventions du projet

Projet d'apprentissage ciblé explicitement sur la stack la plus demandée en 2026 pour un poste Forward Deployed Engineer côté agents IA (recherche marché faite dans [[novasupply-agent]]) : LangGraph (framework d'orchestration dominant côté adoption enterprise, contrairement à Strands qui reste un choix AWS-natif de niche) et AWS Bedrock AgentCore (disponibilité générale depuis octobre 2025, la nouvelle couche managée de déploiement d'agents sur AWS — Runtime, Gateway, Memory, Observability, Evaluations — plutôt que de refaire du Lambda + API Gateway + CDK à la main comme sur NovaSupply).

Scénario : **Alder Freight**, une entreprise de transport fictive, reçoit des factures fournisseurs (carburant, maintenance, péages) à valider avant paiement. L'agent extrait les données de la facture, la compare au bon de commande, évalue le risque, et **interrompt le graphe pour une validation humaine** sur les cas à risque (montant au-dessus d'un seuil, fournisseur inconnu, écart avec le bon de commande) — contrairement à NovaSupply où l'agent décidait seul, ici on pratique explicitement le pattern human-in-the-loop (interrupt/resume LangGraph), identifié comme une vraie lacune du projet précédent.

Voir le brief complet : `docs/PROJECT.md`.

## Conventions

- Commentaires et docstrings en français, code (noms de variables/fonctions) en anglais — même convention que les autres projets freelance-clients.
- Avancer phase par phase (voir roadmap dans `docs/PROJECT.md`) : ne pas déployer sur AgentCore avant que le graphe LangGraph local (Phase 0) ait validé le routage et l'interruption humaine sur plusieurs cas de test.
- AgentCore est un service très récent (GA octobre 2025) : documenter les surprises et limitations rencontrées au fur et à mesure, ne pas supposer que la documentation/les tutoriels trouvés en ligne sont à jour.
- Ne pas committer `.env`, `cdk.out/`, ni aucune donnée de coûts/facturation réelle.
- Ne pas modifier le projet `novasupply-agent` existant : celui-ci est un projet séparé, pas une migration en place.
