import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from graph import builder

LangchainInstrumentor().instrument()

app = BedrockAgentCoreApp()
log = app.logger

# Checkpointer durable (validé en local : survit à un redémarrage complet du
# process, cf. test_persistence_part1/2.py). Sur AgentCore Runtime (build
# CodeZip), le répertoire de code est en lecture seule : seul /tmp est
# inscriptible. Reste à vérifier si /tmp survit entre deux appels distincts
# (deux instances différentes) ou seulement au sein d'une même instance chaude.
_conn = sqlite3.connect("/tmp/checkpoints.sqlite", check_same_thread=False)
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
