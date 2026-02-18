from flask import jsonify, request, Response
import io
import csv
from flask_login import login_required, current_user
from app import db
from app.utils import get_agent_monthly_by_year, get_agent_totals_for_month, get_invoice_monthly_and_annual
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
        'AA_H_NomCommercial'
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

        # If View_AA_SansFacture exists, prefer returning its top 1000 rows
        sans_cols = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'View_AA_SansFacture'
        """)).scalars().all()
        if sans_cols:
            # select exactly the columns requested by the user
            select_list = [
                'AA_H_Reference','AA_H_DateProcess','AA_H_Dossier','AA_H_NomClient',
                'AA_H_Adresse_1','AA_H_Adresse_2','AA_H_Adresse_3','AA_H_TVA',
                'AA_H_DateSuspTVA_Du','AA_H_DateSuspTVA_Au','AA_H_IdBar','AA_H_Voyage',
                'AA_H_Navire','AA_H_PPOL','AA_H_POL','AA_H_DPOL','AA_H_PPOD','AA_H_POD',
                'AA_H_DPOD','AA_H_ETA','AA_H_Traduccion','AA_H_House','AA_H_MasterBL',
                'AA_H_Service','AA_H_Escale','AA_H_Rubrique','AA_H_IdCommercial',
                'AA_H_NomCommercial','AA_H_EmailCommercial','AA_H_IdUtilisateur',
                'AA_H_EmailUtilisateur','AA_H_Trans_PC_ClientFinal','AA_H_NomClientFinal',
                'AA_H_NumSuspTVA','AA_H_NumFacture'
            ]
            # ensure columns exist in the view
            available = {c for c in sans_cols}
            select_parts = [c for c in select_list if c in available]
            # attempt to include AA totals from View_AA_Total when available
            aa_total_cols = db.session.execute(text("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'View_AA_Total'
            """)).scalars().all()
            aa_total_set = {c for c in aa_total_cols}
            aa_join_col = None
            # prefer referencing by AA_T_Reference if both sides exist
            if 'AA_T_Reference' in aa_total_set and 'AA_H_Reference' in available:
                aa_join_col = ('AA_T_Reference', 'AA_H_Reference')
            elif 'AA_T_NumFact' in aa_total_set and 'AA_H_NumFacture' in available:
                aa_join_col = ('AA_T_NumFact', 'AA_H_NumFacture')
            elif 'AA_T_NumFacture' in aa_total_set and 'AA_H_NumFacture' in available:
                aa_join_col = ('AA_T_NumFacture', 'AA_H_NumFacture')

            # include aa total select parts when present
            if 'AA_T_TotalNonSoumis' in aa_total_set:
                select_parts.append('at.AA_T_TotalNonSoumis AS aa_total_non_soumis')
            if 'AA_T_TotalSoumis' in aa_total_set:
                select_parts.append('at.AA_T_TotalSoumis AS aa_total_soumis')
            if 'AA_T_TotalTVA' in aa_total_set:
                select_parts.append('at.AA_T_TotalTVA AS aa_total_tva')

            if select_parts:
                join_clause = ''
                if aa_join_col:
                    join_clause = f" LEFT JOIN [dbo].[View_AA_Total] at ON at.{aa_join_col[0]} = a.{aa_join_col[1]}"
                sql = text(f"SELECT TOP 1000 {', '.join(select_parts)} FROM [dbo].[View_AA_SansFacture] a {join_clause} ORDER BY AA_H_DateProcess DESC")
                rows = db.session.execute(sql).mappings().all()
                factures = [dict(r) for r in rows]
                return jsonify({'factures': factures, 'total': len(factures)})

        selected_columns = [c for c in desired_columns if c in column_set]
        # If the AA view is not available or doesn't contain expected columns,
        # fall back to returning rows from View_FF_Entete + View_FF_Total so the
        # frontend lists (not-stamped / invoices) can still show data based on FF.
        try:
            # Try unqualified views first
            total_du_mois = 0.0
            total_global = 0.0
            total_year = 0.0
            count_du_mois = 0
            count_global = 0

            def try_query_sum(view_sql, col_name='s', count=False):
                try:
                    if count:
                        q = db.session.execute(text(view_sql)).mappings().first()
                        return float(q.get(col_name) or 0), int(q.get('cnt') or 0)
                    else:
                        q = db.session.execute(text(view_sql)).mappings().first()
                        return float(q.get(col_name) or 0), None
                except Exception:
                    return None, None

            # prefer month total from View_FREIGHT_TND_DuMois using MontantTTC
            s, c = try_query_sum("SELECT SUM(ISNULL(FF_D_MontantTTC,0)) AS s, COUNT(1) AS cnt FROM [dbo].[View_FREIGHT_TND_DuMois]", count=True)
            if s is None:
                # try fully qualified DB name (some installations use Dashboard.dbo)
                s, c = try_query_sum("SELECT SUM(ISNULL(FF_D_MontantTTC,0)) AS s, COUNT(1) AS cnt FROM [Dashboard].[dbo].[View_FREIGHT_TND_DuMois]", count=True)
            if s is not None:
                total_du_mois = s
                count_du_mois = c or 0

            # global totals using FF_D_MontantTTC (use TTC for yearly/global sums too)
            s, c = try_query_sum("SELECT SUM(ISNULL(FF_D_MontantTTC,0)) AS s, COUNT(1) AS cnt FROM [dbo].[View_FREIGHT_TND]", count=True)
            if s is None:
                s, c = try_query_sum("SELECT SUM(ISNULL(FF_D_MontantTTC,0)) AS s, COUNT(1) AS cnt FROM [Dashboard].[dbo].[View_FREIGHT_TND]", count=True)
            if s is not None:
                total_global = s
                count_global = c or 0
                if year:
                    # try yearly sum from the global view using MontantTTC
                    try:
                        r3 = db.session.execute(text("SELECT SUM(ISNULL(FF_D_MontantTTC,0)) AS s FROM [dbo].[View_FREIGHT_TND] WHERE YEAR(FF_H_DateProcess) = :year"), {'year': year}).mappings().first()
                        if r3 and r3.get('s') is not None:
                            total_year = float(r3.get('s') or 0)
                    except Exception:
                        try:
                            r3 = db.session.execute(text("SELECT SUM(ISNULL(FF_D_MontantTTC,0)) AS s FROM [Dashboard].[dbo].[View_FREIGHT_TND] WHERE YEAR(FF_H_DateProcess) = :year"), {'year': year}).mappings().first()
                            if r3 and r3.get('s') is not None:
                                total_year = float(r3.get('s') or 0)
                        except Exception:
                            total_year = 0.0

            out = {'total_du_mois': total_du_mois, 'total_global': total_global, 'total_year': total_year,
                   'count_du_mois': count_du_mois, 'count_global': count_global}
            if request.args.get('debug'):
                samples = {}
                if count_du_mois > 0:
                    rows_sample = db.session.execute(text("SELECT TOP 20 FF_D_NumFact, FF_H_DateProcess, FF_D_Dossier, FF_D_House, FF_D_MontantTTC FROM [dbo].[View_FREIGHT_TND_DuMois] ORDER BY FF_H_DateProcess DESC")).mappings().all()
                    samples['du_mois'] = [dict(r) for r in rows_sample]
                if count_global > 0:
                    rows_sample = db.session.execute(text("SELECT TOP 20 FF_D_NumFact, FF_H_DateProcess, FF_D_Dossier, FF_D_House, FF_D_MontantHT_TND FROM [dbo].[View_FREIGHT_TND] ORDER BY FF_H_DateProcess DESC")).mappings().all()
                    samples['global'] = [dict(r) for r in rows_sample]
                out['samples'] = samples
            return jsonify(out)
        except Exception as exc:
            # If anything fails while computing FF-based fallback totals, ignore
            # and continue with the AA-based logic below (or return empty rows).
            pass

        order_by = 'AA_H_DateProcess' if 'AA_H_DateProcess' in column_set else selected_columns[0]

        # Inspect available columns on View_FF_Total to include totals when present
        total_cols = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = 'View_FF_Total'
        """)).scalars().all()
        total_set = {c for c in total_cols}
        total_exists = total_column in total_set

        # Also check for AA totals (View_AA_Total) and include if available
        aa_total_cols = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = 'View_AA_Total'
        """)).scalars().all()
        aa_total_set = {c for c in aa_total_cols}

        select_parts = [f"a.{col}" for col in selected_columns]
        if total_exists:
            select_parts.append(f"t.{total_column} AS total_ttc")
        # Add detailed FF total columns if present
        if 'FF_T_TotalNonSoumis' in total_set:
            select_parts.append('t.FF_T_TotalNonSoumis AS ff_total_non_soumis')
        if 'FF_T_TotalSoumis' in total_set:
            select_parts.append('t.FF_T_TotalSoumis AS ff_total_soumis')
        if 'FF_T_TotalTVA' in total_set:
            select_parts.append('t.FF_T_TotalTVA AS ff_total_tva')

        # Determine join column name in View_AA_Total (could be AA_T_NumFact or AA_T_NumFacture)
        aa_join_col = None
        if 'AA_T_NumFact' in aa_total_set:
            aa_join_col = 'AA_T_NumFact'
        elif 'AA_T_NumFacture' in aa_total_set:
            aa_join_col = 'AA_T_NumFacture'

        # include AA totals if present and we have a join key
        if aa_join_col:
            if 'AA_T_TotalNonSoumis' in aa_total_set:
                select_parts.append(f'at.AA_T_TotalNonSoumis AS aa_total_non_soumis')
            if 'AA_T_TotalSoumis' in aa_total_set:
                select_parts.append(f'at.AA_T_TotalSoumis AS aa_total_soumis')
            if 'AA_T_TotalTVA' in aa_total_set:
                select_parts.append(f'at.AA_T_TotalTVA AS aa_total_tva')
        # Build optional join to View_AA_Total using the detected join column name
        join_at_clause = ''
        if aa_join_col:
            join_at_clause = f"LEFT JOIN [dbo].[View_AA_Total] at ON at.{aa_join_col} = a.AA_H_NumFacture"

        sql = text(f"""
            SELECT {top_clause}
                {', '.join(select_parts)}
            FROM [dbo].[View_AA_AvecFacture] a
            LEFT JOIN [dbo].[View_FF_Total] t
              ON t.FF_T_NumFact = a.AA_H_NumFacture
            {join_at_clause}
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
                
                'total_ttc': row.get('total_ttc'),
                'ff_total_non_soumis': row.get('ff_total_non_soumis'),
                'ff_total_soumis': row.get('ff_total_soumis'),
                'ff_total_tva': row.get('ff_total_tva'),
                'aa_total_non_soumis': row.get('aa_total_non_soumis'),
                'aa_total_soumis': row.get('aa_total_soumis'),
                'aa_total_tva': row.get('aa_total_tva')
            }
            for row in rows
        ]

        return jsonify({'factures': factures, 'total': len(factures)})
    except Exception as exc:
        return jsonify({'factures': [], 'total': 0, 'error': str(exc)}), 500


@api_bp.route('/factures/details-aa', methods=['GET'])
@login_required
def get_aa_details_by_reference():
    """Return detail rows from View_AA_Detail for a given AA reference."""
    ref = request.args.get('reference')
    if not ref:
        return jsonify({'details': [], 'error': 'Missing reference parameter'}), 400
    try:
        # Inspect columns of View_AA_Detail to build a safe WHERE clause
        detail_cols = db.session.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='View_AA_Detail'
        """)).scalars().all()
        available = {c for c in detail_cols}
        # candidate reference columns
        candidates = ['AA_D_Reference','AA_D_NumAvis','AA_D_NumFacture','AA_D_Ref','AA_D_Num']
        where_cols = [c for c in candidates if c in available]
        if not where_cols:
            # fallback: return empty
            return jsonify({'details': []})
        conditions = ' OR '.join([f"{col} = :ref" for col in where_cols])
        sql = text(f"SELECT * FROM [dbo].[View_AA_Detail] WHERE {conditions} ORDER BY 1")
        rows = db.session.execute(sql, {'ref': ref}).mappings().all()
        details = [dict(r) for r in rows]
        return jsonify({'details': details, 'count': len(details)})
    except Exception as exc:
        return jsonify({'details': [], 'error': str(exc)}), 500

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


