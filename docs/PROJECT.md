# Alder AP Agent

Projet d'apprentissage ciblé sur la stack agents IA la plus demandée en 2026 pour un poste Forward Deployed Engineer : LangGraph + AWS Bedrock AgentCore. Scaffoldé le 2026-10-04, dans la continuité directe de [[novasupply-agent]] (recherche marché faite dans ce projet-là, voir sa section "Statut" du 2026-10-04).

## Pourquoi ce projet, et pourquoi différent de NovaSupply

NovaSupply Ops Agent a validé la compétence "agent qui choisit ses outils" (Strands + Bedrock + Lambda/API Gateway/CDK artisanal). Deux lacunes identifiées en le construisant, confirmées par la recherche marché :

1. **LangGraph** domine l'adoption enterprise des frameworks d'agents (34,5M téléchargements mensuels, utilisé par Klarna/Replit/Elastic), pas Strands. LangGraph modélise l'agent comme un **graphe d'états explicite** (nœuds + arêtes conditionnelles), pas une simple boucle outil-après-outil — ça permet des patterns que Strands ne fait pas nativement, notamment l'**interruption humaine** (pause durable de l'exécution en attendant une décision humaine, avec reprise exacte où ça s'était arrêté).
2. **AWS Bedrock AgentCore** (disponibilité générale depuis octobre 2025) est la nouvelle couche managée pour déployer des agents sur AWS : Runtime (hébergement serverless avec isolation par session), Gateway (transforme une API existante en outil d'agent avec auth intégrée), Memory (court/long terme), Observability et Evaluations intégrées. Sur NovaSupply, tout ça a été construit à la main (Lambda, table `traces`, suite `evals.py` custom). Ici, l'objectif est d'utiliser les primitives natives d'AgentCore à la place.

## Scénario

**Alder Kitchens**, une chaîne de restaurants fictive, reçoit des factures de ses fournisseurs alimentaires (viande, poisson, légumes, boissons) qu'il faut valider avant paiement, restaurant par restaurant. Le processus métier type :

1. Une facture arrive (email, PDF, ou texte libre pour le prototype).
2. Il faut en extraire les données structurées (fournisseur, montant, numéro de bon de commande, lignes avec quantités et prix au kg/litre/unité).
3. Comparer au bon de commande hebdomadaire correspondant (quantités/prix attendus).
4. Évaluer le risque : montant au-dessus d'un seuil, fournisseur non référencé pour ce restaurant, écart de quantité livrée vs commandée, prix au kg/litre qui dérive anormalement par rapport au bon de commande (saisonnalité des produits frais), facture en double.
5. Si risque faible → approbation automatique. Si risque élevé → **le graphe s'arrête et attend une décision humaine** (le responsable du restaurant ou le contrôle de gestion) avant de continuer.

C'est un vrai cas d'automatisation de comptabilité fournisseurs (AP automation), reconnaissable par n'importe quel recruteur, et qui a une structure naturellement multi-étapes/multi-agents plutôt qu'un simple choix d'outil — contrairement à NovaSupply où un seul agent avec 3 outils suffisait. Le secteur restauration a aussi l'avantage d'écarts de prix fréquents et légitimes (saisonnalité, cours des matières premières), ce qui rend le scoring de risque moins binaire qu'un simple contrôle de conformité — bon terrain pour tester la décision de l'agent à interrompre ou non.

## Architecture du graphe (LangGraph)

Nœuds envisagés (à affiner en Phase 0, pas figé) :

- `extract_invoice` — extrait les champs structurés d'une facture brute (LLM).
- `validate_po` — compare la facture à son bon de commande (donnée mockée en Phase 0, comme `fulfillments` sur NovaSupply).
- `score_risk` — décide si le dossier nécessite une validation humaine.
- Arête conditionnelle : risque faible → `auto_approve` ; risque élevé → `human_approval` (nœud qui utilise `interrupt()` de LangGraph pour suspendre l'exécution).
- `notify` — enregistre la décision finale.

Pas de règle `if/else` écrite à l'avance sur quel nœud fait quoi dans le détail : c'est le graphe qui structure le flux, mais chaque nœud reste un appel LLM qui raisonne sur son propre périmètre.

## Stack technique retenue

- **Python**
- **LangGraph** (orchestration, graphe d'états, interruption/reprise via checkpointer)
- **Amazon Bedrock** comme fournisseur de modèle (même famille que NovaSupply : Claude via Bedrock, modèle précis à choisir en Phase 0)
- **AWS Bedrock AgentCore** : Runtime (hébergement), Gateway (expose le mock ERP comme outil), Memory (persistance de l'état du graphe pendant une interruption humaine), Observability/Evaluations natifs
- **AWS CDK (Python)** pour toute ressource encore nécessaire en dehors d'AgentCore (ex: la donnée mockée du bon de commande)

## Point de vigilance

AgentCore est un service très récent (GA octobre 2025) : peu de retours d'expérience en ligne, documentation probablement encore incomplète sur certains détails (ex: comment persister exactement l'état d'interruption LangGraph via AgentCore Memory). À documenter au fur et à mesure plutôt que de supposer que ça marchera comme prévu du premier coup — NovaSupply a déjà montré que même des services AWS matures (S3 Vectors, Bedrock Knowledge Base) ont des pièges non documentés (dépendances CloudFormation implicites manquantes, noms de ressources trop longs).

## Roadmap par phases

**Phase 0 — graphe LangGraph local**
Construire le graphe avec les nœuds ci-dessus, données de bon de commande mockées en dur (pas encore d'AWS réel), modèle appelé via Bedrock. Valider le routage conditionnel ET l'interruption humaine en local (checkpointer `MemorySaver` de LangGraph), sur plusieurs cas de test (risque faible, risque élevé, écart détecté).

**Phase 1 — déploiement AgentCore**
Packager le graphe pour AgentCore Runtime. Exposer le mock ERP (ou une vraie donnée si pertinent) via AgentCore Gateway. Tester l'interruption humaine à travers une vraie session AgentCore (pas juste en mémoire locale) — point le plus incertain du projet.

**Phase 2 — Observability & Evaluations natifs**
Utiliser les fonctionnalités Observability/Evaluations d'AgentCore plutôt que de recoder une table `traces` et un `evals.py` maison comme sur NovaSupply — comparer l'expérience aux deux approches.

**Phase 3 — à définir selon ce qui manque après les 3 premières phases** (guardrails, vraie extraction de PDF, etc.)

## Statut

**Phase 0 : premier jet terminé le 2026-10-04.** Graphe LangGraph fonctionnel en local (`src/graph.py`) : `extract_invoice` (LLM, extraction structurée via Pydantic) → `validate_po` (comparaison déterministe au bon de commande mocké, pas de LLM — comparer des quantités/prix est un calcul exact, pas un jugement) → `score_risk` (LLM, jugement nuancé sur les écarts) → routage conditionnel `auto_approve` / `human_approval` (`interrupt()`) → `notify`. Checkpointer `InMemorySaver`. 5 cas de test validés dans `src/run_tests.py` : risque faible (conforme), fournisseur non référencé, écart quantité + prix, facture en double, montant au-dessus du seuil malgré conformité — l'interruption humaine se déclenche correctement sur les 4 cas à risque et reprend l'exécution avec `Command(resume=...)`. Modèle : `eu.anthropic.claude-haiku-4-5-20251001-v1:0` via Bedrock (région eu-west-3), même choix que NovaSupply.

Point corrigé en cours de route : stocker l'extraction LLM comme objet Pydantic brut dans le state du graphe déclenchait un warning de dépréciation du checkpointer (sérialisation msgpack d'un type non enregistré). Corrigé en stockant un dict (`model_dump()`) dans le state et en reconstruisant l'objet Pydantic localement dans chaque nœud qui en a besoin.

**Phase 1 : persistance durable validée le 2026-10-11.** Remplacement du checkpointer `InMemorySaver` par `SqliteSaver` (package `langgraph-checkpoint-sqlite`), avec une connexion sqlite ouverte au niveau du module plutôt que via le context manager `from_conn_string(...)` par défaut (celui-ci referme la connexion dès la sortie du bloc `with`, ce qui aurait cassé toute invocation ultérieure). Hypothèse testée explicitement avec `test_persistence_part1.py` et `test_persistence_part2.py` : un premier process Python déclenche une interruption puis se termine complètement, un second process, totalement indépendant, reprend l'exécution depuis le fichier `checkpoints.sqlite` sur disque jusqu'à la décision finale. Confirme que l'état survit à un redémarrage complet du programme, condition nécessaire avant un déploiement sur une Lambda ou AgentCore Runtime qui ne garde rien en mémoire entre deux invocations.

Prochaine étape : packager le graphe pour AgentCore Runtime (le reste de la Phase 1).

## Liens

- Projet précédent, origine de la recherche marché qui a motivé ce projet : [[novasupply-agent]] (`~/Desktop/CODE/freelance-clients/novasupply-agent/`), resté sur Strands/Lambda/CDK.
