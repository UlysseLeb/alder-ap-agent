from langchain_aws import ChatBedrockConverse

# Même modèle que le reste du projet (Phase 0) et que NovaSupply.
MODEL_ID = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
REGION = "eu-west-3"


def load_model() -> ChatBedrockConverse:
    """Get Bedrock model client using IAM credentials."""
    return ChatBedrockConverse(model=MODEL_ID, region_name=REGION, temperature=0)