@api_bp.route('/factures/ca-activite', methods=['GET'])
@login_required
def get_ca_par_activite():
    """Chiffre d'affaires par activité (group by TypeService) using View_FF_Entete + View_FF_Detail.
    Accepts optional `year` query param (defaults to current year).
    """
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    if not year:
        from datetime import datetime
        year = datetime.utcnow().year

    # required columns to compute provided SQL
    required_entete = {'FF_H_TypeFacture', 'FF_H_NumFact', 'FF_H_DateProcess'}
    # FF_D_MontantHT_TND may be missing; we'll fall back to (TotalTTC - TotalTVA)
    required_detail = {'FF_D_NumFact', 'FF_D_Devise', 'FF_D_Montant', 'FF_D_MontantTVA', 'FF_D_MontantTTC'}

    # CA by activity calculations removed by user request — return empty rows.
    return jsonify({'year': year, 'rows': []})


@api_bp.route('/factures/ca-activite-total', methods=['GET'])
@login_required
def get_ca_activite_total():
    """Retourne les totaux agrégés (ht, soumis, non_soumis, tva, ttc) par activité
    ou pour un type spécifique si `type` est fourni. Paramètres: year, month, type.
    """
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    req_type = request.args.get('type')
    if not year:
        from datetime import datetime
        year = datetime.utcnow().year

    # CA-activite-total calculations removed by user request — return empty.
    return jsonify({'year': year, 'month': month, 'rows': []})


@api_bp.route('/factures/agent-totals', methods=['GET'])
@login_required
def get_agent_totals():
    """Retourne la somme TTC par devise (EUR, USD) pour les factures Agent.
    Params: year (opt), month (opt). Par défaut mois/année courants.
    """
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)
    if month is None or year is None:
        from datetime import datetime
        now = datetime.utcnow()
        if month is None:
            month = now.month
        if year is None:
            year = now.year

    try:
        # protective check for required views/columns
        detail_cols = db.session.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='View_FF_Detail'
        """)).scalars().all()
        entete_cols = db.session.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='View_FF_Entete'
        """)).scalars().all()
        if not {'FF_D_Devise','FF_D_MontantTTC','FF_D_NumFact'}.issubset({c for c in detail_cols}):
            return jsonify({'error':'Colonnes manquantes dans View_FF_Detail','missing': list(set(['FF_D_Devise','FF_D_MontantTTC','FF_D_NumFact']) - set(detail_cols))}), 500
        if 'FF_H_TypeFacture' not in entete_cols or 'FF_H_NumFact' not in entete_cols or 'FF_H_DateProcess' not in entete_cols:
            return jsonify({'error':'Colonnes manquantes dans View_FF_Entete','missing': []}), 500

        # use shared helper to ensure same logic as monthly histogram
        totals = get_agent_totals_for_month(db, year, month)
        return jsonify({'year': year, 'month': month, 'totals': totals})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/factures/agent-tnd-monthly', methods=['GET'])
