"""Démo pédagogique : affiche en direct l'exécution du graphe Alder dans une page web,
dans l'esprit d'AG-UI (flux d'événements en continu, reprise humaine par le même canal)
mais construite maison, sans le protocole officiel ni redéploiement sur AgentCore.

Interface traduite en anglais (page HTML + JS) pour une démo filmée destinée à un public
anglophone ; le graphe lui-même (graph.py) n'est pas touché, voir _translate_payload
ci-dessous pour la traduction d'affichage appliquée aux événements avant envoi au navigateur.

Lancer : uvicorn demo_ui_server:app --reload --port 8010, puis ouvrir http://localhost:8010
Fait de vrais appels Bedrock (coût réel minime), utilise le graphe et le checkpointer réels du projet.
"""

import json
import uuid

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel

from graph import graph

app = FastAPI(title="Alder AP — live event demo")

FACTURE_DEMO = """
Facture n°F-9033 — Primeur Rhône
Destinataire : Alder Kitchens - Lyon Part-Dieu
Bon de commande : BC-2026-0920
Lignes :
- Tomates grappe : 45 kg x 4,80€/kg
- Salade batavia : 15 kg x 2,10€/kg
Montant total : 247,50€
"""

# Correspondance des clés françaises de l'état du graphe vers un libellé anglais, pour
# l'affichage uniquement : le graphe (graph.py) continue de tourner avec ses noms de
# champs d'origine, rien n'est traduit côté backend logique, seulement côté rendu.
_KEY_LABELS = {
    "fournisseur": "supplier",
    "restaurant": "restaurant",
    "numero_bon_commande": "po_number",
    "montant_total": "total_amount",
    "lignes": "line_items",
    "produit": "product",
    "quantite": "quantity",
    "unite": "unit",
    "prix_unitaire": "unit_price",
    "ecarts": "discrepancies",
    "risque": "risk",
    "justification_risque": "risk_rationale",
    "decision_finale": "final_decision",
    "commentaire_humain": "human_comment",
    "pennylane_invoice_id": "pennylane_invoice_id",
    "extraction": "extraction",
    "question": "question",
}

# Remplacements de valeurs connues (énumérations fixes produites par graph.py) : les
# phrases générées librement par le LLM (justification_risque, ecarts) restent telles
# quelles, seuls les mots-clés fixes de l'état sont traduits.
_VALUE_REPLACEMENTS = {
    "faible": "low",
    "eleve": "high",
    "approuvée automatiquement": "auto-approved",
    "approuvée par validation humaine": "approved by human validation",
    "rejetée par validation humaine": "rejected by human validation",
}

_INTERRUPT_QUESTION_EN = "High-risk invoice: approve or reject?"


def _translate_value(value):
    if isinstance(value, str):
        return _VALUE_REPLACEMENTS.get(value, value)
    if isinstance(value, dict):
        return _translate_payload(value)
    if isinstance(value, list):
        return [_translate_value(v) for v in value]
    return value


def _translate_payload(payload):
    """Traduit les clés connues et les valeurs d'énumération d'un dict d'état pour
    l'affichage dans le navigateur, récursivement. Les clés inconnues sont laissées
    telles quelles plutôt que supprimées, pour ne jamais perdre d'information.
    Un nœud qui ne renvoie rien (sortie None) est laissé tel quel plutôt que de
    faire planter l'affichage, comme le faisait déjà la version non traduite."""
    if not isinstance(payload, dict):
        return payload
    translated = {}
    for key, value in payload.items():
        new_key = _KEY_LABELS.get(key, key)
        translated[new_key] = _translate_value(value)
    if "question" in translated:
        translated["question"] = _INTERRUPT_QUESTION_EN
    return translated


def sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/stream/{thread_id}")
def stream(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}

    def gen():
        yield sse({"type": "run_started"})
        for chunk in graph.stream({"raw_text": FACTURE_DEMO}, config=config, stream_mode="updates"):
            for node_name, output in chunk.items():
                if node_name == "__interrupt__":
                    yield sse({"type": "interrupt", "payload": _translate_payload(output[0].value)})
                else:
                    yield sse({"type": "node", "node": node_name, "output": _translate_payload(output)})
        yield sse({"type": "run_finished"})

    return StreamingResponse(gen(), media_type="text/event-stream")


