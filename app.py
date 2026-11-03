import os

from flask import Flask, render_template


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")

    @app.get("/")
    def dashboard():
        return render_template(
            "dashboard.html",
            servers=[],
            metrics=[
                {"label": "CPU", "value": "—"},
                {"label": "Memory", "value": "—"},
                {"label": "Network", "value": "—"},
                {"label": "Ports", "value": "—"},
            ],
        )

    return app


app = create_app()


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=debug)
