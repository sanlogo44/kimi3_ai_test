
"""Flask-Server: Admin-Bereich + User-Trainings-Interface mit 4 Toggle-Switches."""
import os
import json
import copy
import torch
from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify)

import auth
import analytics
import benchmarks
from model_manager import (ToyModel, train_step, save_checkpoint,
                           list_checkpoints, load_checkpoint, delete_checkpoint,
                           soup, synthetic_data, DEVICE)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "kimi3-dev-secret-change-me")

# Toggle-Zustaende (Toggle 1: Bewerten, 2: Graph/Tabelle, 3: Layer-Training, 4: Auto-Benchmarks)
# Persistiert in data/toggles.json -> ueberlebt Server-Neustart.
TOGGLES_FILE = os.path.join(os.path.dirname(__file__), "data", "toggles.json")
_DEFAULT_TOGGLES = {"rate_mode": False, "show_graph": True,
                    "layer_training": False, "auto_benchmarks": False}


def load_toggles():
    if os.path.exists(TOGGLES_FILE):
        try:
            with open(TOGGLES_FILE, "r", encoding="utf-8") as f:
                return {**_DEFAULT_TOGGLES, **json.load(f)}
        except Exception:
            pass
    return dict(_DEFAULT_TOGGLES)


def save_toggles():
    os.makedirs(os.path.dirname(TOGGLES_FILE), exist_ok=True)
    with open(TOGGLES_FILE, "w", encoding="utf-8") as f:
        json.dump(TOGGLES, f, indent=2)


TOGGLES = load_toggles()

_model = ToyModel().to(DEVICE)          # Original-Modell (wird nie durch Weitertraining veraendert)
_model_lock = __import__("threading").Lock()


# ---------------- Auth ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if auth.verify(request.form["username"], request.form["password"]):
            session["is_admin"] = True
            session["user"] = request.form["username"]
            if auth.must_change_password():
                return redirect(url_for("change_credentials"))
            return redirect(url_for("index"))
        error = "Ungueltige Zugangsdaten."
    return render_template("login.html", error=error)

@app.route("/change-credentials", methods=["GET", "POST"])
@auth.admin_required
def change_credentials():
    msg = None
    if request.method == "POST":
        u, p1, p2 = (request.form.get(k, "") for k in ("username", "password", "password2"))
        if len(p1) < 4:
            msg = "Passwort muss mindestens 4 Zeichen haben."
        elif p1 != p2:
            msg = "Passwoerter stimmen nicht ueberein."
        else:
            auth.change_credentials(u, p1)
            session["user"] = u
            return redirect(url_for("index"))
    return render_template("change_credentials.html", msg=msg, forced=auth.must_change_password())

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------- Seiten ----------------

@app.route("/")
@auth.admin_required
def index():
    return render_template("training.html",
                           toggles=TOGGLES,
                           checkpoints=list_checkpoints(),
                           layers=ToyModel().layer_names(),
                           admin=True,
                           benchmarks_on=benchmarks.is_running())

@app.route("/admin")
@auth.admin_required
def admin_panel():
    """Reiner Admin-Bereich: Nutzerverwaltung, Toggles global, Checkpoint-Verwaltung."""
    return render_template("admin.html",
                           toggles=TOGGLES,
                           checkpoints=list_checkpoints(),
                           metrics=analytics.all_metrics(),
                           benchmarks_on=benchmarks.is_running())


# ---------------- API: Toggles ----------------

@app.route("/api/toggles", methods=["GET", "POST"])
@auth.admin_required
def toggles_api():
    if request.method == "POST":
        data = request.get_json(force=True)
        for k in TOGGLES:
            if k in data:
                TOGGLES[k] = bool(data[k])
        save_toggles()
        if "auto_benchmarks" in data:
            if data["auto_benchmarks"]:
                benchmarks.start(__import__("model_manager"), analytics)
            else:
                benchmarks.stop()
    return jsonify({"toggles": TOGGLES, "benchmarks_running": benchmarks.is_running()})


# ---------------- API: Training ----------------

