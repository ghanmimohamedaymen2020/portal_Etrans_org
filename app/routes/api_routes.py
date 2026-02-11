from flask import jsonify, request
from flask_login import login_required, current_user
from app import db
from app.models import Dossier, AvisArrivee, User
from app.utils import token_required
from app.routes import api_bp
from sqlalchemy import text

@api_bp.route('/dossiers', methods=['GET'])
@login_required
def get_dossiers():
    """Récupérer la liste des dossiers"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    pagination = Dossier.query.paginate(page=page, per_page=per_page)
    
    dossiers = [{
        'id': d.id,
        'numero': d.numero,
        'type_conteneur': d.type_conteneur,
        'date_arrivee': d.date_arrivee.isoformat(),
        'status': d.status,
        'avis_envoye': d.avis_envoye,
        'contient_imo': d.contient_imo
    } for d in pagination.items]
    
    return jsonify({
        'dossiers': dossiers,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    })

@api_bp.route('/dossiers/<int:dossier_id>', methods=['GET'])
@login_required
def get_dossier(dossier_id):
    """Récupérer un dossier spécifique"""
    dossier = Dossier.query.get_or_404(dossier_id)
    
    return jsonify({
        'id': dossier.id,
        'numero': dossier.numero,
        'type_conteneur': dossier.type_conteneur,
        'date_arrivee': dossier.date_arrivee.isoformat(),
        'status': dossier.status,
        'avis_envoye': dossier.avis_envoye,
        'contient_imo': dossier.contient_imo,
        'validé_transit': dossier.validé_transit,
        'validé_documentation': dossier.validé_documentation
    })

@api_bp.route('/dossiers', methods=['POST'])
@login_required
def create_dossier():
    """Créer un nouveau dossier"""
    data = request.get_json()
    
    dossier = Dossier(
        numero=data.get('numero'),
        type_conteneur=data.get('type_conteneur'),
        date_arrivee=data.get('date_arrivee'),
        contient_imo=data.get('contient_imo', False),
        contient_escale=data.get('contient_escale', False),
        contient_fret=data.get('contient_fret', False)
    )
    
    db.session.add(dossier)
    db.session.commit()
    
    return jsonify({
        'message': 'Dossier créé',
        'id': dossier.id
    }), 201

@api_bp.route('/dossiers/<int:dossier_id>/valider-transit', methods=['PUT'])
@login_required
def valider_transit(dossier_id):
    """Valider un dossier par le service Transit"""
    dossier = Dossier.query.get_or_404(dossier_id)
    dossier.validé_transit = True
    
    # Si tous les critères sont remplis, marquer comme à envoyer
    if dossier.validé_transit and dossier.validé_documentation and dossier.contient_escale:
        dossier.avis_a_envoyer = True
    
    db.session.commit()
    
    return jsonify({'message': 'Dossier validé par Transit'})

@api_bp.route('/dossiers/<int:dossier_id>/valider-doc', methods=['PUT'])
@login_required
def valider_doc(dossier_id):
    """Valider un dossier par la Documentation"""
    dossier = Dossier.query.get_or_404(dossier_id)
    dossier.validé_documentation = True
    
    # Si tous les critères sont remplis, marquer comme à envoyer
    if dossier.validé_transit and dossier.validé_documentation and dossier.contient_escale:
        dossier.avis_a_envoyer = True
    
    db.session.commit()
    
    return jsonify({'message': 'Dossier validé par Documentation'})

@api_bp.route('/avis/<int:avis_id>/envoyer', methods=['PUT'])
@login_required
def envoyer_avis(avis_id):
    """Envoyer un avis d'arrivée"""
    avis = AvisArrivee.query.get_or_404(avis_id)
    avis.statut = 'envoyé'
    avis.dossier.avis_envoye = True
    
    from datetime import datetime
    avis.date_envoi = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'message': 'Avis envoyé'})

@api_bp.route('/profile', methods=['GET'])
@login_required
def get_profile():
    """Récupérer le profil de l'utilisateur actuel"""
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'role': current_user.role.name,
        'is_active': current_user.is_active,
        'created_at': current_user.created_at.isoformat(),
        'last_login': current_user.last_login.isoformat() if current_user.last_login else None
    })

