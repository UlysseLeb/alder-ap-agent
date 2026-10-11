"""Appelle le vrai agent déployé sur AWS Bedrock AgentCore Runtime (pas en local).

agentcore invoke ne sait envoyer qu'un "prompt" texte simple ; notre entrypoint
attend un payload structuré ({"raw_text": ...} ou {"human_decision": ...}), donc
on utilise directement l'API boto3 invoke_agent_runtime comme documenté par AWS.
"""

import json
import sys
import uuid
from pathlib import Path

import boto3

# L'ARN n'est pas codé en dur (il contient l'ID de compte AWS) : on le relit
# depuis l'état de déploiement local, généré par `agentcore deploy` et jamais
# commité (cf. AlderApAgent/agentcore/.gitignore).
_STATE_PATH = Path(__file__).resolve().parents[2] / "agentcore" / ".cli" / "deployed-state.json"


def _load_agent_arn() -> str:
    state = json.loads(_STATE_PATH.read_text())
    return state["targets"]["default"]["resources"]["runtimes"]["AlderInvoiceAgent"]["runtimeArn"]


AGENT_ARN = _load_agent_arn()

client = boto3.client("bedrock-agentcore", region_name="eu-west-3")


def call(payload: dict, session_id: str) -> dict:
    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_ARN,
        runtimeSessionId=session_id,
        payload=json.dumps(payload).encode(),
        qualifier="DEFAULT",
    )
    content = [chunk.decode("utf-8") for chunk in response.get("response", [])]
    return json.loads("".join(content))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "new"
    session_id = sys.argv[2] if len(sys.argv) > 2 else str(uuid.uuid4())

    if mode == "new":
        result = call({"raw_text": """
Facture n°F-9012 — Nouveau Fournisseur Viandes SARL
Destinataire : Alder Kitchens - Lyon Part-Dieu
Bon de commande : BC-2026-0921
Lignes :
- Entrecôte de bœuf : 20 kg x 24,50€/kg
Montant total : 490,00€
"""}, session_id)
        print(f"session_id = {session_id}")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif mode == "resume":
        result = call(
            {"human_decision": {"decision": "rejetée", "commentaire": "test agentcore deploy réel"}},
            session_id,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
