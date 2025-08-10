from flask import Flask, render_template


def create_app() -> Flask:
    """Application factory to create and configure the Flask app."""
    app = Flask(__name__)

    @app.route("/")
    def home():
        return render_template("index.html", title="Omni Chat", message="Hello, world!")

    return app


app = create_app()


if __name__ == "__main__":
    # Run the development server
    app.run(debug=True, host="127.0.0.1", port=5000)
