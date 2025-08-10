from flask import Flask, render_template, request, jsonify


def create_app() -> Flask:
    """Application factory to create and configure the Flask app."""
    app = Flask(__name__)

    @app.route("/")
    def home():
        return render_template("index.html", title="Omni Chat", message="Hello, world!")

    @app.post("/api/chat")
    def api_chat():
        """Placeholder chat endpoint that echoes the user's message.

        Expected JSON body: { message: str, history: list, provider: str, model: str }
        """
        try:
            data = request.get_json(silent=True) or {}
            message = (data.get("message") or "").strip()
            provider = data.get("provider") or "unknown"
            model = data.get("model") or "unknown"
            if not message:
                return jsonify({"error": "message is required"}), 400
            reply = f"[{provider}/{model}] Echo: {message}"
            return jsonify({"reply": reply})
        except Exception:  # pragma: no cover - keep placeholder simple
            return jsonify({"error": "unexpected error"}), 500

    return app


app = create_app()


if __name__ == "__main__":
    # Run the development server
    app.run(debug=True, host="127.0.0.1", port=5000)
