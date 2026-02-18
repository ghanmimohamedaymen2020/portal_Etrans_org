import os
from dotenv import load_dotenv
from app import create_app, db

# Determine environment and load corresponding .env file if present
env = os.environ.get('FLASK_ENV', 'development')
dotenv_path = f'.env.{env}'
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    # fallback to default .env
    load_dotenv()

# Créer l'application
app = create_app(env)

@app.shell_context_processor
def make_shell_context():
    """Contexte shell pour flask shell"""
    return {'db': db}

@app.before_request
def before_request():
    """Avant chaque requête"""
    pass

@app.after_request
def after_request(response):
    """Après chaque requête"""
    return response

@app.errorhandler(404)
def not_found(error):
    """Erreur 404"""
    from flask import render_template
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Erreur 500"""
    db.session.rollback()
    from flask import render_template
    return render_template('errors/500.html'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