@app.route("/api/train", methods=["POST"])
@auth.admin_required
def train_api():
    data = request.get_json(force=True)
    epochs = int(data.get("epochs", 10))
    lr = float(data.get("lr", 1e-2))
    base_model = data.get("base_model")            # optional: Checkpoint-Id
    train_layers = data.get("layers") or None      # Toggle 3: nur diese Layer trainieren

    X, y = synthetic_data()
    if base_model:
        # Kopie laden -> Original-Checkpoint bleibt unberuehrt
        model, meta = load_checkpoint(base_model)
    else:
        with _model_lock:
            model = copy.deepcopy(_model)

    stats = train_step(model, X, y, epochs=epochs, lr=lr, train_layers=train_layers)
    analytics.record(model=meta["name"] if base_model else "original",
                     accuracy=stats["accuracy"], train_time=stats["train_time"],
                     tokens=stats["tokens"], epoch=epochs)
    return jsonify({
        "accuracy": stats["accuracy"],
        "train_time": stats["train_time"],
        "tokens": stats["tokens"],
        "layers_trained": train_layers or "all",
    })

@app.route("/api/train/soup", methods=["POST"])
@auth.admin_required
def soup_api():
    """SOUP-Training: mehrere Checkpoints mitteln und als neues Modell speichern."""
    ids = request.get_json(force=True).get("checkpoint_ids", [])
    models = [load_checkpoint(cid)[0] for cid in ids]
    if not models:
        return jsonify({"error": "keine Checkpoints gewaehlt"}), 400
    merged = soup(models)
    X, y = synthetic_data()
    acc = float((merged(X.to(DEVICE)).argmax(1) == y.to(DEVICE)).float().mean())
    cid = save_checkpoint(merged, f"soup_of_{len(ids)}", {"accuracy": acc})
    return jsonify({"accuracy": acc, "checkpoint_id": cid})


# ---------------- API: Checkpoints ----------------

@app.route("/api/checkpoints", methods=["GET", "POST"])
@auth.admin_required
def checkpoints_api():
    if request.method == "POST":
        data = request.get_json(force=True)
        with _model_lock:
            cid = save_checkpoint(_model, data.get("name", "checkpoint"),
                                  {"accuracy": data.get("accuracy")})
        return jsonify({"checkpoint_id": cid})
    return jsonify({"checkpoints": list_checkpoints()})

@app.route("/api/checkpoints/<cid>/delete", methods=["POST"])
@auth.admin_required
def checkpoint_delete(cid):
    return jsonify({"deleted": delete_checkpoint(cid)})

@app.route("/api/checkpoints/<cid>/use", methods=["POST"])
@auth.admin_required
def checkpoint_use(cid):
    """Gespeichertes Modell als Arbeitskopie laden; Original bleibt erhalten."""
    global _model
    model, meta = load_checkpoint(cid)
    with _model_lock:
        _model = model
    return jsonify({"loaded": meta["name"]})


# ---------------- API: Bewertung (Toggle 1) ----------------

@app.route("/api/rate", methods=["POST"])
@auth.admin_required
def rate_api():
    if not TOGGLES["rate_mode"]:
        return jsonify({"error": "Bewertungsmodus ist deaktiviert"}), 403
    data = request.get_json(force=True)
    with __import__("sqlite3").connect(os.path.join(os.path.dirname(__file__), "data", "ratings.db")) as c:
        c.execute("CREATE TABLE IF NOT EXISTS ratings ("
                  "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, answer TEXT, score INTEGER, comment TEXT)")
        c.execute("INSERT INTO ratings (ts, answer, score, comment) VALUES (?, ?, ?, ?)",
                  (__import__("time").strftime("%Y-%m-%d %H:%M:%S"),
                   str(data.get("answer", ""))[:2000], int(data.get("score", 0)),
                   str(data.get("comment", ""))[:500]))
    return jsonify({"ok": True})


# ---------------- API: Metriken (Toggle 2) ----------------

@app.route("/api/metrics")
@auth.admin_required
def metrics_api():
    return jsonify({"metrics": analytics.all_metrics(), "enabled": TOGGLES["show_graph"]})


if __name__ == "__main__":
    if TOGGLES.get("auto_benchmarks"):
        benchmarks.start(__import__("model_manager"), analytics)
    app.run(host="0.0.0.0", port=5000, debug=True)