class Decision(BaseModel):
    thread_id: str
    decision: str
    commentaire: str = ""


@app.post("/resume")
def resume(d: Decision):
    config = {"configurable": {"thread_id": d.thread_id}}
    events = []
    for chunk in graph.stream(
        Command(resume={"decision": d.decision, "commentaire": d.commentaire}),
        config=config,
        stream_mode="updates",
    ):
        for node_name, output in chunk.items():
            events.append({"type": "node", "node": node_name, "output": _translate_payload(output)})
    return {"events": events}


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_PAGE


HTML_PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Alder AP — live event demo</title>
<style>
  body { font-family: -apple-system, sans-serif; max-width: 720px; margin: 40px auto; color: #1a1a1a; }
  h1 { font-size: 20px; }
  #log { margin-top: 24px; }
  .evt { padding: 10px 14px; border-left: 3px solid #ccc; margin-bottom: 8px; background: #fafafa; font-size: 14px; }
  .evt.node { border-left-color: #4065b8; }
  .evt.interrupt { border-left-color: #d9622b; background: #fff6ef; }
  .evt.run { border-left-color: #1f8a58; color: #1f8a58; font-weight: bold; }
  pre { white-space: pre-wrap; margin: 4px 0 0; font-size: 12px; color: #555; }
  button { padding: 8px 16px; margin-right: 8px; cursor: pointer; }
  textarea { width: 100%; margin-top: 8px; }
  #startBtn { padding: 10px 20px; font-size: 14px; }
</style>
</head>
<body>
  <h1>Alder AP Agent — live event stream</h1>
  <p>Invoice sent automatically: F-9033, from supplier "Primeur Rhône" (a price and quantity discrepancy on tomatoes, designed to test whether it's seasonal pricing or a real risk).</p>
  <button id="startBtn" onclick="start()">Start a run</button>
  <div id="log"></div>

<script>
let threadId = null;
let currentSource = null;

function addEvent(cls, html) {
  const div = document.createElement("div");
  div.className = "evt " + cls;
  div.innerHTML = html;
  document.getElementById("log").appendChild(div);
  div.scrollIntoView({behavior: "smooth"});
}

function start() {
  if (currentSource) { currentSource.close(); currentSource = null; }
  document.getElementById("log").innerHTML = "";
  threadId = "demo-" + Math.random().toString(36).slice(2);
  const es = new EventSource("/stream/" + threadId);
  currentSource = es;
  es.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === "run_started") addEvent("run", "Run started");
    if (data.type === "node") addEvent("node", `<b>${data.node}</b><pre>${JSON.stringify(data.output, null, 2)}</pre>`);
    if (data.type === "interrupt") { showInterrupt(data.payload); es.close(); currentSource = null; }
    if (data.type === "run_finished") { addEvent("run", "Finished"); es.close(); currentSource = null; }
  };
}

function showInterrupt(payload) {
  addEvent("interrupt", `
    <b>Human approval requested</b>
    <pre>${JSON.stringify(payload, null, 2)}</pre>
    <div>
      <button onclick="resume('approuvée')">Approve</button>
      <button onclick="resume('rejetée')">Reject</button>
      <textarea id="commentaire" rows="2" placeholder="comment (optional)"></textarea>
    </div>
  `);
}

async function resume(decision) {
  const commentaire = document.getElementById("commentaire").value;
  const label = decision === "approuvée" ? "approve" : "reject";
  addEvent("run", "Decision sent: " + label + ", resuming...");
  const res = await fetch("/resume", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({thread_id: threadId, decision, commentaire}),
  });
  const data = await res.json();
  for (const evt of data.events) {
    addEvent("node", `<b>${evt.node}</b><pre>${JSON.stringify(evt.output, null, 2)}</pre>`);
  }
  addEvent("run", "Finished");
}
</script>
</body>
</html>
"""