@login_required
def get_agent_tnd_monthly():
    """Retourne la somme mensuelle des factures Agent en TND pour une année donnée.
    Params: year (opt). Retourne un tableau de 12 valeurs (mois 1..12) en TND.
    Utilise la vue `View_FREIGHT_TND` si disponible.
    """
    year = request.args.get('year', type=int)
    if not year:
        from datetime import datetime
        year = datetime.utcnow().year

    try:
        # check if View_FREIGHT_TND exists
        view_exists = db.session.execute(text("""
            SELECT 1 FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'View_FREIGHT_TND'
        """)).fetchone() is not None

        if not view_exists:
            return jsonify({'error': 'View_FREIGHT_TND not available on DB; cannot compute TND totals.'}), 404

        sql = text("""
            SELECT MONTH(FF_H_DateProcess) AS month,
                   SUM(ISNULL(FF_D_MontantTTC,0)) AS total_ttc_tnd
            FROM [dbo].[View_FREIGHT_TND]
            WHERE UPPER(LTRIM(RTRIM(FF_H_TypeFacture))) = 'A'
              AND YEAR(FF_H_DateProcess) = :year
            GROUP BY MONTH(FF_H_DateProcess)
            ORDER BY MONTH(FF_H_DateProcess)
        """)

        rows = db.session.execute(sql, {'year': year}).mappings().all()
        by_month = {int(r['month']): float(r['total_ttc_tnd'] or 0) for r in rows}
        series = [by_month.get(m, 0.0) for m in range(1, 13)]

        return jsonify({'year': year, 'monthly_tnd': series})
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

    # Calculations for monthly CA removed by user request.
    # Return empty structures so frontend does not attempt to plot computed series.
    try:
        empty_month = [0.0] * 12
        empty_activities = {
            'timbrage': empty_month.copy(),
            'magasinage': empty_month.copy(),
            'agent': empty_month.copy(),
            'surestarie': empty_month.copy()
        }
        return jsonify({
            'year': year,
            'current': empty_month,
            'previous': empty_month,
            'activities': {'current': empty_activities, 'previous': empty_activities},
            'agent_by_currency': {},
            'invoices_by_currency': {'current': {'series': {}, 'totals': {}}, 'previous': {'series': {}, 'totals': {}}},
            'note': 'Monthly CA calculations removed'
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

    # Monthly activity calculations removed by user request — return empty structures
    try:
        empty_month = [0.0] * 12
        empty_activities = {
            'timbrage': empty_month.copy(),
            'magasinage': empty_month.copy(),
            'agent': empty_month.copy(),
            'surestarie': empty_month.copy()
        }
        return jsonify({
            'year': year,
            'current': empty_activities,
            'previous': empty_activities,
            'note': 'Monthly activity calculations removed'
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/factures/invoices-by-currency', methods=['GET'])
@login_required
def get_invoices_by_currency():
    """Return distinct invoice numbers that have at least one detail row in the given currency.

    Query parameters:
    - currency (default 'TND')
    - year (optional, defaults to current year)
    """
    currency = (request.args.get('currency') or 'TND').strip().upper()
    year = request.args.get('year', type=int)
    if not year:
        from datetime import datetime
        year = datetime.utcnow().year

    try:
        sql = text("""
            SELECT DISTINCT COALESCE(a.AA_H_NumFacture, e.FF_H_NumFact) AS invoice_num,
                   UPPER(LTRIM(RTRIM(ISNULL(e.FF_H_TypeFacture, '')))) AS type_facture
            FROM dbo.View_FF_Entete e
            LEFT JOIN dbo.View_FF_Detail d ON e.FF_H_NumFact = d.FF_D_NumFact
            LEFT JOIN dbo.View_AA_AvecFacture a ON a.AA_H_NumFacture = e.FF_H_NumFact
            WHERE UPPER(ISNULL(d.FF_D_Devise,'N/A')) = :currency
              AND YEAR(COALESCE(a.AA_H_DateProcess, e.FF_H_DateProcess)) = :year
        """)
        rows = db.session.execute(sql, {'currency': currency, 'year': year}).mappings().all()
        invoices = []
        types = {}
        for r in rows:
            inv = r.get('invoice_num')
            t = (r.get('type_facture') or '').upper()
            if inv:
                invoices.append(inv)
                types[inv] = t
        return jsonify({'year': year, 'currency': currency, 'invoices': invoices, 'types': types})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/factures/invoices-by-currency/agent', methods=['GET'])
@login_required
def get_agent_invoices_by_currency():
    """Return invoice numbers of type 'A' (Agent) that have detail rows in the given currency."""
    currency = (request.args.get('currency') or 'TND').strip().upper()
    year = request.args.get('year', type=int)
    try:
        base_sql = """
            SELECT DISTINCT COALESCE(a.AA_H_NumFacture, e.FF_H_NumFact) AS invoice_num
            FROM dbo.View_FF_Entete e
            LEFT JOIN dbo.View_FF_Detail d ON e.FF_H_NumFact = d.FF_D_NumFact
            LEFT JOIN dbo.View_AA_AvecFacture a ON a.AA_H_NumFacture = e.FF_H_NumFact
            WHERE UPPER(ISNULL(d.FF_D_Devise,'N/A')) = :currency
              AND UPPER(LTRIM(RTRIM(ISNULL(e.FF_H_TypeFacture,'')))) = 'A'
        """
        params = {'currency': currency}
        if year:
            base_sql += "\n              AND YEAR(COALESCE(a.AA_H_DateProcess, e.FF_H_DateProcess)) = :year"
            params['year'] = year

        sql = text(base_sql)
        rows = db.session.execute(sql, params).mappings().all()
        invoices = [r.get('invoice_num') for r in rows if r.get('invoice_num')]
        out = {'currency': currency, 'agent_invoices': invoices}
        if year:
            out['year'] = year
        return jsonify(out)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/factures/details-by-invoices', methods=['GET'])
@login_required
def get_details_by_invoices():
    """Return detail rows from View_FF_Detail for given invoice numbers.

    Query param `invoices` should be a comma-separated list of invoice numbers.
    """
    invs = request.args.get('invoices')
    if not invs:
        return jsonify({'error': 'Missing invoices parameter'}), 400
    # split and sanitize
    parts = [p.strip() for p in invs.split(',') if p.strip()]
    if not parts:
        return jsonify({'error': 'No invoice numbers provided'}), 400
    try:
        # inspect available columns on the detail and entete views and choose a safe subset
        detail_cols = db.session.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'View_FF_Detail'
        """)).scalars().all()
        entete_cols = db.session.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'View_FF_Entete'
        """)).scalars().all()
        detail_set = {c for c in detail_cols}
        entete_set = {c for c in entete_cols}

        # preferred detail columns (alias mapping)
        preferred_detail = [
            ('FF_D_NumFact', 'invoice_num'),
            ('FF_D_Libelle', 'libelle'),
            ('FF_D_Devise', 'devise'),
            ('FF_D_Montant', 'montant'),
            ('FF_D_MontantTVA', 'montant_tva'),
            ('FF_D_MontantTTC', 'montant_ttc'),
            # include a few common variants for HT columns so we can use them as fallbacks
            ('FF_D_MontantHT_TND', 'montant_ht_tnd'),
            ('FF_D_MontantHT', 'montant_ht'),
            ('FF_D_Montant_HT_TND', 'montant_ht_tnd_alt')
        ]

        # preferred entete columns to provide context for detail rows
        preferred_entete = [
            ('FF_H_DateProcess', 'date_process'),
            ('FF_H_Dossier', 'dossier'),
            ('FF_H_NomClient', 'nom_client'),
            ('FF_H_TypeFacture', 'type_facture'),
            ('FF_H_ETA', 'eta'),
            ('FF_H_House', 'house'),
            ('FF_H_Service', 'service')
        ]

        select_parts = [f"d.{col} AS {alias}" for col, alias in preferred_detail if col in detail_set]
        # include entete columns by joining entete and prefixing with e.
        select_parts += [f"e.{col} AS {alias}" for col, alias in preferred_entete if col in entete_set]
        if not select_parts:
            return jsonify({'error': 'Aucune colonne disponible dans View_FF_Detail/View_FF_Entete pour afficher les détails'}), 500

        # build parameterized IN list
        placeholders = ','.join([f":inv{i}" for i in range(len(parts))])
        params = {f"inv{i}": parts[i] for i in range(len(parts))}
        sql = text(f"""
            SELECT {', '.join(select_parts)}
            FROM dbo.View_FF_Detail d
            LEFT JOIN dbo.View_FF_Entete e ON d.FF_D_NumFact = e.FF_H_NumFact
            WHERE d.FF_D_NumFact IN ({placeholders})
            ORDER BY d.FF_D_NumFact
        """)
        rows = db.session.execute(sql, params).mappings().all()
        details = [dict(r) for r in rows]

        # Post-process rows to populate montant_ht_tnd when it's missing.
        # Strategy:
        # 1) If montant_ht_tnd present, keep it.
        # 2) If 'montant_ht' present and devise is TND, use it.
        # 3) If both montant_ttc and montant_tva present and amounts are TND (or devise missing), compute montant_ttc - montant_tva.
        # 4) As a last resort, try to fetch converted HT from View_FREIGHT_TND for the same invoice number.
        freight_cache = {}
        for row in details:
            try:
                mh_tnd = row.get('montant_ht_tnd')
                # also consider alt column
                if mh_tnd in (None, '') and row.get('montant_ht_tnd_alt') not in (None, ''):
                    mh_tnd = row.get('montant_ht_tnd_alt')

                if mh_tnd not in (None, ''):
                    # ensure numeric
                    try:
                        row['montant_ht_tnd'] = float(mh_tnd)
                        continue
                    except Exception:
                        pass

                devise = (row.get('devise') or '').strip().upper()
                # prefer explicit montant_ht column if present
                montant_ht = row.get('montant_ht')
                if montant_ht not in (None, '') and devise == 'TND':
                    try:
                        row['montant_ht_tnd'] = float(montant_ht)
                        continue
                    except Exception:
                        pass

                # try compute from TTC - TVA when available
                montant_ttc = row.get('montant_ttc')
                montant_tva = row.get('montant_tva')
                type_fact = (row.get('type_facture') or '').strip().upper()
                # Compute HT when amounts available AND either currency is TND/unknown,
                # or it's a Timbrage invoice and currency is different from TND
                compute_ht = False
                if montant_ttc not in (None, '') and montant_tva not in (None, ''):
                    if devise in ('', 'TND'):
                        compute_ht = True
                    elif type_fact.startswith('T') and devise != 'TND':
                        compute_ht = True

                if compute_ht:
                    try:
                        row['montant_ht_tnd'] = float(montant_ttc) - float(montant_tva)
                        continue
                    except Exception:
                        pass

                # last resort: try to lookup converted HT in View_FREIGHT_TND by invoice
                inv = row.get('invoice_num')
                dossier = row.get('dossier')
                house = row.get('house')
                lookup_key = None
                # prefer dossier+house when available (more specific)
                if dossier and house:
                    lookup_key = f"{dossier}::{house}"
                elif inv:
                    lookup_key = inv

                if lookup_key:
                    if lookup_key not in freight_cache:
                        # try queries: by dossier+house first (if provided), else by invoice num
                        v = None
                        try:
                            if dossier and house:
                                q = db.session.execute(text("SELECT TOP 1 FF_D_MontantHT_TND FROM dbo.View_FREIGHT_TND WHERE FF_D_Dossier = :d AND FF_D_House = :h"), {'d': dossier, 'h': house}).mappings().first()
                                v = q.get('FF_D_MontantHT_TND') if q else None
                            if v in (None, '') and inv:
                                q2 = db.session.execute(text("SELECT TOP 1 FF_D_MontantHT_TND FROM dbo.View_FREIGHT_TND WHERE FF_D_NumFact = :inv"), {'inv': inv}).mappings().first()
                                v = q2.get('FF_D_MontantHT_TND') if q2 else None
                            # fallback to fully qualified Dashboard.dbo if not found
                            if v in (None, ''):
                                if dossier and house:
                                    q3 = db.session.execute(text("SELECT TOP 1 FF_D_MontantHT_TND FROM [Dashboard].[dbo].[View_FREIGHT_TND] WHERE FF_D_Dossier = :d AND FF_D_House = :h"), {'d': dossier, 'h': house}).mappings().first()
                                    v = q3.get('FF_D_MontantHT_TND') if q3 else None
                                if v in (None, '') and inv:
                                    q4 = db.session.execute(text("SELECT TOP 1 FF_D_MontantHT_TND FROM [Dashboard].[dbo].[View_FREIGHT_TND] WHERE FF_D_NumFact = :inv"), {'inv': inv}).mappings().first()
                                    v = q4.get('FF_D_MontantHT_TND') if q4 else None
                        except Exception:
                            v = None
                        try:
                            freight_cache[lookup_key] = float(v) if v not in (None, '') else None
                        except Exception:
                            freight_cache[lookup_key] = None
                    if freight_cache.get(lookup_key) is not None:
                        row['montant_ht_tnd'] = freight_cache.get(lookup_key)
            except Exception:
                # don't fail the whole request on a single row error
                continue

        return jsonify({'count': len(details), 'details': details})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/factures/ff-list', methods=['GET'])
@login_required
def get_ff_list():
    """Return rows from View_FF_Entete for a given month/year with FF totals when available."""
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)
    if month is None or year is None:
        from datetime import datetime
        now = datetime.utcnow()
        if month is None:
            month = now.month
        if year is None:
            year = now.year

    try:
        # Inspect available columns
        entete_cols = db.session.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='View_FF_Entete'
        """)).scalars().all()
        total_cols = db.session.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='View_FF_Total'
        """)).scalars().all()
        entete_set = {c for c in entete_cols}
        total_set = {c for c in total_cols}

        # Build select list mapping to frontend keys
        # respect optional type filter (Agent invoices don't have 'nom_commercial')
        req_type = request.args.get('type')

        select_parts = [
            'e.FF_H_DateProcess AS date_process',
            'e.FF_H_Dossier AS dossier',
            "e.FF_H_NumFact AS reference"
        ]
        if 'FF_H_NomClient' in entete_set:
            select_parts.append('e.FF_H_NomClient AS nom_client')
        else:
            select_parts.append("NULL AS nom_client")
        if 'FF_H_ETA' in entete_set:
            select_parts.append('e.FF_H_ETA AS eta')
        else:
            select_parts.append("NULL AS eta")
        if 'FF_H_House' in entete_set:
            select_parts.append('e.FF_H_House AS house')
        else:
            select_parts.append("NULL AS house")
        if 'FF_H_Service' in entete_set:
            select_parts.append('e.FF_H_Service AS service')
        else:
            select_parts.append("NULL AS service")
        # Commercial name: include only for non-Agent exports (Agent invoices don't have commercial)
        if not (req_type and str(req_type).upper() == 'A'):
            if 'FF_H_NomCommercial' in entete_set:
                select_parts.append('e.FF_H_NomCommercial AS nom_commercial')
            elif 'FF_H_IdCommercial' in entete_set:
                select_parts.append('e.FF_H_IdCommercial AS nom_commercial')

        # Add FF total columns when available
        if 'FF_T_TotalNonSoumis' in total_set:
            select_parts.append('t.FF_T_TotalNonSoumis AS ff_total_non_soumis')
        else:
            select_parts.append("NULL AS ff_total_non_soumis")
        if 'FF_T_TotalSoumis' in total_set:
            select_parts.append('t.FF_T_TotalSoumis AS ff_total_soumis')
        else:
            select_parts.append("NULL AS ff_total_soumis")
        # computed total (non_soumis + soumis) when at least one exists
        if 'FF_T_TotalNonSoumis' in total_set or 'FF_T_TotalSoumis' in total_set:
            select_parts.append('(COALESCE(t.FF_T_TotalNonSoumis,0) + COALESCE(t.FF_T_TotalSoumis,0)) AS ff_total')
        else:
            select_parts.append("NULL AS ff_total")
        if 'FF_T_TotalTVA' in total_set:
            select_parts.append('t.FF_T_TotalTVA AS ff_total_tva')
        else:
            select_parts.append("NULL AS ff_total_tva")

        # Include total TTC if present
        if 'FF_T_TotalTTC' in total_set:
            select_parts.append('t.FF_T_TotalTTC AS total_ttc')
        else:
            select_parts.append("NULL AS total_ttc")

        # Try to include HT total (TND) when the totals view exposes it under common names
        ht_candidates = ['FF_T_TotalHT_TND', 'FF_T_TotalHT', 'FF_T_Total_HT_TND']
        ht_col = None
        for c in ht_candidates:
            if c in total_set:
                ht_col = c
                break
        if ht_col:
            select_parts.append(f't.{ht_col} AS total_ht_tnd')
        else:
            select_parts.append("NULL AS total_ht_tnd")

        # include a representative currency for the invoice (from details)
        # For Timbrage/Magasinage/Surestarie invoices the UI/list should show TND
        if req_type and str(req_type).upper() in ('T', 'M', 'S'):
            select_parts.append("'TND' AS devise")
        else:
            # this ensures exported CSV contains the currency column when not forced to TND
            select_parts.append("(SELECT TOP 1 FF_D_Devise FROM dbo.View_FF_Detail d WHERE d.FF_D_NumFact = e.FF_H_NumFact) AS devise")
        # If a specific invoice type is requested, prefer the totals view
        # joined to the entete view and filter by FF_H_TypeFacture (matches
        # the SQL you provided for Timbrage/Agent/Magasinage).
        req_type = request.args.get('type')
        params = {'month': month, 'year': year}
        if req_type:
            # Build t_select using only columns that exist to avoid SQL errors
            t_select = [
                't.FF_T_NumFact AS reference',
                'e.FF_H_DateProcess AS date_process',
                't.FF_T_Dossier AS dossier',
                "COALESCE(e.FF_H_NomClient, NULL) AS nom_client",
                "COALESCE(e.FF_H_ETA, NULL) AS eta",
                't.FF_T_House AS house',
                "COALESCE(e.FF_H_Service, NULL) AS service",
            ]
            # commercial column: include only for non-Agent exports
            if not (req_type and str(req_type).upper() == 'A'):
                if 'FF_H_NomCommercial' in entete_set:
                    t_select.append('e.FF_H_NomCommercial AS nom_commercial')
                elif 'FF_H_IdCommercial' in entete_set:
                    t_select.append('e.FF_H_IdCommercial AS nom_commercial')
            # totals from View_FF_Total when available
            if 'FF_T_TotalNonSoumis' in total_set:
                t_select.append('t.FF_T_TotalNonSoumis AS ff_total_non_soumis')
            else:
                t_select.append("NULL AS ff_total_non_soumis")
            if 'FF_T_TotalSoumis' in total_set:
                t_select.append('t.FF_T_TotalSoumis AS ff_total_soumis')
            else:
                t_select.append("NULL AS ff_total_soumis")
            # computed total for convenience
            if 'FF_T_TotalNonSoumis' in total_set or 'FF_T_TotalSoumis' in total_set:
                t_select.append('(COALESCE(t.FF_T_TotalNonSoumis,0) + COALESCE(t.FF_T_TotalSoumis,0)) AS ff_total')
            else:
                t_select.append("NULL AS ff_total")
            if 'FF_T_TotalTVA' in total_set:
                t_select.append('t.FF_T_TotalTVA AS ff_total_tva')
            else:
                t_select.append("NULL AS ff_total_tva")
            if 'FF_T_TotalTTC' in total_set:
                t_select.append('t.FF_T_TotalTTC AS total_ttc')
            else:
                t_select.append("NULL AS total_ttc")
            # include HT total if available in totals view
            ht_col = None
            for c in ['FF_T_TotalHT_TND', 'FF_T_TotalHT', 'FF_T_Total_HT_TND']:
                if c in total_set:
                    ht_col = c
                    break
            if ht_col:
                t_select.append(f't.{ht_col} AS total_ht_tnd')
            else:
                t_select.append("NULL AS total_ht_tnd")
            # include a representative currency for the invoice (from details)
            # For Timbrage/Magasinage/Surestarie invoices the UI/list should show TND
            if req_type and str(req_type).upper() in ('T', 'M', 'S'):
                t_select.append("'TND' AS devise")
            else:
                t_select.append("(SELECT TOP 1 FF_D_Devise FROM dbo.View_FF_Detail d WHERE d.FF_D_NumFact = t.FF_T_NumFact) AS devise")
            sql = text(f"SELECT {', '.join(t_select)} FROM [dbo].[View_FF_Total] t INNER JOIN [dbo].[View_FF_Entete] e ON t.FF_T_NumFact = e.FF_H_NumFact WHERE UPPER(LTRIM(RTRIM(e.FF_H_TypeFacture))) = :type AND MONTH(e.FF_H_DateProcess) = :month AND YEAR(e.FF_H_DateProcess) = :year ORDER BY e.FF_H_DateProcess DESC")
            params['type'] = str(req_type).upper()
            rows = db.session.execute(sql, params).mappings().all()
            factures = [
                {
                    'reference': row.get('reference'),
                    'date_process': row.get('date_process'),
                    'dossier': row.get('dossier'),
                    'nom_client': row.get('nom_client'),
                    'eta': row.get('eta'),
                    'house': row.get('house'),
                    'service': row.get('service'),
                    'nom_commercial': row.get('nom_commercial'),
                    'ff_total_non_soumis': row.get('ff_total_non_soumis'),
                    'ff_total_soumis': row.get('ff_total_soumis'),
                    'ff_total_tva': row.get('ff_total_tva'),
                    'total_ttc': row.get('total_ttc'),
                    'total_ht_tnd': row.get('total_ht_tnd'),
                    'devise': row.get('devise')
                }
                for row in rows
            ]
        else:
            # default behavior: return entete-based rows (existing behavior)
            type_filter_sql = ''
            if request.args.get('type'):
                type_filter_sql = " AND UPPER(LTRIM(RTRIM(e.FF_H_TypeFactRect))) = :type"
            sql_text = f"SELECT {', '.join(select_parts)} FROM [dbo].[View_FF_Entete] e LEFT JOIN [dbo].[View_FF_Total] t ON t.FF_T_NumFact = e.FF_H_NumFact WHERE MONTH(e.FF_H_DateProcess) = :month AND YEAR(e.FF_H_DateProcess) = :year {type_filter_sql} ORDER BY e.FF_H_DateProcess DESC"
            sql = text(sql_text)
            rows = db.session.execute(sql, params).mappings().all()
            factures = [dict(row) for row in rows]

        # Post-process factures to populate total_ht_tnd when missing/null.
        freight_cache = {}
        for f in factures:
            try:
                if f.get('total_ht_tnd') not in (None, ''):
                    # ensure numeric
                    try:
                        f['total_ht_tnd'] = float(f.get('total_ht_tnd'))
                        continue
                    except Exception:
                        pass

                # Try compute from total_ttc - ff_total_tva when both present
                ttc = f.get('total_ttc')
                tva = f.get('ff_total_tva')
                f_dev = (f.get('devise') or '').strip().upper()
                # Compute HT if totals are present and either currency is TND/unknown,
                # or requested type is Timbrage and currency != TND
                compute_tot_ht = False
                if ttc not in (None, '') and tva not in (None, ''):
                    if f_dev in ('', 'TND'):
                        compute_tot_ht = True
                    elif req_type and str(req_type).upper().startswith('T') and f_dev != 'TND':
                        compute_tot_ht = True

                if compute_tot_ht:
                    try:
                        f['total_ht_tnd'] = float(ttc) - float(tva)
                        continue
                    except Exception:
                        pass

                # last resort: lookup in View_FREIGHT_TND by reference or dossier+house
                ref = f.get('reference') or f.get('FF_H_NumFact') or f.get('reference')
                dossier = f.get('dossier')
                house = f.get('house')
                lookup_key = None
                if dossier and house:
                    lookup_key = f"{dossier}::{house}"
                elif ref:
                    lookup_key = ref

                if lookup_key:
                    if lookup_key not in freight_cache:
                        try:
                            v = None
                            if dossier and house:
                                q = db.session.execute(text("SELECT SUM(ISNULL(FF_D_MontantHT_TND,0)) AS s FROM dbo.View_FREIGHT_TND WHERE FF_D_Dossier = :d AND FF_D_House = :h"), {'d': dossier, 'h': house}).mappings().first()
                                v = q.get('s') if q else None
                            if v in (None, 0) and ref:
                                q2 = db.session.execute(text("SELECT SUM(ISNULL(FF_D_MontantHT_TND,0)) AS s FROM dbo.View_FREIGHT_TND WHERE FF_D_NumFact = :ref"), {'ref': ref}).mappings().first()
                                v = q2.get('s') if q2 else None
                            # fallback to Dashboard.dbo
                            if v in (None, 0):
                                if dossier and house:
                                    q3 = db.session.execute(text("SELECT SUM(ISNULL(FF_D_MontantHT_TND,0)) AS s FROM [Dashboard].[dbo].[View_FREIGHT_TND] WHERE FF_D_Dossier = :d AND FF_D_House = :h"), {'d': dossier, 'h': house}).mappings().first()
                                    v = q3.get('s') if q3 else None
                                if v in (None,0) and ref:
                                    q4 = db.session.execute(text("SELECT SUM(ISNULL(FF_D_MontantHT_TND,0)) AS s FROM [Dashboard].[dbo].[View_FREIGHT_TND] WHERE FF_D_NumFact = :ref"), {'ref': ref}).mappings().first()
                                    v = q4.get('s') if q4 else None
                            freight_cache[lookup_key] = float(v) if v not in (None, '') else None
                        except Exception:
                            freight_cache[lookup_key] = None
                    if freight_cache.get(lookup_key) is not None:
                        f['total_ht_tnd'] = freight_cache.get(lookup_key)
            except Exception:
                continue
        return jsonify({'factures': factures, 'total': len(factures)})
    except Exception as exc:
        return jsonify({'factures': [], 'total': 0, 'error': str(exc)}), 500


