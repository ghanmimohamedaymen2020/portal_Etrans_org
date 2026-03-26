"""Point d'entrée de l'application E-trans Portal."""
import os

from dotenv import load_dotenv

# Charger le fichier .env correspondant à l'environnement
env = os.environ.get("FLASK_ENV", "development")
dotenv_path = f".env.{env}"
load_dotenv(dotenv_path if os.path.exists(dotenv_path) else ".env")

from app import create_app, db  # noqa: E402

app = create_app(env)


@app.shell_context_processor
def make_shell_context():
    """Variables disponibles dans `flask shell`."""
    return {"db": db, "app": app}


if __name__ == "__main__":
    debug_mode = env == "development"
    app.run(debug=debug_mode, host="0.0.0.0", port=5000)
