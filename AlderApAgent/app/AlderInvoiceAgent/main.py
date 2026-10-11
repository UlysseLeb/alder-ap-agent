import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from graph import builder

LangchainInstrumentor().instrument()

app = BedrockAgentCoreApp()
log = app.logger

# Checkpointer durable. /tmp a été testé et confirmé NON durable : perdu dès
# qu'une nouvelle instance remplace l'ancienne (testé le 2026-10-11, voir
# docs/PROJECT.md). Remplacé par un stockage de session géré par AgentCore
# (filesystemConfigurations.sessionStorage dans agentcore.json), monté sur
# /mnt/session-storage. Ce montage est un système de fichiers réseau (type
# NFS) : le verrouillage de fichier POSIX classique de SQLite y échoue
# ("database is locked" dès la création, testé le 2026-10-11). "nolock=1"
# désactive ce verrouillage (documenté par SQLite pour ce cas précis :
# https://www.sqlite.org/uri.html). Acceptable ici : un seul écrivain actif
# par session, pas de vraie concurrence sur un même thread_id.
_conn = sqlite3.connect(
    "file:/mnt/session-storage/checkpoints.sqlite?nolock=1",
    uri=True,
    check_same_thread=False,
    timeout=30,
)
_checkpointer = SqliteSaver(_conn)
graph = builder.compile(checkpointer=_checkpointer)


@app.entrypoint
async def invoke(payload, context):
    thread_id = getattr(context, "session_id", "default-session")
    config = {"configurable": {"thread_id": thread_id}}

    if "human_decision" in payload:
        log.info(f"Reprise de la session {thread_id} avec une décision humaine")
        result = graph.invoke(Command(resume=payload["human_decision"]), config=config)
    elif "image_base64" in payload:
        log.info(f"Nouvelle facture (image) pour la session {thread_id}")
        result = graph.invoke({"image_base64": payload["image_base64"]}, config=config)
    else:
        log.info(f"Nouvelle facture pour la session {thread_id}")
        result = graph.invoke({"raw_text": payload["raw_text"]}, config=config)

    if "__interrupt__" in result:
        interruption = result["__interrupt__"][0]
        return {"status": "pending_human_approval", "question": interruption.value}

    return {
        "status": "done",
        "risque": result["risque"],
        "decision_finale": result["decision_finale"],
        "ecarts": result["ecarts"],
    }


if __name__ == "__main__":
    app.run()
