import jwt
from functools import wraps
from flask import request, jsonify, current_app
from app.models import User
from config import Config

def token_required(f):
    """Décorateur pour vérifier le token JWT"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'message': 'Token manquant'}), 401
        
        if not token:
            return jsonify({'message': 'Token manquant'}), 401
        
        try:
            data = jwt.decode(token, Config.JWT_SECRET, algorithms=[Config.JWT_ALGORITHM])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'message': 'Utilisateur non trouvé'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token expiré'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token invalide'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

def role_required(role_names):
    """Décorateur pour vérifier les rôles utilisateur"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask_login import current_user
            
            if not current_user.is_authenticated:
                return jsonify({'message': 'Non authentifié'}), 401
            
            if current_user.role.name not in role_names:
                return jsonify({'message': 'Accès refusé'}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator

def send_email(recipient, subject, body, html=None):
    """Envoyer un email"""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        sender = current_app.config['MAIL_USERNAME']
        password = current_app.config['MAIL_PASSWORD']
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient
        
        msg.attach(MIMEText(body, 'plain'))
        if html:
            msg.attach(MIMEText(html, 'html'))
        
        with smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT']) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"Erreur lors de l'envoi d'email: {e}")
        return False


def get_agent_monthly_by_year(db, year: int):
    """Backward-compatible wrapper: monthly series per currency for Agent invoices (type 'A').

    Uses `get_invoice_monthly_and_annual` under the hood and returns only the
    `series` part (dict currency -> 12-element list).
    """
    # Calculation removed by request. Return empty series to disable agent monthly CA.
    return {}


def get_agent_totals_for_month(db, year: int, month: int):
    """Return totals per currency for a specific month/year for Agent invoices.

    Returns a dict mapping currency codes to float totals. This wrapper uses
    `get_invoice_monthly_and_annual` to compute values.
    """
    # Calculation removed by request. Return empty totals.
    return {}


def get_invoice_monthly_and_annual(db, year: int, invoice_type: str | None = None):
    """Return monthly series and annual totals per currency for invoices.

    This single function serves both the monthly histogram (series) and the
    annual total (sum of the 12 months). It returns a dict with two keys:

    - 'series': { 'EUR': [12 floats], 'USD': [12 floats], ... }
    - 'totals': { 'EUR': float, 'USD': float, ... }

    Parameters:
    - `invoice_type`: if provided (e.g. 'A'), filter by
      `UPPER(LTRIM(RTRIM(e.FF_H_TypeFacture))) = :invoice_type`.
    """
    # Calculation removed by request. Return empty series and totals.
    return {'series': {}, 'totals': {}}
