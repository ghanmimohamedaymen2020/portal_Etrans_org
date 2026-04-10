"""Routes d'authentification."""
from datetime import datetime

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db, login_manager
from app.i18n import t
from app.models.user import Role, User
from app.routes import auth_bp
from app.services.auth_service import AuthService
from app.utils.audit import log_user_event


@login_manager.user_loader
def load_user(user_id: int):
    return User.query.get(int(user_id))


# ------------------------------------------------------------------ #
#  Index / Login / Logout                                            #
# ------------------------------------------------------------------ #

@auth_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            log_user_event(
                event_type="login_attempt",
                actor_username=username or "anonymous",
                actor_role="guest",
                status="FAILED",
                details={"reason": "missing_credentials"},
            )
            flash(t("Veuillez fournir un nom d'utilisateur et un mot de passe."), "error")
        else:
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                if user.is_active:
                    user.last_login = datetime.utcnow()
                    db.session.commit()
                    login_user(user, remember=bool(request.form.get("remember")))
                    log_user_event(
                        event_type="login",
                        actor_username=user.username,
                        actor_role=(user.role.name if user.role else "user"),
                        status="SUCCESS",
                    )
                    flash(t("Connexion réussie !"), "success")
                    next_page = request.args.get("next")
                    return redirect(next_page or url_for("dashboard.index"))
                else:
                    log_user_event(
                        event_type="login_attempt",
                        actor_username=user.username,
                        actor_role=(user.role.name if user.role else "user"),
                        status="FAILED",
                        details={"reason": "account_disabled"},
                    )
                    flash(t("Compte désactivé."), "error")
            else:
                log_user_event(
                    event_type="login_attempt",
                    actor_username=username,
                    actor_role=(user.role.name if user and user.role else "guest"),
                    status="FAILED",
                    details={"reason": "invalid_credentials"},
                )
                flash(t("Nom d'utilisateur ou mot de passe incorrect."), "error")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    log_user_event(
        event_type="logout",
        actor_username=current_user.username,
        actor_role=(current_user.role.name if current_user.role else "user"),
        status="SUCCESS",
    )
    logout_user()
    flash(t("Vous avez été déconnecté."), "info")
    return redirect(url_for("auth.login"))


# ------------------------------------------------------------------ #
#  Changement de mot de passe                                        #
# ------------------------------------------------------------------ #

@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            log_user_event(
                event_type="change_password",
                actor_username=current_user.username,
                actor_role=(current_user.role.name if current_user.role else "user"),
                status="FAILED",
                details={"reason": "wrong_current_password"},
            )
            flash(t("Le mot de passe actuel est incorrect."), "error")
            return redirect(url_for("auth.change_password"))

        if new_password != confirm_password:
            log_user_event(
                event_type="change_password",
                actor_username=current_user.username,
                actor_role=(current_user.role.name if current_user.role else "user"),
                status="FAILED",
                details={"reason": "password_mismatch"},
            )
            flash(t("Les nouveaux mots de passe ne correspondent pas."), "error")
            return redirect(url_for("auth.change_password"))

        if current_user.check_password(new_password):
            log_user_event(
                event_type="change_password",
                actor_username=current_user.username,
                actor_role=(current_user.role.name if current_user.role else "user"),
                status="FAILED",
                details={"reason": "password_reuse"},
            )
            flash(t("Le nouveau mot de passe doit être différent de l'ancien."), "error")
            return redirect(url_for("auth.change_password"))

        errors = AuthService.validate_password(new_password)
        if errors:
            log_user_event(
                event_type="change_password",
                actor_username=current_user.username,
                actor_role=(current_user.role.name if current_user.role else "user"),
                status="FAILED",
                details={"reason": "password_policy", "errors": errors},
            )
            flash(" ".join(errors), "error")
            return redirect(url_for("auth.change_password"))

        current_user.set_password(new_password)
        db.session.commit()
        AuthService.send_password_changed_email(current_user.email, current_user.username)
        log_user_event(
            event_type="change_password",
            actor_username=current_user.username,
            actor_role=(current_user.role.name if current_user.role else "user"),
            status="SUCCESS",
        )
        flash(t("Mot de passe modifié avec succès."), "success")
        return redirect(url_for("dashboard.index"))

    return render_template("auth/change_password.html")


# ------------------------------------------------------------------ #
#  Mot de passe oublié / reset                                       #
# ------------------------------------------------------------------ #

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        sent = AuthService().send_reset_email(email)
        log_user_event(
            event_type="forgot_password",
            actor_username=email or "anonymous",
            actor_role="guest",
            status="SUCCESS" if sent else "FAILED",
        )
        # Message neutre côté sécurité, mais on informe en cas d'échec technique global.
        if sent:
            flash(t("Si cet e-mail existe, un lien de réinitialisation a été envoyé."), "info")
        else:
            flash(
                t(
                    "Si cet e-mail existe, un lien de réinitialisation a été envoyé. "
                    "Si vous ne recevez rien, contactez l'administrateur."
                ),
                "warning",
            )
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if new_password != confirm_password:
            flash(t("Les mots de passe ne correspondent pas."), "error")
            return redirect(url_for("auth.reset_password", token=token))

        try:
            AuthService().reset_password(token, new_password)
            log_user_event(
                event_type="reset_password",
                actor_username="anonymous",
                actor_role="guest",
                status="SUCCESS",
            )
            flash(t("Mot de passe réinitialisé avec succès. Veuillez vous connecter."), "success")
            return redirect(url_for("auth.login"))
        except Exception as e:
            log_user_event(
                event_type="reset_password",
                actor_username="anonymous",
                actor_role="guest",
                status="FAILED",
                details={"reason": str(e)[:200]},
            )
            flash(str(e), "error")
            return redirect(url_for("auth.reset_password", token=token))

    return render_template("auth/reset_password.html", token=token)


