from flask import jsonify, request, Response
import io
import csv
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
            if select_parts:
                sql = text(f"SELECT TOP 1000 {', '.join(select_parts)} FROM [dbo].[View_AA_SansFacture] ORDER BY AA_H_DateProcess DESC")
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
                if count_du_mois>0:
                    rows_sample = db.session.execute(text("SELECT TOP 20 FF_D_NumFact, FF_H_DateProcess, FF_D_Dossier, FF_D_House, FF_D_MontantTTC FROM [dbo].[View_FREIGHT_TND_DuMois] ORDER BY FF_H_DateProcess DESC")).mappings().all()
                    if not rows_sample:
                        rows_sample = db.session.execute(text("SELECT TOP 20 FF_D_NumFact, FF_H_DateProcess, FF_D_Dossier, FF_D_House, FF_D_MontantTTC FROM [Dashboard].[dbo].[View_FREIGHT_TND_DuMois] ORDER BY FF_H_DateProcess DESC")).mappings().all()
                    samples['du_mois'] = [dict(r) for r in rows_sample]
                if count_global>0:
                    rows_sample = db.session.execute(text("SELECT TOP 20 FF_D_NumFact, FF_H_DateProcess, FF_D_Dossier, FF_D_House, FF_D_MontantTTC FROM [dbo].[View_FREIGHT_TND] ORDER BY FF_H_DateProcess DESC")).mappings().all()
                    if not rows_sample:
                        rows_sample = db.session.execute(text("SELECT TOP 20 FF_D_NumFact, FF_H_DateProcess, FF_D_Dossier, FF_D_House, FF_D_MontantTTC FROM [Dashboard].[dbo].[View_FREIGHT_TND] ORDER BY FF_H_DateProcess DESC")).mappings().all()
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
    if not year:
        from datetime import datetime
        year = datetime.utcnow().year

    # required columns to compute provided SQL
    required_entete = {'FF_H_TypeFacture', 'FF_H_NumFact', 'FF_H_DateProcess'}
    # FF_D_MontantHT_TND may be missing; we'll fall back to (TotalTTC - TotalTVA)
    required_detail = {'FF_D_NumFact', 'FF_D_Devise', 'FF_D_Montant', 'FF_D_MontantTVA', 'FF_D_MontantTTC'}

    try:
        entete_cols = db.session.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'View_FF_Entete'
        """)).scalars().all()
        detail_cols = db.session.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'View_FF_Detail'
        """)).scalars().all()

        entete_set = {c for c in entete_cols}
        detail_set = {c for c in detail_cols}

        missing = []
        if not required_entete.issubset(entete_set):
            missing.extend(sorted(required_entete - entete_set))
        if not required_detail.issubset(detail_set):
            missing.extend(sorted(required_detail - detail_set))
        if missing:
            return jsonify({'error': 'Colonnes manquantes', 'missing': missing}), 500

        sql = text("""
            SELECT
                CASE
                    WHEN UPPER(LTRIM(RTRIM(H.FF_H_TypeFacture))) = 'A'
                        THEN H.FF_H_TypeFacture + ' - ' + D.FF_D_Devise
                    ELSE H.FF_H_TypeFacture
                END AS TypeService,
                    SUM(ISNULL(D.FF_D_MontantHT_TND, ISNULL(D.FF_D_MontantTTC,0) - ISNULL(D.FF_D_MontantTVA,0))) AS Total_HT,
                SUM(ISNULL(D.FF_D_Montant,0)) AS Total_Soumis,
                SUM(ISNULL(D.FF_D_MontantTVA,0)) AS Total_TVA,
                SUM(ISNULL(D.FF_D_MontantTTC,0)) AS Total_TTC
            FROM [dbo].[View_FF_Entete] H
            INNER JOIN [dbo].[View_FF_Detail] D
                ON H.FF_H_NumFact = D.FF_D_NumFact
            WHERE UPPER(LTRIM(RTRIM(H.FF_H_TypeFacture))) IN ('T','S','A','M')
              AND YEAR(H.FF_H_DateProcess) = :year
            GROUP BY
                CASE
                    WHEN UPPER(LTRIM(RTRIM(H.FF_H_TypeFacture))) = 'A'
                        THEN H.FF_H_TypeFacture + ' - ' + D.FF_D_Devise
                    ELSE H.FF_H_TypeFacture
                END
            ORDER BY TypeService
        """)

        rows = db.session.execute(sql, {'year': year}).mappings().all()
        results = []
        for r in rows:
            results.append({
                'type_service': r.get('TypeService'),
                'total_ht': float(r.get('Total_HT') or 0),
                'total_soumis': float(r.get('Total_Soumis') or 0),
                'total_tva': float(r.get('Total_TVA') or 0),
                'total_ttc': float(r.get('Total_TTC') or 0)
            })

        return jsonify({'year': year, 'rows': results})
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

        debug = request.args.get('debug')
        result = {
            'year': year,
            'current': build_activity_series(year),
            'previous': build_activity_series(year - 1)
        }
        if debug:
            # include raw rows for debugging (requires authenticated session)
            rows_cur = db.session.execute(sql, {'year': year}).mappings().all()
            rows_prev = db.session.execute(sql, {'year': year - 1}).mappings().all()
            # convert Decimal/Date types to strings/numbers for JSON
            def simplify(rows):
                out = []
                for r in rows:
                    row = {}
                    for k,v in r.items():
                        try:
                            # try to convert to float if numeric
                            if v is None:
                                row[k]=None
                            else:
                                row[k]=float(v)
                        except Exception:
                            try:
                                row[k]=str(v)
                            except Exception:
                                row[k]=None
                    out.append(row)
                return out
            result['debug_rows_current'] = simplify(rows_cur)
            result['debug_rows_previous'] = simplify(rows_prev)
        return jsonify(result)
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
        # Commercial name if present
        if 'FF_H_NomCommercial' in entete_set:
            select_parts.append('e.FF_H_NomCommercial AS nom_commercial')
        elif 'FF_H_IdCommercial' in entete_set:
            select_parts.append('e.FF_H_IdCommercial AS nom_commercial')
        else:
            select_parts.append("NULL AS nom_commercial")

        # Add FF total columns when available
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

        # Include total TTC if present
        if 'FF_T_TotalTTC' in total_set:
            select_parts.append('t.FF_T_TotalTTC AS total_ttc')
        else:
            select_parts.append("NULL AS total_ttc")
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
            # commercial column: prefer NomCommercial, else IdCommercial, else NULL
            if 'FF_H_NomCommercial' in entete_set:
                t_select.append('e.FF_H_NomCommercial AS nom_commercial')
            elif 'FF_H_IdCommercial' in entete_set:
                t_select.append('e.FF_H_IdCommercial AS nom_commercial')
            else:
                t_select.append("NULL AS nom_commercial")
            # totals from View_FF_Total when available
            if 'FF_T_TotalNonSoumis' in total_set:
                t_select.append('t.FF_T_TotalNonSoumis AS ff_total_non_soumis')
            else:
                t_select.append("NULL AS ff_total_non_soumis")
            if 'FF_T_TotalSoumis' in total_set:
                t_select.append('t.FF_T_TotalSoumis AS ff_total_soumis')
            else:
                t_select.append("NULL AS ff_total_soumis")
            if 'FF_T_TotalTVA' in total_set:
                t_select.append('t.FF_T_TotalTVA AS ff_total_tva')
            else:
                t_select.append("NULL AS ff_total_tva")
            if 'FF_T_TotalTTC' in total_set:
                t_select.append('t.FF_T_TotalTTC AS total_ttc')
            else:
                t_select.append("NULL AS total_ttc")
            # include a representative currency for the invoice (from details)
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

        sql = text(f"""
            SELECT {', '.join(select_parts)}
            FROM [dbo].[View_FF_Entete] e
            LEFT JOIN [dbo].[View_FF_Total] t
              ON t.FF_T_NumFact = e.FF_H_NumFact
                        WHERE MONTH(e.FF_H_DateProcess) = :month
                            AND YEAR(e.FF_H_DateProcess) = :year
                        ORDER BY e.FF_H_DateProcess DESC
                """)

        rows = db.session.execute(sql, {'month': month, 'year': year}).mappings().all()

        import io, csv
        output = io.StringIO()
        if not rows:
            csv_data = output.getvalue()
            return Response(csv_data, mimetype='text/csv', headers={
                'Content-Disposition': f'attachment; filename="factures_{year}_{month}.csv"'
            })

        headers = list(rows[0].keys())
        writer = csv.writer(output, delimiter=';')
        writer.writerow(headers)
        for r in rows:
            writer.writerow([r.get(h) for h in headers])

        csv_data = output.getvalue()
        return Response(csv_data, mimetype='text/csv', headers={
            'Content-Disposition': f'attachment; filename="factures_{year}_{month}.csv"'
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@api_bp.route('/freight/by-devise', methods=['GET'])
@login_required
def get_freight_by_devise():
    """Total marge sur fret par devise depuis View_FREIGHT."""
    required_cols = {'Devise', 'MontAchat', 'MontVente'}


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
            r2 = db.session.execute(text("SELECT SUM(ISNULL(FF_D_MontantHT_TND,0)) AS s, COUNT(1) AS cnt FROM [dbo].[View_FREIGHT_TND]"))
            row2 = r2.mappings().first()
            total_global = float(row2.get('s') or 0)
            count_global = int(row2.get('cnt') or 0)
            if year:
                # compute yearly total from full view by year
                r3 = db.session.execute(text("SELECT SUM(ISNULL(FF_D_MontantHT_TND,0)) AS s, COUNT(1) AS cnt FROM [dbo].[View_FREIGHT_TND] WHERE YEAR(FF_H_DateProcess) = :year"), {'year': year})
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