@api_bp.route('/factures/ff-list/export', methods=['GET'])
@login_required
def export_ff_list_csv():
    """Export FF list for a month/year as CSV."""
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)
    if month is None or year is None:
        from datetime import datetime
        now = datetime.utcnow()
        if month is None:
            month = now.month
        if year is None:
            year = now.year

    try:
        entete_cols = db.session.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='View_FF_Entete'
        """)).scalars().all()
        total_cols = db.session.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='View_FF_Total'
        """)).scalars().all()
        entete_set = {c for c in entete_cols}
        total_set = {c for c in total_cols}

        select_parts = [
            'e.FF_H_DateProcess AS date_process',
            'e.FF_H_Dossier AS dossier'
        ]
        if 'FF_H_NomClient' in entete_set:
            select_parts.append('e.FF_H_NomClient AS nom_client')
        else:
            select_parts.append("NULL AS nom_client")
        if 'FF_H_ETA' in entete_set:
            select_parts.append('e.FF_H_ETA AS eta')
        else:
            select_parts.append("NULL AS eta")
        if 'FF_H_House' in entete_set:
            select_parts.append('e.FF_H_House AS house')
        else:
            select_parts.append("NULL AS house")
        if 'FF_H_Service' in entete_set:
            select_parts.append('e.FF_H_Service AS service')
        else:
            select_parts.append("NULL AS service")
        if 'FF_H_NomCommercial' in entete_set:
            select_parts.append('e.FF_H_NomCommercial AS nom_commercial')
        elif 'FF_H_IdCommercial' in entete_set:
            select_parts.append('e.FF_H_IdCommercial AS nom_commercial')
        else:
            select_parts.append("NULL AS nom_commercial")

        if 'FF_T_TotalNonSoumis' in total_set:
            select_parts.append('t.FF_T_TotalNonSoumis AS ff_total_non_soumis')
        else:
            select_parts.append("NULL AS ff_total_non_soumis")
        if 'FF_T_TotalSoumis' in total_set:
            select_parts.append('t.FF_T_TotalSoumis AS ff_total_soumis')
        else:
            select_parts.append("NULL AS ff_total_soumis")
        if 'FF_T_TotalTVA' in total_set:
            select_parts.append('t.FF_T_TotalTVA AS ff_total_tva')
        else:
            select_parts.append("NULL AS ff_total_tva")
        if 'FF_T_TotalTTC' in total_set:
            select_parts.append('t.FF_T_TotalTTC AS total_ttc')
        else:
            select_parts.append("NULL AS total_ttc")

        # Build WHERE clause with optional type filter (respect existing schema)
        where_clauses = ["MONTH(e.FF_H_DateProcess) = :month", "YEAR(e.FF_H_DateProcess) = :year"]
        params = {'month': month, 'year': year}
        req_type = request.args.get('type')
        if req_type:
            # choose available column name for type
            if 'FF_H_TypeFacture' in entete_set:
                where_clauses.append("UPPER(LTRIM(RTRIM(e.FF_H_TypeFacture))) = :type")
            elif 'FF_H_TypeFactRect' in entete_set:
                where_clauses.append("UPPER(LTRIM(RTRIM(e.FF_H_TypeFactRect))) = :type")
            # set param uppercased
            params['type'] = str(req_type).upper()

        where_sql = ' AND '.join(where_clauses)
        sql = text(f"""
            SELECT {', '.join(select_parts)}
            FROM [dbo].[View_FF_Entete] e
            LEFT JOIN [dbo].[View_FF_Total] t
              ON t.FF_T_NumFact = e.FF_H_NumFact
            WHERE {where_sql}
            ORDER BY e.FF_H_DateProcess DESC
        """)

        rows = db.session.execute(sql, params).mappings().all()

        import io, csv
        output = io.StringIO()
        # prepare a friendly filename using type, month name and year
        req_type = request.args.get('type')
        type_label = 'all'
        if req_type:
            t = str(req_type).upper()
            mapping = {'T': 'Timbrage', 'M': 'Magasinage', 'S': 'Surestarie', 'A': 'Agent'}
            type_label = mapping.get(t, t)
        month_names = ['Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre']
        try:
            month_name = month_names[int(month)-1]
        except Exception:
            month_name = str(month)
        filename_safe = f"factures_{type_label}_{month_name}_{year}.csv".replace(' ', '_')

        if not rows:
            csv_data = output.getvalue()
            return Response(csv_data, mimetype='text/csv', headers={
                'Content-Disposition': f'attachment; filename="{filename_safe}"'
            })

        headers = list(rows[0].keys())
        writer = csv.writer(output, delimiter=';')
        writer.writerow(headers)
        for r in rows:
            writer.writerow([r.get(h) for h in headers])

        csv_data = output.getvalue()
        return Response(csv_data, mimetype='text/csv', headers={
            'Content-Disposition': f'attachment; filename="{filename_safe}"'
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@api_bp.route('/freight/by-devise', methods=['GET'])
@login_required
def get_freight_by_devise():
    """Total marge sur fret par devise depuis View_FREIGHT."""
    required_cols = {'Devise', 'MontAchat', 'MontVente'}


@api_bp.route('/factures/annual-summary', methods=['GET'])
@login_required
def get_factures_annual_summary():
    """Return annual/monthly totals by invoice type and currency using the provided SQL logic.
    Query param: `year` (optional, defaults to current year).
    """
    year = request.args.get('year', type=int)
    if not year:
        from datetime import datetime
        year = datetime.utcnow().year

    try:
        sql = text("""
WITH FacturesA AS (
    SELECT
        YEAR(e.FF_H_DateProcess) AS annee,
        MONTH(e.FF_H_DateProcess) AS mois,
        'A' AS type_facture,
        d.FF_D_Devise AS devise,
        CASE 
            WHEN e.FF_H_TypeFactRect = 'CN' THEN -d.FF_D_MontantTTC
            ELSE d.FF_D_MontantTTC
        END AS montant
    FROM dbo.View_FF_Entete e
    JOIN dbo.View_FF_Detail d
        ON e.FF_H_NumFact = d.FF_D_NumFact
    WHERE UPPER(ISNULL(e.FF_H_TypeFacture,'')) = 'A'
      AND YEAR(e.FF_H_DateProcess) = :annee
),
FacturesTSM AS (
    SELECT
        YEAR(e.FF_H_DateProcess) AS annee,
        MONTH(e.FF_H_DateProcess) AS mois,
        e.FF_H_TypeFacture AS type_facture,
        'TND' AS devise,
        CASE 
            WHEN e.FF_H_TypeFactRect = 'CN' 
            THEN -(ISNULL(ff.FF_T_TotalSoumis,0) + ISNULL(ff.FF_T_TotalNonSoumis,0))
            ELSE (ISNULL(ff.FF_T_TotalSoumis,0) + ISNULL(ff.FF_T_TotalNonSoumis,0))
        END AS montant
    FROM dbo.View_FF_Entete e
    JOIN dbo.View_FF_Total ff
        ON e.FF_H_NumFact = ff.FF_T_NumFact
    WHERE UPPER(LTRIM(RTRIM(ISNULL(e.FF_H_TypeFacture,'')))) IN ('T','S','M')
      AND YEAR(e.FF_H_DateProcess) = :annee
),
ToutesFactures AS (
    SELECT * FROM FacturesA
    UNION ALL
    SELECT * FROM FacturesTSM
),
FacturesAvecAnnuel AS (
    SELECT * FROM ToutesFactures
    UNION ALL
    SELECT
        annee,
        0 AS mois,
        type_facture,
        devise,
        SUM(montant) AS montant
    FROM ToutesFactures
    GROUP BY annee, type_facture, devise
)
SELECT
    annee,
    mois,
    type_facture,
    devise,
    SUM(montant) AS total
FROM FacturesAvecAnnuel
GROUP BY annee, mois, type_facture, devise
ORDER BY annee, mois, type_facture, devise
""")

        rows = db.session.execute(sql, {'annee': year}).mappings().all()
        result = [dict(r) for r in rows]
        return jsonify({'year': year, 'rows': result})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/factures/dashboard-summary', methods=['GET'])
@login_required
def get_factures_dashboard_summary():
    """Try to use a DB stored procedure/function for dashboard calculations.
    If no suitable routine is found or execution fails, fall back to
    `/factures/annual-summary` (the SQL-based implementation).
    Query params: `year` (optional), `proc` (optional override, e.g. dbo.MyProc)
    """
    year = request.args.get('year', type=int)
    if not year:
        from datetime import datetime
        year = datetime.utcnow().year

    proc = request.args.get('proc', type=str)

    try:
        # If user didn't provide a proc name, try to discover likely routines
        if not proc:
            discover_sql = text("""
SELECT ROUTINE_SCHEMA, ROUTINE_NAME, ROUTINE_TYPE
FROM INFORMATION_SCHEMA.ROUTINES
WHERE (ROUTINE_TYPE IN ('PROCEDURE','FUNCTION'))
  AND (
    ROUTINE_NAME LIKE '%factur%'
    OR ROUTINE_NAME LIKE '%ca%'
    OR ROUTINE_NAME LIKE '%calc%'
    OR ROUTINE_NAME LIKE '%calcul%'
    OR ROUTINE_NAME LIKE '%dashboard%'
  )
ORDER BY ROUTINE_NAME
""")
            candidates = db.session.execute(discover_sql).fetchall()
            if candidates:
                # use first candidate schema.name
                proc = f"{candidates[0][0]}.{candidates[0][1]}"

        if proc:
            # Try executing as a stored procedure: EXEC schema.name :year
            try:
                exec_sql = text(f"EXEC {proc} :year")
                res = db.session.execute(exec_sql, {'year': year})
                rows = res.mappings().all()
                result = [dict(r) for r in rows]
                return jsonify({'year': year, 'rows': result, 'source': 'procedure', 'routine': proc})
            except Exception:
                # If procedure exec failed, try calling as a table-valued function
                try:
                    func_sql = text(f"SELECT * FROM {proc}(:year)")
                    res2 = db.session.execute(func_sql, {'year': year})
                    rows2 = res2.mappings().all()
                    result2 = [dict(r) for r in rows2]
                    return jsonify({'year': year, 'rows': result2, 'source': 'function', 'routine': proc})
                except Exception:
                    # fall through to fallback
                    pass

        # Fallback: delegate to existing SQL-based annual summary
        return get_factures_annual_summary()
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/factures/count', methods=['GET'])
@login_required
def get_factures_count():
    """Retourne le nombre de factures; optionnellement pour un mois/année donné.
    Query uses View_FF_Entete (FF_H_DateProcess). Defaults to current month/year.
    Params: month (1-12), year (YYYY)
    """
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)
    # Default to current month/year when not provided (user expects current month count)
    if month is None or year is None:
        from datetime import datetime
        now = datetime.utcnow()
        if month is None:
            month = now.month
        if year is None:
            year = now.year
    try:
        # Build WHERE clauses
        where_clauses = []
        params = {}
        # Count based on FF_H_DateProcess to match DB direct count on View_FF_Entete
        date_expr = "e.FF_H_DateProcess"
        if month:
            where_clauses.append(f"MONTH({date_expr}) = :month")
            params['month'] = month
        if year:
            where_clauses.append(f"YEAR({date_expr}) = :year")
            params['year'] = year

        # optional type filter: prefer FF_H_TypeFacture, fallback to FF_H_TypeFactRect
        invoice_type = request.args.get('type')
        if invoice_type:
            # inspect columns to choose the correct column name
            entete_cols = db.session.execute(text("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'dbo'
                  AND TABLE_NAME = 'View_FF_Entete'
            """)).scalars().all()
            entete_set = {c for c in entete_cols}
            if 'FF_H_TypeFacture' in entete_set:
                where_clauses.append("UPPER(LTRIM(RTRIM(e.FF_H_TypeFacture))) = :type")
            elif 'FF_H_TypeFactRect' in entete_set:
                where_clauses.append("UPPER(LTRIM(RTRIM(e.FF_H_TypeFactRect))) = :type")
            else:
                # if neither column exists, do not add a type filter
                pass
            params['type'] = str(invoice_type).upper()

        where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''
        sql = text(f"""
            SELECT COUNT(1) AS cnt
            FROM [dbo].[View_FF_Entete] e
            {where_sql}
        """)

        row = db.session.execute(sql, params).mappings().first() or {}
        return jsonify({'count': int(row.get('cnt') or 0)})
    except Exception as exc:
        return jsonify({'count': 0, 'error': str(exc)}), 500


@api_bp.route('/factures/aa-detail/export', methods=['GET'])
@login_required
def export_aa_detail():
    """Exporter les lignes de View_AA_SansFacture au format CSV (colonnes réduites)."""
    try:
        sans_cols = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'View_AA_SansFacture'
        """)).scalars().all()
        if not sans_cols:
            return jsonify({'error': 'View_AA_SansFacture not available'}), 404

        # Columns the UI displays for not-stamped -- export only these if present
        desired = [
            'AA_H_Dossier','AA_H_NomClient','AA_H_TVA','AA_H_Voyage','AA_H_Navire',
            'AA_H_ETA','AA_H_Traduccion','AA_H_House','AA_H_MasterBL','AA_H_Service',
            'AA_H_Escale','AA_H_Rubrique','AA_H_NomCommercial','AA_H_Trans_PC_ClientFinal','AA_H_NomClientFinal'
        ]
        available = {c for c in sans_cols}
        select_parts = [c for c in desired if c in available]
        if not select_parts:
            return jsonify({'error': 'No matching columns available for export'}), 400

        sql = text(f"SELECT TOP 10000 {', '.join(select_parts)} FROM [dbo].[View_AA_SansFacture] ORDER BY AA_H_DateProcess DESC")
        rows = db.session.execute(sql).mappings().all()

        output = io.StringIO()
        writer = csv.writer(output)
        # header using column names
        writer.writerow(select_parts)
        for r in rows:
            writer.writerow([r.get(c) for c in select_parts])

        csv_data = output.getvalue()
        return Response(csv_data, mimetype='text/csv', headers={
            'Content-Disposition': 'attachment; filename="aa_sans_facture.csv"'
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

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


@api_bp.route('/freight/items/export', methods=['GET'])
@login_required
def export_freight_items_csv():
    """Export freight items as CSV."""
    try:
        cols = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = 'View_FREIGHT'
        """)).scalars().all()
        col_set = {c for c in cols}

        required_cols = {
            'Devise', 'dossier', 'house', 'MontAchat', 'MontVente',
            'ETA', 'FournisseurNom', 'DateCreation', 'Ioe', 'PoC',
            'Refrence_AA', 'IdUtilisateur', 'EmailUtilisateur'
        }

        if not required_cols.issubset(col_set):
            return jsonify({
                'error': 'Colonnes manquantes dans View_FREIGHT',
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

        import io, csv
        output = io.StringIO()
        headers = ['devise','dossier','house','mont_achat','mont_vente','eta','fournisseur','date_creation','ioe','poc','reference_aa','id_utilisateur','email_utilisateur']
        writer = csv.writer(output, delimiter=';')
        writer.writerow(headers)
        for r in rows:
            writer.writerow([
                r.get('Devise'),
                r.get('dossier'),
                r.get('house'),
                r.get('MontAchat'),
                r.get('MontVente'),
                r.get('ETA'),
                r.get('FournisseurNom'),
                r.get('DateCreation'),
                r.get('Ioe'),
                r.get('PoC'),
                r.get('Refrence_AA'),
                r.get('IdUtilisateur'),
                r.get('EmailUtilisateur')
            ])

        csv_data = output.getvalue()
        return Response(csv_data, mimetype='text/csv', headers={
            'Content-Disposition': 'attachment; filename="freight_items.csv"'
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/freight/summary', methods=['GET'])
@login_required
def get_freight_summary():
    """Retourne les totaux marge sur fret:
    - total_du_mois: somme(FF_D_MontantHT_TND) depuis View_FREIGHT_TND_DuMois
    - total_global: somme(FF_D_MontantHT_TND) depuis View_FREIGHT_TND
    """
    try:
        # check available views
        views = db.session.execute(text("""
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.VIEWS
            WHERE TABLE_SCHEMA = 'dbo'
        """)).scalars().all()
        view_set = {v for v in views}

        total_du_mois = 0.0
        total_global = 0.0
        total_year = 0.0
        count_du_mois = 0
        count_global = 0

        # optional year filter for yearly total
        year = request.args.get('year', type=int)

        if 'View_FREIGHT_TND_DuMois' in view_set:
            # For current-month total use FF_D_MontantTTC per request
            r = db.session.execute(text("SELECT SUM(ISNULL(FF_D_MontantTTC,0)) AS s, COUNT(1) AS cnt FROM [dbo].[View_FREIGHT_TND_DuMois]"))
            row = r.mappings().first()
            total_du_mois = float(row.get('s') or 0)
            count_du_mois = int(row.get('cnt') or 0)

        if 'View_FREIGHT_TND' in view_set:
            # use FF_D_MontantTTC for global/year totals as requested
            r2 = db.session.execute(text("SELECT SUM(ISNULL(FF_D_MontantTTC,0)) AS s, COUNT(1) AS cnt FROM [dbo].[View_FREIGHT_TND]"))
            row2 = r2.mappings().first()
            total_global = float(row2.get('s') or 0)
            count_global = int(row2.get('cnt') or 0)
            if year:
                # compute yearly total from full view by year using MontantTTC
                r3 = db.session.execute(text("SELECT SUM(ISNULL(FF_D_MontantTTC,0)) AS s, COUNT(1) AS cnt FROM [dbo].[View_FREIGHT_TND] WHERE YEAR(FF_H_DateProcess) = :year"), {'year': year})
                row3 = r3.mappings().first()
                total_year = float(row3.get('s') or 0)
                # override count for yearly if needed
                # year_count = int(row3.get('cnt') or 0)

        # include counts; when debug=1, include a small sample of rows from each view
        out = {'total_du_mois': total_du_mois, 'total_global': total_global, 'total_year': total_year,
               'count_du_mois': count_du_mois, 'count_global': count_global}
        if request.args.get('debug'):
            samples = {}
            if 'View_FREIGHT_TND_DuMois' in view_set and count_du_mois>0:
                # sample month rows including MontantTTC (used for month total)
                rows_sample = db.session.execute(text("SELECT TOP 20 FF_D_NumFact, FF_H_DateProcess, FF_D_Dossier, FF_D_House, FF_D_MontantTTC FROM [dbo].[View_FREIGHT_TND_DuMois] ORDER BY FF_H_DateProcess DESC")).mappings().all()
                samples['du_mois'] = [dict(r) for r in rows_sample]
            if 'View_FREIGHT_TND' in view_set and count_global>0:
                rows_sample = db.session.execute(text("SELECT TOP 20 FF_D_NumFact, FF_H_DateProcess, FF_D_Dossier, FF_D_House, FF_D_MontantHT_TND FROM [dbo].[View_FREIGHT_TND] ORDER BY FF_H_DateProcess DESC")).mappings().all()
                samples['global'] = [dict(r) for r in rows_sample]
            out['samples'] = samples
        return jsonify(out)
    except Exception as exc:
        return jsonify({'error': str(exc), 'total_du_mois': 0, 'total_global': 0}), 500


@api_bp.route('/factures/aa-detail/export', methods=['GET'])
@login_required
def export_aa_detail_csv():
    """Export AA detail / invoices as CSV (falls back to FF entete if AA view missing)."""
    try:
        # Reuse much of get_factures_aa_detail logic to build rows
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
            'AA_H_NomCommercial'
        ]
        total_column = 'FF_T_TotalTTC'

        columns = db.session.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = 'View_AA_AvecFacture'
        """)).scalars().all()
        column_set = {c for c in columns}

        selected_columns = [c for c in desired_columns if c in column_set]
        output_rows = []

        # If AA view not usable, fallback to FF entete/total
        if not selected_columns:
            ff_entete_cols = db.session.execute(text("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'dbo'
                  AND TABLE_NAME = 'View_FF_Entete'
            """)).scalars().all()
            ff_total_cols = db.session.execute(text("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'dbo'
                  AND TABLE_NAME = 'View_FF_Total'
            """)).scalars().all()
            ff_set = {c for c in ff_entete_cols}
            total_set = {c for c in ff_total_cols}

            ff_select = [
                'e.FF_H_NumFact AS AA_H_Reference',
                'e.FF_H_DateProcess AS AA_H_DateProcess',
                'e.FF_H_Dossier AS AA_H_Dossier'
            ]
            if 'FF_H_NomClient' in ff_set:
                ff_select.append('e.FF_H_NomClient AS AA_H_NomClient')
            else:
                ff_select.append("NULL AS AA_H_NomClient")
            if 'FF_H_ETA' in ff_set:
                ff_select.append('e.FF_H_ETA AS AA_H_ETA')
            else:
                ff_select.append("NULL AS AA_H_ETA")
            if 'FF_H_House' in ff_set:
                ff_select.append('e.FF_H_House AS AA_H_House')
            else:
                ff_select.append("NULL AS AA_H_House")
            if 'FF_H_Service' in ff_set:
                ff_select.append('e.FF_H_Service AS AA_H_Service')
            else:
                ff_select.append("NULL AS AA_H_Service")
            if 'FF_H_IdCommercial' in ff_set:
                ff_select.append('e.FF_H_IdCommercial AS AA_H_IdCommercial')
            elif 'FF_H_NomCommercial' in ff_set:
                ff_select.append('e.FF_H_NomCommercial AS AA_H_NomCommercial')
            else:
                ff_select.append("NULL AS AA_H_IdCommercial")

            if 'FF_T_TotalTTC' in total_set:
                ff_select.append('t.FF_T_TotalTTC AS total_ttc')
            else:
                ff_select.append("NULL AS total_ttc")
            if 'FF_T_TotalNonSoumis' in total_set:
                ff_select.append('t.FF_T_TotalNonSoumis AS ff_total_non_soumis')
            else:
                ff_select.append("NULL AS ff_total_non_soumis")
            if 'FF_T_TotalSoumis' in total_set:
                ff_select.append('t.FF_T_TotalSoumis AS ff_total_soumis')
            else:
                ff_select.append("NULL AS ff_total_soumis")
            if 'FF_T_TotalTVA' in total_set:
                ff_select.append('t.FF_T_TotalTVA AS ff_total_tva')
            else:
                ff_select.append("NULL AS ff_total_tva")

            fallback_sql = text(f"SELECT {', '.join(ff_select)} FROM [dbo].[View_FF_Entete] e LEFT JOIN [dbo].[View_FF_Total] t ON t.FF_T_NumFact = e.FF_H_NumFact ORDER BY e.FF_H_DateProcess DESC")
            rows = db.session.execute(fallback_sql).mappings().all()
            for row in rows:
                output_rows.append({
                    'reference': row.get('AA_H_Reference'),
                    'date_process': row.get('AA_H_DateProcess'),
                    'dossier': row.get('AA_H_Dossier'),
                    'nom_client': row.get('AA_H_NomClient'),
                    'eta': row.get('AA_H_ETA'),
                    'house': row.get('AA_H_House'),
                    'service': row.get('AA_H_Service'),
                    'id_commercial': row.get('AA_H_IdCommercial') or row.get('AA_H_NomCommercial'),
                    'total_ttc': row.get('total_ttc'),
                    'ff_total_non_soumis': row.get('ff_total_non_soumis'),
                    'ff_total_soumis': row.get('ff_total_soumis'),
                    'ff_total_tva': row.get('ff_total_tva')
                })
        else:
            # Build select parts for AA view with optional totals
            total_cols = db.session.execute(text("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'dbo'
                  AND TABLE_NAME = 'View_FF_Total'
            """)).scalars().all()
            total_set = {c for c in total_cols}

            select_parts = [f"a.{col}" for col in selected_columns]
            if total_column in total_set:
                select_parts.append(f"t.{total_column} AS total_ttc")
            if 'FF_T_TotalNonSoumis' in total_set:
                select_parts.append('t.FF_T_TotalNonSoumis AS ff_total_non_soumis')
            if 'FF_T_TotalSoumis' in total_set:
                select_parts.append('t.FF_T_TotalSoumis AS ff_total_soumis')
            if 'FF_T_TotalTVA' in total_set:
                select_parts.append('t.FF_T_TotalTVA AS ff_total_tva')

            aa_total_cols = db.session.execute(text("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'dbo'
                  AND TABLE_NAME = 'View_AA_Total'
            """)).scalars().all()
            aa_total_set = {c for c in aa_total_cols}

            aa_join_col = None
            if 'AA_T_NumFact' in aa_total_set:
                aa_join_col = 'AA_T_NumFact'
            elif 'AA_T_NumFacture' in aa_total_set:
                aa_join_col = 'AA_T_NumFacture'

            if aa_join_col:
                if 'AA_T_TotalNonSoumis' in aa_total_set:
                    select_parts.append('at.AA_T_TotalNonSoumis AS aa_total_non_soumis')
                if 'AA_T_TotalSoumis' in aa_total_set:
                    select_parts.append('at.AA_T_TotalSoumis AS aa_total_soumis')
                if 'AA_T_TotalTVA' in aa_total_set:
                    select_parts.append('at.AA_T_TotalTVA AS aa_total_tva')

            join_at_clause = ''
            if aa_join_col:
                join_at_clause = f"LEFT JOIN [dbo].[View_AA_Total] at ON at.{aa_join_col} = a.AA_H_NumFacture"

            sql = text(f"SELECT {', '.join(select_parts)} FROM [dbo].[View_AA_AvecFacture] a LEFT JOIN [dbo].[View_FF_Total] t ON t.FF_T_NumFact = a.AA_H_NumFacture {join_at_clause} ORDER BY a.AA_H_DateProcess DESC")
            rows = db.session.execute(sql).mappings().all()
            for row in rows:
                output_rows.append({
                    'reference': row.get('AA_H_Reference'),
                    'date_process': row.get('AA_H_DateProcess'),
                    'dossier': row.get('AA_H_Dossier'),
                    'nom_client': row.get('AA_H_NomClient'),
                    'eta': row.get('AA_H_ETA'),
                    'house': row.get('AA_H_House'),
                    'service': row.get('AA_H_Service'),
                    'id_commercial': row.get('AA_H_IdCommercial'),
                    'nom_commercial': row.get('AA_H_NomCommercial'),
                    'total_ttc': row.get('total_ttc'),
                    'ff_total_non_soumis': row.get('ff_total_non_soumis'),
                    'ff_total_soumis': row.get('ff_total_soumis'),
                    'ff_total_tva': row.get('ff_total_tva'),
                    'aa_total_non_soumis': row.get('aa_total_non_soumis'),
                    'aa_total_soumis': row.get('aa_total_soumis'),
                    'aa_total_tva': row.get('aa_total_tva')
                })

        import io, csv
        output = io.StringIO()
        if not output_rows:
            return Response(output.getvalue(), mimetype='text/csv', headers={
                'Content-Disposition': 'attachment; filename="invoices.csv"'
            })

        headers = list(output_rows[0].keys())
        writer = csv.writer(output, delimiter=';')
        writer.writerow(headers)
        for r in output_rows:
            writer.writerow([r.get(h) for h in headers])

        csv_data = output.getvalue()
        return Response(csv_data, mimetype='text/csv', headers={
            'Content-Disposition': 'attachment; filename="invoices.csv"'
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500