# ------------------------------------------------------------------ #
#  Administration des utilisateurs                                   #
# ------------------------------------------------------------------ #

@auth_bp.route("/admin/users", methods=["GET"])
@login_required
def admin_users():
    if current_user.role.name != "Admin":
        flash(t("Accès refusé."), "error")
        return redirect(url_for("dashboard.index"))
    users = User.query.all()
    roles = Role.query.all()
    return render_template("admin/manage_users.html", users=users, roles=roles)


@auth_bp.route("/admin/users/create", methods=["POST"])
@login_required
def admin_create_user():
    if current_user.role.name != "Admin":
        log_user_event(
            event_type="admin_create_user",
            actor_username=current_user.username,
            actor_role=(current_user.role.name if current_user.role else "user"),
            status="FAILED",
            details={"reason": "access_denied"},
        )
        flash(t("Accès refusé."), "error")
        return redirect(url_for("dashboard.index"))

    try:
        created_username = request.form.get("username", "").strip()
        AuthService.create_user(
            username=created_username,
            email=request.form.get("email", "").strip(),
            password=request.form.get("password", ""),
            role_id=int(request.form.get("role_id", 0)),
        )
        log_user_event(
            event_type="admin_create_user",
            actor_username=current_user.username,
            actor_role=(current_user.role.name if current_user.role else "user"),
            status="SUCCESS",
            details={"target": created_username},
        )
        flash(t("Utilisateur créé avec succès."), "success")
    except Exception as e:
        log_user_event(
            event_type="admin_create_user",
            actor_username=current_user.username,
            actor_role=(current_user.role.name if current_user.role else "user"),
            status="FAILED",
            details={"reason": str(e)[:200]},
        )
        flash(str(e), "error")

    return redirect(url_for("auth.admin_users"))


@auth_bp.route("/admin/users/<int:user_id>/edit", methods=["POST"])
@login_required
def admin_edit_user(user_id: int):
    if current_user.role.name != "Admin":
        log_user_event(
            event_type="admin_edit_user",
            actor_username=current_user.username,
            actor_role=(current_user.role.name if current_user.role else "user"),
            status="FAILED",
            details={"reason": "access_denied", "target_id": user_id},
        )
        flash(t("Accès refusé."), "error")
        return redirect(url_for("dashboard.index"))

    try:
        AuthService.update_user(user_id, request.form.to_dict())
        log_user_event(
            event_type="admin_edit_user",
            actor_username=current_user.username,
            actor_role=(current_user.role.name if current_user.role else "user"),
            status="SUCCESS",
            details={"target_id": user_id},
        )
        flash(t("Utilisateur mis à jour."), "success")
    except Exception as e:
        log_user_event(
            event_type="admin_edit_user",
            actor_username=current_user.username,
            actor_role=(current_user.role.name if current_user.role else "user"),
            status="FAILED",
            details={"target_id": user_id, "reason": str(e)[:200]},
        )
        flash(str(e), "error")

    return redirect(url_for("auth.admin_users"))


@auth_bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
def admin_delete_user(user_id: int):
    if current_user.role.name != "Admin":
        log_user_event(
            event_type="admin_delete_user",
            actor_username=current_user.username,
            actor_role=(current_user.role.name if current_user.role else "user"),
            status="FAILED",
            details={"reason": "access_denied", "target_id": user_id},
        )
        flash(t("Accès refusé."), "error")
        return redirect(url_for("dashboard.index"))

    try:
        AuthService.delete_user(user_id)
        log_user_event(
            event_type="admin_delete_user",
            actor_username=current_user.username,
            actor_role=(current_user.role.name if current_user.role else "user"),
            status="SUCCESS",
            details={"target_id": user_id},
        )
        flash(t("Utilisateur supprimé."), "success")
    except Exception as e:
        log_user_event(
            event_type="admin_delete_user",
            actor_username=current_user.username,
            actor_role=(current_user.role.name if current_user.role else "user"),
            status="FAILED",
            details={"target_id": user_id, "reason": str(e)[:200]},
        )
        flash(str(e), "error")

    return redirect(url_for("auth.admin_users"))


@auth_bp.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@login_required
def admin_toggle_user(user_id: int):
    if current_user.role.name != "Admin":
        log_user_event(
            event_type="admin_toggle_user",
            actor_username=current_user.username,
            actor_role=(current_user.role.name if current_user.role else "user"),
            status="FAILED",
            details={"reason": "access_denied", "target_id": user_id},
        )
        flash(t("Accès refusé."), "error")
        return redirect(url_for("dashboard.index"))

    try:
        user = AuthService.toggle_user_status(user_id)
        status = "activé" if user.is_active else "désactivé"
        log_user_event(
            event_type="admin_toggle_user",
            actor_username=current_user.username,
            actor_role=(current_user.role.name if current_user.role else "user"),
            status="SUCCESS",
            details={"target_id": user_id, "new_state": "active" if user.is_active else "disabled"},
        )
        flash(t(f"Utilisateur {status}."), "success")
    except Exception as e:
        log_user_event(
            event_type="admin_toggle_user",
            actor_username=current_user.username,
            actor_role=(current_user.role.name if current_user.role else "user"),
            status="FAILED",
            details={"target_id": user_id, "reason": str(e)[:200]},
        )
        flash(str(e), "error")

    return redirect(url_for("auth.admin_users"))

@auth_bp.route("/admin/roles", methods=["GET"])
@login_required
def admin_roles():
    """Page de gestion des rôles et permissions."""
    if current_user.role.name != "Admin":
        flash(t("Accès refusé."), "error")
        return redirect(url_for("dashboard.index"))
    return render_template("admin/manage_roles.html")