@api_bp.route('/factures/aa-detail', methods=['GET'])
@login_required
def get_factures_aa_detail():
    """Récupérer les factures depuis View_AA_AvecFacture"""
    limit = request.args.get('limit', 0, type=int)
    limit = max(0, min(limit, 100000))
    top_clause = f"TOP {limit}" if limit > 0 else ""

    desired_columns = [
        'AA_H_ID',
        'AA_H_Reference',
        'AA_H_DateProcess',
        'AA_H_Dossier',
        'AA_H_NomClient',
        'AA_H_ETA',
        'AA_H_House',
        'AA_H_Service',
        'AA_H_IdCommercial',
        'AA_H_NomCommercial',
        'AA_H_NumFacture'
    ]
    total_column = 'FF_T_TotalTTC'

    try:
        columns = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = 'View_AA_AvecFacture'
        """)).scalars().all()
        column_set = {c for c in columns}

        selected_columns = [c for c in desired_columns if c in column_set]
        if not selected_columns:
            return jsonify({
                'factures': [],
                'total': 0,
                'error': "Aucune colonne attendue trouvée dans View_AA_AvecFacture"
            }), 500

        order_by = 'AA_H_DateProcess' if 'AA_H_DateProcess' in column_set else selected_columns[0]

        total_exists = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = 'View_FF_Total'
              AND COLUMN_NAME = :col
        """), {'col': total_column}).scalars().first() is not None

        select_parts = [f"a.{col}" for col in selected_columns]
        if total_exists:
            select_parts.append(f"t.{total_column} AS total_ttc")

        sql = text(f"""
            SELECT {top_clause}
                {', '.join(select_parts)}
            FROM [dbo].[View_AA_AvecFacture] a
            LEFT JOIN [dbo].[View_FF_Total] t
              ON t.FF_T_NumFact = a.AA_H_NumFacture
            ORDER BY a.{order_by} DESC
        """)

        rows = db.session.execute(sql).mappings().all()
        factures = [
            {
                'reference': row.get('AA_H_Reference'),
                'date_process': row.get('AA_H_DateProcess'),
                'dossier': row.get('AA_H_Dossier'),
                'nom_client': row.get('AA_H_NomClient'),
                'eta': row.get('AA_H_ETA'),
                'house': row.get('AA_H_House'),
                'service': row.get('AA_H_Service'),
                'id_commercial': row.get('AA_H_IdCommercial'),
                'nom_commercial': row.get('AA_H_NomCommercial'),
                'num_facture': row.get('AA_H_NumFacture'),
                'total_ttc': row.get('total_ttc')
            }
            for row in rows
        ]

        return jsonify({'factures': factures, 'total': len(factures)})
    except Exception as exc:
        return jsonify({'factures': [], 'total': 0, 'error': str(exc)}), 500

