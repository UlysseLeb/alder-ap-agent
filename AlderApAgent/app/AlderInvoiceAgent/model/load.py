from langchain_aws import ChatBedrockConverse

# Même modèle que le reste du projet (Phase 0) et que NovaSupply.
MODEL_ID = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
REGION = "eu-west-3"

# Garde-fou : factures = texte non fiable (n'importe quel fournisseur peut en
# écrire une). guardrail_config bloque les tentatives d'injection de prompt
# détectées en entrée (filtre PROMPT_ATTACK). Testé et validé en local (Phase
# 3, voir docs/PROJECT.md) : ne couvre pas tout (nos 3 attaques réelles ne
# l'ont pas déclenché), mais complète la robustesse déjà apportée par la
# sortie structurée Pydantic.
GUARDRAIL_ID = "97j0cwpultuj"
GUARDRAIL_VERSION = "1"


def load_model() -> ChatBedrockConverse:
    """Get Bedrock model client using IAM credentials."""
    return ChatBedrockConverse(
        model=MODEL_ID,
        region_name=REGION,
        temperature=0,
        guardrail_config={
            "guardrail_identifier": GUARDRAIL_ID,
            "guardrail_version": GUARDRAIL_VERSION,
            "trace": "enabled",
        },
    )
