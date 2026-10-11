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

**Phase 1 : déploiement réel sur AgentCore Runtime terminé le 2026-10-11.** L'outil de déploiement officiel a changé entre notre recherche initiale et maintenant : AWS a remplacé l'ancien package Python `bedrock-agentcore-starter-toolkit` par un nouveau CLI npm, `@aws/agentcore` (Node.js 20+ requis en plus de Python/uv). `agentcore create --framework LangChain_LangGraph` génère un scaffold complet (entrypoint `main.py`, structure `app/<nom>/`, CDK généré automatiquement dans `agentcore/cdk/`) qu'on a adapté pour y brancher notre graphe existant plutôt que l'agent `create_react_agent` fourni par défaut.

Surprise documentée : le répertoire de code sur AgentCore Runtime (build `CodeZip`) est en lecture seule. Notre `checkpoints.sqlite` ne pouvait pas s'écrire au chemin relatif utilisé en local (`sqlite3.OperationalError: attempt to write a readonly database`, vu dans les logs CloudWatch). Corrigé en pointant la connexion sqlite vers `/tmp` (seul répertoire inscriptible dans ce type d'environnement serverless).

Déployé avec `agentcore deploy` et testé via l'API réelle `invoke_agent_runtime` (pas `agentcore invoke`, qui n'envoie qu'un `prompt` texte simple, incompatible avec notre payload structuré `{"raw_text": ...}` / `{"human_decision": ...}`) : une facture à risque élevé interrompt bien l'agent déployé, et un second appel séparé, avec le même `session_id`, reprend correctement jusqu'à la décision finale. Point de prudence : ce test s'est fait à quelques secondes d'écart, donc il ne prouve pas encore que l'état survit à un vrai redémarrage d'instance (le scénario réel à plusieurs heures/jours) — seulement qu'il survit au sein d'une même instance chaude. À retester sur un délai plus long avant de considérer la persistance en production comme validée.