@api_bp.route('/factures/ff-activity', methods=['GET'])
@login_required
def get_ff_activity_totals():
    """Sommes par activité depuis View_FF_Entete et View_FF_Total."""
    year = request.args.get('year', type=int)
    if not year:
        from datetime import datetime
        year = datetime.utcnow().year

    required_aa = {'AA_H_NumFacture', 'AA_H_DateProcess'}
    required_entete = {'FF_H_TypeFacture', 'FF_H_NumFact', 'FF_H_TypeFactRect'}
    required_total = {'FF_T_NumFact', 'FF_T_TotalSoumis', 'FF_T_TotalNonSoumis'}

    try:
        entete_cols = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = 'View_FF_Entete'
        """)).scalars().all()
        total_cols = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = 'View_FF_Total'
        """)).scalars().all()

        entete_set = {c for c in entete_cols}
        total_set = {c for c in total_cols}

        if not required_entete.issubset(entete_set):
            return jsonify({
                'error': "Colonnes manquantes dans View_FF_Entete",
                'missing': sorted(required_entete - entete_set)
            }), 500

        if not required_total.issubset(total_set):
            return jsonify({
                'error': "Colonnes manquantes dans View_FF_Total",
                'missing': sorted(required_total - total_set)
            }), 500

        entete_cols = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = 'View_FF_Entete'
        """)).scalars().all()
        total_cols = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = 'View_FF_Total'
        """)).scalars().all()
        aa_cols = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = 'View_AA_AvecFacture'
        """)).scalars().all()

        entete_set = {c for c in entete_cols}
        total_set = {c for c in total_cols}
        aa_set = {c for c in aa_cols}

        if not required_entete.issubset(entete_set):
            return jsonify({
                'error': "Colonnes manquantes dans View_FF_Entete",
                'missing': sorted(required_entete - entete_set)
            }), 500

        if not required_total.issubset(total_set):
            return jsonify({
                'error': "Colonnes manquantes dans View_FF_Total",
                'missing': sorted(required_total - total_set)
            }), 500

        if not required_aa.issubset(aa_set):
            return jsonify({
                'error': "Colonnes manquantes dans View_AA_AvecFacture",
                'missing': sorted(required_aa - aa_set)
            }), 500

        sql = text("""
            SELECT
                SUM(CASE WHEN UPPER(LTRIM(RTRIM(e.FF_H_TypeFacture))) = 'T'
                         THEN TRY_CONVERT(decimal(18,2), t.FF_T_TotalSoumis) + TRY_CONVERT(decimal(18,2), t.FF_T_TotalNonSoumis) ELSE 0 END) AS timbrage,
                SUM(CASE WHEN UPPER(LTRIM(RTRIM(e.FF_H_TypeFacture))) = 'M'
                         THEN TRY_CONVERT(decimal(18,2), t.FF_T_TotalSoumis) + TRY_CONVERT(decimal(18,2), t.FF_T_TotalNonSoumis) ELSE 0 END) AS magasinage,
                SUM(CASE WHEN UPPER(LTRIM(RTRIM(e.FF_H_TypeFacture))) = 'A'
                         THEN TRY_CONVERT(decimal(18,2), t.FF_T_TotalSoumis) + TRY_CONVERT(decimal(18,2), t.FF_T_TotalNonSoumis) ELSE 0 END) AS agent,
                SUM(CASE WHEN UPPER(LTRIM(RTRIM(e.FF_H_TypeFacture))) = 'S'
                         THEN TRY_CONVERT(decimal(18,2), t.FF_T_TotalSoumis) + TRY_CONVERT(decimal(18,2), t.FF_T_TotalNonSoumis) ELSE 0 END) AS seristari
            FROM [dbo].[View_FF_Entete] e
            JOIN [dbo].[View_FF_Total] t
              ON t.FF_T_NumFact = e.FF_H_NumFact
            LEFT JOIN [dbo].[View_AA_AvecFacture] a
              ON a.AA_H_NumFacture = t.FF_T_NumFact
            WHERE (e.FF_H_TypeFactRect IS NULL
               OR UPPER(LTRIM(RTRIM(e.FF_H_TypeFactRect))) <> 'CN')
              AND YEAR(COALESCE(a.AA_H_DateProcess, e.FF_H_DateProcess)) = :year
        """)

        row = db.session.execute(sql, {'year': year}).mappings().first() or {}
        return jsonify({
            'year': year,
            'timbrage': float(row.get('timbrage') or 0),
            'magasinage': float(row.get('magasinage') or 0),
            'agent': float(row.get('agent') or 0),
            'surestarie': float(row.get('seristari') or 0)
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@api_bp.route('/factures/ff-monthly', methods=['GET'])
@login_required
def get_ff_monthly_totals():
    """Chiffre d'affaires mensuel (année courante et précédente)."""
    year = request.args.get('year', type=int)
    if not year:
        from datetime import datetime
        year = datetime.utcnow().year

    required_aa = {'AA_H_NumFacture', 'AA_H_DateProcess'}
    required_total = {'FF_T_NumFact', 'FF_T_TotalSoumis', 'FF_T_TotalNonSoumis'}

    try:
        aa_cols = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = 'View_AA_AvecFacture'
        """)).scalars().all()
        total_cols = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = 'View_FF_Total'
        """)).scalars().all()

        aa_set = {c for c in aa_cols}
        total_set = {c for c in total_cols}

        if not required_aa.issubset(aa_set):
            return jsonify({
                'error': "Colonnes manquantes dans View_AA_AvecFacture",
                'missing': sorted(required_aa - aa_set)
            }), 500

        if not required_total.issubset(total_set):
            return jsonify({
                'error': "Colonnes manquantes dans View_FF_Total",
                'missing': sorted(required_total - total_set)
            }), 500

        sql = text("""
            SELECT
                MONTH(COALESCE(a.AA_H_DateProcess, e.FF_H_DateProcess)) AS month,
                SUM(TRY_CONVERT(decimal(18,2), t.FF_T_TotalSoumis)
                    + TRY_CONVERT(decimal(18,2), t.FF_T_TotalNonSoumis)) AS total,
                SUM(CASE WHEN UPPER(LTRIM(RTRIM(e.FF_H_TypeFacture))) = 'T'
                    THEN TRY_CONVERT(decimal(18,2), t.FF_T_TotalSoumis) + TRY_CONVERT(decimal(18,2), t.FF_T_TotalNonSoumis) ELSE 0 END) AS timbrage,
                SUM(CASE WHEN UPPER(LTRIM(RTRIM(e.FF_H_TypeFacture))) = 'M'
                    THEN TRY_CONVERT(decimal(18,2), t.FF_T_TotalSoumis) + TRY_CONVERT(decimal(18,2), t.FF_T_TotalNonSoumis) ELSE 0 END) AS magasinage,
                SUM(CASE WHEN UPPER(LTRIM(RTRIM(e.FF_H_TypeFacture))) = 'A'
                    THEN TRY_CONVERT(decimal(18,2), t.FF_T_TotalSoumis) + TRY_CONVERT(decimal(18,2), t.FF_T_TotalNonSoumis) ELSE 0 END) AS agent,
                SUM(CASE WHEN UPPER(LTRIM(RTRIM(e.FF_H_TypeFacture))) = 'S'
                    THEN TRY_CONVERT(decimal(18,2), t.FF_T_TotalSoumis) + TRY_CONVERT(decimal(18,2), t.FF_T_TotalNonSoumis) ELSE 0 END) AS surestarie
            FROM [dbo].[View_FF_Entete] e
            JOIN [dbo].[View_FF_Total] t
                ON t.FF_T_NumFact = e.FF_H_NumFact
            LEFT JOIN [dbo].[View_AA_AvecFacture] a
                ON a.AA_H_NumFacture = t.FF_T_NumFact
            WHERE YEAR(COALESCE(a.AA_H_DateProcess, e.FF_H_DateProcess)) = :year
            GROUP BY MONTH(COALESCE(a.AA_H_DateProcess, e.FF_H_DateProcess))
            ORDER BY MONTH(COALESCE(a.AA_H_DateProcess, e.FF_H_DateProcess))
        """)

        def build_series_and_activities(target_year):
            rows = db.session.execute(sql, {'year': target_year}).mappings().all()
            by_month = {int(r['month']): r for r in rows}
            totals = [float(by_month.get(m, {}).get('total') or 0) for m in range(1, 13)]
            activities = {
                'timbrage': [float(by_month.get(m, {}).get('timbrage') or 0) for m in range(1, 13)],
                'magasinage': [float(by_month.get(m, {}).get('magasinage') or 0) for m in range(1, 13)],
                'agent': [float(by_month.get(m, {}).get('agent') or 0) for m in range(1, 13)],
                'surestarie': [float(by_month.get(m, {}).get('surestarie') or 0) for m in range(1, 13)]
            }
            return totals, activities

        current_totals, current_activities = build_series_and_activities(year)
        previous_totals, previous_activities = build_series_and_activities(year - 1)

        return jsonify({
            'year': year,
            'current': current_totals,
            'previous': previous_totals,
            'activities': {
                'current': current_activities,
                'previous': previous_activities
            }
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@api_bp.route('/factures/ff-monthly-activity', methods=['GET'])
@login_required
def get_ff_monthly_activity_totals():
    """Totaux mensuels par activité (année courante et précédente).
    Retourne pour chaque activité un tableau de 12 valeurs (mois 1..12).
    """
    year = request.args.get('year', type=int)
    if not year:
        from datetime import datetime
        year = datetime.utcnow().year

    required_aa = {'AA_H_NumFacture', 'AA_H_DateProcess'}
    required_total = {'FF_T_NumFact', 'FF_T_TotalSoumis', 'FF_T_TotalNonSoumis'}
    required_entete = {'FF_H_NumFact', 'FF_H_TypeFacture'}

    try:
        aa_cols = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = 'View_AA_AvecFacture'
        """)).scalars().all()
        total_cols = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = 'View_FF_Total'
        """)).scalars().all()
        entete_cols = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = 'View_FF_Entete'
        """)).scalars().all()

        aa_set = {c for c in aa_cols}
        total_set = {c for c in total_cols}
        entete_set = {c for c in entete_cols}

        if not required_aa.issubset(aa_set):
            return jsonify({'error': "Colonnes manquantes dans View_AA_AvecFacture",
                            'missing': sorted(required_aa - aa_set)}), 500
        if not required_total.issubset(total_set):
            return jsonify({'error': "Colonnes manquantes dans View_FF_Total",
                            'missing': sorted(required_total - total_set)}), 500
        if not required_entete.issubset(entete_set):
            return jsonify({'error': "Colonnes manquantes dans View_FF_Entete",
                            'missing': sorted(required_entete - entete_set)}), 500

        sql = text("""
            SELECT
                MONTH(COALESCE(a.AA_H_DateProcess, e.FF_H_DateProcess)) AS month,
                SUM(CASE WHEN UPPER(LTRIM(RTRIM(e.FF_H_TypeFacture))) = 'T'
                    THEN TRY_CONVERT(decimal(18,2), t.FF_T_TotalSoumis) + TRY_CONVERT(decimal(18,2), t.FF_T_TotalNonSoumis) ELSE 0 END) AS timbrage,
                SUM(CASE WHEN UPPER(LTRIM(RTRIM(e.FF_H_TypeFacture))) = 'M'
                    THEN TRY_CONVERT(decimal(18,2), t.FF_T_TotalSoumis) + TRY_CONVERT(decimal(18,2), t.FF_T_TotalNonSoumis) ELSE 0 END) AS magasinage,
                SUM(CASE WHEN UPPER(LTRIM(RTRIM(e.FF_H_TypeFacture))) = 'A'
                    THEN TRY_CONVERT(decimal(18,2), t.FF_T_TotalSoumis) + TRY_CONVERT(decimal(18,2), t.FF_T_TotalNonSoumis) ELSE 0 END) AS agent,
                SUM(CASE WHEN UPPER(LTRIM(RTRIM(e.FF_H_TypeFacture))) = 'S'
                    THEN TRY_CONVERT(decimal(18,2), t.FF_T_TotalSoumis) + TRY_CONVERT(decimal(18,2), t.FF_T_TotalNonSoumis) ELSE 0 END) AS surestarie
            FROM [dbo].[View_FF_Entete] e
            JOIN [dbo].[View_FF_Total] t
              ON t.FF_T_NumFact = e.FF_H_NumFact
            LEFT JOIN [dbo].[View_AA_AvecFacture] a
              ON a.AA_H_NumFacture = t.FF_T_NumFact
            WHERE YEAR(COALESCE(a.AA_H_DateProcess, e.FF_H_DateProcess)) = :year
            GROUP BY MONTH(COALESCE(a.AA_H_DateProcess, e.FF_H_DateProcess))
            ORDER BY MONTH(COALESCE(a.AA_H_DateProcess, e.FF_H_DateProcess))
        """)

        def build_activity_series(target_year):
            rows = db.session.execute(sql, {'year': target_year}).mappings().all()
            by_month = {int(r['month']): r for r in rows}
            def get_list(key):
                return [float(by_month.get(m, {}).get(key) or 0) for m in range(1, 13)]
            return {
                'timbrage': get_list('timbrage'),
                'magasinage': get_list('magasinage'),
                'agent': get_list('agent'),
                'surestarie': get_list('surestarie')
            }

        return jsonify({
            'year': year,
            'current': build_activity_series(year),
            'previous': build_activity_series(year - 1)
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@api_bp.route('/freight/by-devise', methods=['GET'])
@login_required
def get_freight_by_devise():
    """Total marge sur fret par devise depuis View_FREIGHT."""
    required_cols = {'Devise', 'MontAchat', 'MontVente'}

@api_bp.route('/freight/items', methods=['GET'])
@login_required
def get_freight_items():
    """Liste des lignes de fret depuis View_FREIGHT."""
    required_cols = {
        'Devise', 'dossier', 'house', 'MontAchat', 'MontVente',
        'ETA', 'FournisseurNom', 'DateCreation', 'Ioe', 'PoC',
        'Refrence_AA', 'IdUtilisateur', 'EmailUtilisateur'
    }

    try:
        cols = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = 'View_FREIGHT'
        """)).scalars().all()
        col_set = {c for c in cols}

        if not required_cols.issubset(col_set):
            return jsonify({
                'error': "Colonnes manquantes dans View_FREIGHT",
                'missing': sorted(required_cols - col_set)
            }), 500

        sql = text("""
            SELECT
                Devise,
                dossier,
                house,
                MontAchat,
                MontVente,
                ETA,
                FournisseurNom,
                DateCreation,
                Ioe,
                PoC,
                Refrence_AA,
                IdUtilisateur,
                EmailUtilisateur
            FROM [dbo].[View_FREIGHT]
        """)

        rows = db.session.execute(sql).mappings().all()
        items = [
            {
                'devise': row.get('Devise'),
                'dossier': row.get('dossier'),
                'house': row.get('house'),
                'mont_achat': row.get('MontAchat'),
                'mont_vente': row.get('MontVente'),
                'eta': row.get('ETA'),
                'fournisseur': row.get('FournisseurNom'),
                'date_creation': row.get('DateCreation'),
                'ioe': row.get('Ioe'),
                'poc': row.get('PoC'),
                'reference_aa': row.get('Refrence_AA'),
                'id_utilisateur': row.get('IdUtilisateur'),
                'email_utilisateur': row.get('EmailUtilisateur')
            }
            for row in rows
        ]

        return jsonify({'items': items, 'total': len(items)})
    except Exception as exc:
        return jsonify({'items': [], 'total': 0, 'error': str(exc)}), 500
