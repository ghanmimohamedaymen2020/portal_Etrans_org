from flask import render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db, login_manager
from app.models import User, Role, PasswordResetToken
from app.utils import send_email
from datetime import datetime, timedelta
import secrets
import re
from app.routes import auth_bp

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@auth_bp.route('/')
def index():
    """Page d'accueil - redirige vers login ou dashboard"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if not username or not password:
            flash('Veuillez fournir un nom d\'utilisateur et un mot de passe.', 'error')
        else:
            if user:
                if user.check_password(password):
                    if user.is_active:
                        user.last_login = datetime.utcnow()
                        db.session.commit()
                        login_user(user, remember=request.form.get('remember', False))
                        flash('Connexion réussie!', 'success')
                        next_page = request.args.get('next')
                        if next_page:
                            return redirect(next_page)
                        return redirect(url_for('dashboard.index'))
                    else:
                        flash('Utilisateur désactivé.', 'error')
                else:
                    flash('Nom d\'utilisateur ou mot de passe incorrect.', 'error')
            else:
                flash('Nom d\'utilisateur ou mot de passe incorrect.', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Vous avez été déconnecté.', 'info')
    return redirect(url_for('auth.login'))

def validate_password_rules(password):
    errors = []
    if len(password) < 8:
        errors.append('Le mot de passe doit contenir au moins 8 caractères.')
    if not re.search(r'[A-Z]', password):
        errors.append('Le mot de passe doit contenir une lettre majuscule.')
    if not re.search(r'[a-z]', password):
        errors.append('Le mot de passe doit contenir une lettre minuscule.')
    if not re.search(r'[0-9]', password):
        errors.append('Le mot de passe doit contenir un chiffre.')
    if not re.search(r'[!@#$%^&*]', password):
        errors.append('Le mot de passe doit contenir un caractère spécial (!@#$%^&*).')
    return errors

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_user.check_password(current_password):
            flash('Le mot de passe actuel est incorrect.', 'error')
            return redirect(url_for('auth.change_password'))
        
        if new_password != confirm_password:
            flash('Les nouveaux mots de passe ne correspondent pas.', 'error')
            return redirect(url_for('auth.change_password'))

        if current_user.check_password(new_password):
            flash('Le nouveau mot de passe doit être différent de l\'ancien.', 'error')
            return redirect(url_for('auth.change_password'))

        errors = validate_password_rules(new_password)
        if errors:
            flash(' '.join(errors), 'error')
            return redirect(url_for('auth.change_password'))
        
        current_user.set_password(new_password)
        db.session.commit()
        flash('Votre mot de passe a été changé avec succès.', 'success')
        return redirect(url_for('dashboard.index'))
    
    return render_template('auth/change_password.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Générer un token
            token = secrets.token_urlsafe(32)
            reset_token = PasswordResetToken(
                user_id=user.id,
                token=token,
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            db.session.add(reset_token)
            db.session.commit()
            
            # Envoyer l'email
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            send_email(
                user.email,
                'Réinitialisation du mot de passe',
                f'Cliquez sur le lien pour réinitialiser votre mot de passe: {reset_url}'
            )
            flash('Un email de réinitialisation a été envoyé.', 'info')
        else:
            flash('Un email de réinitialisation a été envoyé si le compte existe.', 'info')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    reset_token = PasswordResetToken.query.filter_by(token=token).first()
    
    if not reset_token or not reset_token.is_valid():
        flash('Le lien de réinitialisation est invalide ou expiré.', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Les mots de passe ne correspondent pas.', 'error')
            return redirect(url_for('auth.reset_password', token=token))

        user = reset_token.user
        if user.check_password(password):
            flash('Le nouveau mot de passe doit être différent de l\'ancien.', 'error')
            return redirect(url_for('auth.reset_password', token=token))

        errors = validate_password_rules(password)
        if errors:
            flash(' '.join(errors), 'error')
            return redirect(url_for('auth.reset_password', token=token))
        user.set_password(password)
        reset_token.is_used = True
        db.session.commit()
        
        flash('Votre mot de passe a été réinitialisé. Vous pouvez maintenant vous connecter.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html')

@auth_bp.route('/admin/users', methods=['GET'])
@login_required
def manage_users():
    """Page de gestion des utilisateurs (Admin seulement)"""
    if current_user.role.name != 'Admin':
        flash('Accès non autorisé.', 'error')
        return redirect(url_for('dashboard.index'))
    
    users = User.query.all()
    roles = Role.query.all()
    return render_template('admin/manage_users.html', users=users, roles=roles)

@auth_bp.route('/admin/users/create', methods=['POST'])
@login_required
def create_user():
    """Créer un nouvel utilisateur (Admin seulement)"""
    if current_user.role.name != 'Admin':
        flash('Accès non autorisé.', 'error')
        return redirect(url_for('dashboard.index'))
    
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    role_id = request.form.get('role_id')
    
    # Validation
    if not all([username, email, password, role_id]):
        flash('Tous les champs sont obligatoires.', 'error')
        return redirect(url_for('auth.manage_users'))
    
    # Vérifier si l'utilisateur existe déjà
    if User.query.filter_by(username=username).first():
        flash('Ce nom d\'utilisateur existe déjà.', 'error')
        return redirect(url_for('auth.manage_users'))
    
    if User.query.filter_by(email=email).first():
        flash('Cet email est déjà utilisé.', 'error')
        return redirect(url_for('auth.manage_users'))
    
    # Créer l'utilisateur
    user = User(username=username, email=email, role_id=role_id)
    user.set_password(password)
    user.is_active = True
    
    db.session.add(user)
    db.session.commit()
    
    flash(f'Utilisateur {username} créé avec succès!', 'success')
    return redirect(url_for('auth.manage_users'))

@auth_bp.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    """Supprimer un utilisateur (Admin seulement)"""
    if current_user.role.name != 'Admin':
        flash('Accès non autorisé.', 'error')
        return redirect(url_for('dashboard.index'))
    
    user = User.query.get_or_404(user_id)
    
    # Ne pas supprimer soi-même
    if user.id == current_user.id:
        flash('Vous ne pouvez pas supprimer votre propre compte.', 'error')
        return redirect(url_for('auth.manage_users'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    flash(f'Utilisateur {username} supprimé avec succès.', 'success')
    return redirect(url_for('auth.manage_users'))

@auth_bp.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@login_required
def toggle_user(user_id):
    """Activer/désactiver un utilisateur (Admin seulement)"""
    if current_user.role.name != 'Admin':
        flash('Accès non autorisé.', 'error')
        return redirect(url_for('dashboard.index'))
    
    user = User.query.get_or_404(user_id)
    
    # Ne pas désactiver soi-même
    if user.id == current_user.id:
        flash('Vous ne pouvez pas désactiver votre propre compte.', 'error')
        return redirect(url_for('auth.manage_users'))
    
    user.is_active = not user.is_active
    db.session.commit()
    
    status = 'activé' if user.is_active else 'désactivé'
    flash(f'Utilisateur {user.username} {status} avec succès.', 'success')
    return redirect(url_for('auth.manage_users'))