**Phase 2 : Evaluations natives testées le 2026-10-11.** Le modèle d'évaluation d'AgentCore ne ressemble pas à `evals.py` sur NovaSupply (écrire des cas de test, relancer le code, asserter sur le résultat). Ici, on invoque l'agent normalement, ce qui génère des traces dans CloudWatch, puis on fait juger ces traces après coup par un évaluateur. Deux types possibles : `llm-as-a-judge` (consigne en langage naturel, pas d'infra à héberger) ou `code-based` (fonction Lambda à écrire et héberger soi même, plus proche de l'ancienne approche). Choisi `llm-as-a-judge` pour la simplicité : un évaluateur `invoice_decision_correctness` créé via `agentcore add evaluator` (niveau `SESSION`, placeholders disponibles trouvés par essai-erreur : `{context}` et `{available_tools}`), avec une consigne décrivant les 4 critères de correction attendus pour ce métier.

Les 5 cas de test de Phase 0 ont été rejoués pour de vrai contre l'agent déployé (`run_remote_tests.py`), puis évalués avec `agentcore run eval`. Résultat : 4/5 Pass, 1/5 Fail. Le Fail est un faux négatif, pas un bug de l'agent : en inspectant la trace réelle (`agentcore traces get`), la reprise de cette session précise (celle qui conclut en 0,006s, sans nouvel appel LLM à faire) a été indexée dans CloudWatch sans l'attribut `sessionId` correctement associé, alors que les 3 autres reprises (plus lentes, avec un appel LLM ou pas selon le cas) l'ont bien eu. L'évaluateur n'a donc vu que la moitié de la session et a conclu, à raison avec les données disponibles, qu'aucune interruption n'était visible. Surprise AgentCore documentée : les reprises très rapides semblent perdre intermittemment leur tag `sessionId` dans les traces d'observabilité, pas un problème systématique (1 cas sur 4 reprises testées), mais un vrai piège pour qui se fierait aveuglément au score automatique sans vérifier la trace sous-jacente en cas d'échec inattendu.

**Phase 3 : vraie extraction par vision testée le 2026-10-11.** `extract_invoice` ne partait que de texte tapé à la main. Génération de vraies images de facture (`src/generate_sample_invoices.py`, PNG avec en-tête, tableau de lignes, total, via Pillow) pour les cas "conforme" et "fournisseur non référencé", puis extraction directement par la vision de Claude (message multimodal `HumanMessage` avec un bloc `image` en base64, plutôt qu'un bloc texte) : `src/test_vision_extraction.py` valide l'extraction isolée, `src/test_vision_graph.py` valide le graphe complet à partir d'une image. `InvoiceState` accepte maintenant `raw_text` OU `image_base64` (mutuellement exclusifs), `extract_invoice` bascule automatiquement entre les deux. Aucune régression sur les 5 cas texte de Phase 0 (`run_tests.py` toujours 5/5).

Propagé jusqu'à l'agent réellement déployé le même jour : `main.py` accepte désormais un payload `{"image_base64": ...}` en plus de `{"raw_text": ...}` / `{"human_decision": ...}`, redéployé et testé via `invoke_agent_runtime` avec les deux images générées (conforme et fournisseur non référencé) : extraction, routage et interruption/reprise fonctionnent à l'identique du chemin texte, directement sur AgentCore Runtime.

**Phase 1 (réserve) : résultat négatif sur la persistance longue durée, le 2026-10-11.** Test lancé en parallèle du travail de Phase 3 : une facture à risque envoyée, attente de 17 minutes (au-delà du délai d'inactivité par défaut d'AgentCore Runtime, 900s/15min, trouvé dans la doc AWS), puis reprise. Résultat : `KeyError: 'raw_text'` dans les logs CloudWatch, l'agent est reparti de `START` avec un état vide au lieu de reprendre à `human_approval`, preuve que `/tmp/checkpoints.sqlite` n'avait pas survécu.

Facteur confondant à noter honnêtement : l'agent a été redéployé (pour l'extraction vision) pendant la fenêtre d'attente de 17 minutes, donc impossible d'isoler si c'est le timeout d'inactivité naturel ou le redéploiement qui a provoqué le remplacement d'instance. Les deux produisent le même effet (nouvelle instance, `/tmp` vierge), donc la cause précise reste à isoler avec un test plus propre si besoin. Ce qui est en revanche confirmé sans ambiguïté : **`/tmp` ne survit pas à un changement d'instance**, qu'il soit causé par un timeout ou un déploiement. Pour un vrai cas d'usage où l'attente humaine peut durer des heures ou des jours, une persistance locale sur `/tmp` est donc insuffisante : il faudrait un stockage externe durable (EFS monté via `--session-storage-mount-path`/`--efs-mount-path`, vus dans les options de `agentcore create`, ou une base de données comme DynamoDB) pour que le pattern d'interruption humaine soit fiable en production.

**Phase 1 (réserve refermée) : persistance longue durée validée le 2026-10-11.** Stockage de session géré par AgentCore branché (`filesystemConfigurations.sessionStorage` dans `agentcore.json`, monté sur `/mnt/session-storage`, configuré sans créer manuellement de système de fichiers EFS). Premier essai bloqué par une limitation connue de SQLite (pas spécifique à AWS) : le verrouillage de fichier POSIX ne fonctionne pas correctement sur ce type de stockage réseau (`database is locked` dès la création du fichier). Contourné avec le paramètre d'URI SQLite `nolock=1` (acceptable ici : pas de vraie concurrence sur une même session). Test de 17 minutes rejoué proprement (sans redéploiement cette fois) : facture envoyée, interruption, attente réelle de 17 minutes, reprise réussie avec la décision finale correcte. La réserve ouverte depuis le début de la Phase 1 est maintenant refermée : la persistance survit à un vrai changement d'instance, pas seulement à quelques secondes d'écart.

**Phase 3 : guardrail + test adversarial, le 2026-10-11.** Angle d'attaque choisi, spécifique à notre architecture : `extract_invoice` lit du texte non fiable (n'importe quel fournisseur peut écrire sa facture), et le champ `fournisseur` extrait est réinjecté dans le prompt de `score_risk`. Trois tentatives d'injection de prompt indirecte testées (`test_adversarial_injection{,_v2,_v3}.py`) : marqueur explicite ("SYSTEM OVERRIDE"), note commerciale plausible en bas de facture, instruction formatée comme une mention légale dans le nom du fournisseur. **Les trois ont échoué, sans aucun garde-fou actif.** Raison structurelle identifiée : la sortie contrainte par schéma Pydantic (`with_structured_output`) filtre naturellement les instructions parasites lors de l'extraction, et le texte brut de la facture n'atteint de toute façon jamais `score_risk` (qui ne reçoit que les champs structurés et les écarts calculés en Python déterministe).

Garde-fou ajouté quand même, en défense en profondeur : Bedrock Guardrail (`alder-invoice-prompt-attack-guard`, filtre `PROMPT_ATTACK` en `HIGH`/`BLOCK`) branché sur `ChatBedrockConverse` via `guardrail_config`. Validé par un vrai appel adversarial direct (pas juste un message normal) : `stopReason: guardrail_intervened`, filtre détecté et bloqué.

Point honnête à retenir, découvert en vérifiant la trace du guardrail sur nos 3 tentatives réelles : **le guardrail ne s'est déclenché sur aucune des trois** (`actionReason: No action.`). Il ne réagit qu'à des formulations d'attaque nues et classiques, pas aux attaques subtiles noyées dans un contexte métier plausible. Les deux défenses (architecture structurée + guardrail) sont donc complémentaires, pas redondantes : chacune couvre un type d'attaque que l'autre ne couvre pas forcément.

Propagé à l'agent réellement déployé le même jour (`model/load.py`). Détail d'infra découvert au passage : le rôle d'exécution IAM de l'agent (différent de notre utilisateur IAM local) n'avait pas la permission `bedrock:ApplyGuardrail`, ajoutée manuellement sur la ressource du guardrail précisément. Testé sur le vrai agent déployé : facture normale toujours approuvée automatiquement (pas de régression), facture avec injection toujours correctement interrompue pour validation humaine, cohérent avec les résultats locaux.

Les trois phases de la roadmap initiale sont maintenant complètes (Phase 0, 1, 2, 3), avec une réserve de Phase 1 explicitement testée et refermée dans la journée.

## Liens

- Projet précédent, origine de la recherche marché qui a motivé ce projet : [[novasupply-agent]] (`~/Desktop/CODE/freelance-clients/novasupply-agent/`), resté sur Strands/Lambda/CDK.
