"""Routes API — Factures (AA & FF)."""
from flask import jsonify, request, Response
import io
import csv
try:
    from openpyxl import Workbook
except Exception:
    Workbook = None
from flask_login import login_required, current_user
from app import db
from app.routes.api import api_bp
from sqlalchemy import text
from datetime import datetime

@api_bp.route('/factures/aa-detail', methods=['GET'])
@login_required
def get_factures_aa_detail():
    """Récupérer les factures depuis View_AA_AvecFacture"""
    limit = request.args.get('limit', 0, type=int)
    limit = max(0, min(limit, 100000))
    top_clause = f"TOP {limit}" if limit > 0 else ""

    # Use the per-AA aggregation (group by AA header) to compute totals per AA
    try:
        sql = text(f"""
            SELECT {top_clause}
                h.AA_H_Reference,
                h.AA_H_DateProcess,
                h.AA_H_Dossier,
                h.AA_H_NomClient,
                h.AA_H_Adresse_1,
                h.AA_H_Adresse_2,
                h.AA_H_Adresse_3,
                h.AA_H_TVA,
                h.AA_H_DateSuspTVA_Du,
                h.AA_H_DateSuspTVA_Au,
                h.AA_H_IdBar,
                h.AA_H_Voyage,
                h.AA_H_Navire,
                h.AA_H_PPOL,
                h.AA_H_POL,
                h.AA_H_DPOL,
                h.AA_H_PPOD,
                h.AA_H_POD,
                h.AA_H_DPOD,
                h.AA_H_ETA,
                h.AA_H_Traduccion,
                h.AA_H_House,
                h.AA_H_MasterBL,
                h.AA_H_Service,
                h.AA_H_Escale,
                h.AA_H_Rubrique,
                h.AA_H_IdCommercial,
                h.AA_H_NomCommercial,
                h.AA_H_EmailCommercial,
                h.AA_H_IdUtilisateur,
                h.AA_H_EmailUtilisateur,
                h.AA_H_Trans_PC_ClientFinal,
                h.AA_H_NomClientFinal,
                h.AA_H_NumSuspTVA,
                h.AA_H_NumFacture,
                SUM(ISNULL(t.AA_T_TotalNonSoumis,0)) AS aa_total_non_soumis,
                SUM(ISNULL(t.AA_T_TotalSoumis,0)) AS aa_total_soumis,
                SUM(ISNULL(t.AA_T_TotalNonSoumis,0) + ISNULL(t.AA_T_TotalSoumis,0)) AS aa_total_general,
                SUM(ISNULL(t.AA_T_TotalTVA,0)) AS aa_total_tva
            FROM [Dashboard].[dbo].[View_AA_SansFacture] h
            LEFT JOIN [Dashboard].[dbo].[View_AA_Total] t
                ON t.AA_T_Reference = h.AA_H_Reference
            GROUP BY h.AA_H_Reference, h.AA_H_DateProcess, h.AA_H_Dossier, h.AA_H_NomClient,
                     h.AA_H_Adresse_1, h.AA_H_Adresse_2, h.AA_H_Adresse_3, h.AA_H_TVA,
                     h.AA_H_DateSuspTVA_Du, h.AA_H_DateSuspTVA_Au, h.AA_H_IdBar, h.AA_H_Voyage,
                     h.AA_H_Navire, h.AA_H_PPOL, h.AA_H_POL, h.AA_H_DPOL, h.AA_H_PPOD,
                     h.AA_H_POD, h.AA_H_DPOD, h.AA_H_ETA, h.AA_H_Traduccion, h.AA_H_House,
                     h.AA_H_MasterBL, h.AA_H_Service, h.AA_H_Escale, h.AA_H_Rubrique,
                     h.AA_H_IdCommercial, h.AA_H_NomCommercial, h.AA_H_EmailCommercial,
                     h.AA_H_IdUtilisateur, h.AA_H_EmailUtilisateur, h.AA_H_Trans_PC_ClientFinal,
                     h.AA_H_NomClientFinal, h.AA_H_NumSuspTVA, h.AA_H_NumFacture
            ORDER BY h.AA_H_DateProcess DESC
        """)

        rows = db.session.execute(sql).mappings().all()
        factures = [dict(r) for r in rows]

        # total count from the canonical view
        try:
            cnt_row = db.session.execute(text("SELECT COUNT(1) AS cnt FROM [Dashboard].[dbo].[View_AA_SansFacture]")).mappings().first()
            total_count = int(cnt_row.get('cnt') or len(factures))
        except Exception:
            total_count = len(factures)

        return jsonify({'factures': factures, 'total': total_count})
    except Exception as exc:
        # fallback to previous behavior: return empty with error
        return jsonify({'factures': [], 'total': 0, 'error': str(exc)}), 500


@api_bp.route('/factures/aa-totals', methods=['GET'])
@login_required
def get_aa_totals():
    """Return aggregated totals and count for Avis (AA) without invoice.
    Tries multiple strategies: direct sums from View_AA_Total, or joining
    View_AA_SansFacture to View_AA_Total. Returns totals and computed HT.
    """
    try:
        # Preferred calculation: aggregate per AA (avoid duplicates when View_AA_Total has multiple rows per AA)
        sql = text("""
            WITH per_aa AS (
                SELECT h.AA_H_Reference,
                       SUM(ISNULL(t.AA_T_TotalNonSoumis,0)) AS total_non_soumis,
                       SUM(ISNULL(t.AA_T_TotalSoumis,0)) AS total_soumis,
                       SUM(ISNULL(t.AA_T_TotalNonSoumis,0) + ISNULL(t.AA_T_TotalSoumis,0)) AS total_general,
                       SUM(ISNULL(t.AA_T_TotalTVA,0)) AS total_tva
                FROM [Dashboard].[dbo].[View_AA_SansFacture] h
                LEFT JOIN [Dashboard].[dbo].[View_AA_Total] t
                  ON t.AA_T_Reference = h.AA_H_Reference
                GROUP BY h.AA_H_Reference
            )
            SELECT COUNT(1) AS count,
                   SUM(total_non_soumis) AS total_non_soumis,
                   SUM(total_soumis) AS total_soumis,
                   SUM(total_general) AS total_general,
                   SUM(total_tva) AS total_tva
            FROM per_aa
        """)

        r = db.session.execute(sql).mappings().first()
        if r:
            count = int(r.get('count') or 0)
            total_non_soumis = float(r.get('total_non_soumis') or 0)
            total_soumis = float(r.get('total_soumis') or 0)
            total_general = float(r.get('total_general') or (total_non_soumis + total_soumis))
            total_tva = float(r.get('total_tva') or 0)
        else:
            count = 0
            total_non_soumis = total_soumis = total_general = total_tva = 0.0

        total_ht = total_general - total_tva
        return jsonify({
            'count': count,
            'total_non_soumis': total_non_soumis,
            'total_soumis': total_soumis,
            'total_tva': total_tva,
            'total_general': total_general,
            'total_ht': total_ht
        })
    except Exception:
        # If the preferred per-AA calculation fails, fall back to previous logic
        try:
            # detect columns in View_AA_Total
            aa_total_cols = db.session.execute(text("""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'View_AA_Total'
            """)).scalars().all()
            aa_total_set = {c for c in aa_total_cols}

            # detect existence of View_AA_SansFacture (for count and join)
            sans_exists = db.session.execute(text("""
                SELECT 1 FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'View_AA_SansFacture'
            """)).fetchone() is not None

            # count of not-stamped notices (prefer View_AA_SansFacture)
            count = 0
            if sans_exists:
                try:
                    cnt_row = db.session.execute(text("SELECT COUNT(1) AS cnt FROM dbo.View_AA_SansFacture")).mappings().first()
                    count = int(cnt_row.get('cnt') or 0)
                except Exception:
                    count = 0

            total_soumis = 0.0
            total_non_soumis = 0.0
            total_tva = 0.0

            # Preferred: sum directly from View_AA_Total if totals columns exist
            if 'AA_T_TotalSoumis' in aa_total_set or 'AA_T_TotalNonSoumis' in aa_total_set:
                try:
                    tva_expr = 'SUM(ISNULL(AA_T_TotalTVA,0)) AS total_tva' if 'AA_T_TotalTVA' in aa_total_set else '0 AS total_tva'
                    sql = text(f"SELECT SUM(ISNULL(AA_T_TotalSoumis,0)) AS total_soumis, SUM(ISNULL(AA_T_TotalNonSoumis,0)) AS total_non_soumis, {tva_expr} FROM dbo.View_AA_Total")
                    row = db.session.execute(sql).mappings().first() or {}
                    total_soumis = float(row.get('total_soumis') or 0)
                    total_non_soumis = float(row.get('total_non_soumis') or 0)
                    total_tva = float(row.get('total_tva') or 0)
                    total_general = total_non_soumis + total_soumis
                    total_ht = (total_soumis + total_non_soumis) - total_tva
                    return jsonify({
                        'count': count,
                        'total_soumis': total_soumis,
                        'total_non_soumis': total_non_soumis,
                        'total_tva': total_tva,
                        'total_general': total_general,
                        'total_ht': total_ht
                    })
                except Exception:
                    # fallback to join-based approach below
                    pass

            # If direct totals not available, try joining SansFacture -> AA_Total
            if sans_exists:
                try:
                    aa_total_cols = db.session.execute(text("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'View_AA_Total'")).scalars().all()
                    aa_total_set = {c for c in aa_total_cols}
                    aa_join_col = None
                    if 'AA_T_Reference' in aa_total_set:
                        aa_join_col = 'AA_T_Reference'
                    elif 'AA_T_NumFact' in aa_total_set:
                        aa_join_col = 'AA_T_NumFact'
                    elif 'AA_T_NumFacture' in aa_total_set:
                        aa_join_col = 'AA_T_NumFacture'

                    if aa_join_col:
                        tva_expr = 'SUM(ISNULL(at.AA_T_TotalTVA,0)) AS total_tva' if 'AA_T_TotalTVA' in aa_total_set else '0 AS total_tva'
                        sql = text(f"SELECT SUM(ISNULL(at.AA_T_TotalSoumis,0)) AS total_soumis, SUM(ISNULL(at.AA_T_TotalNonSoumis,0)) AS total_non_soumis, {tva_expr} FROM dbo.View_AA_SansFacture a LEFT JOIN dbo.View_AA_Total at ON at.{aa_join_col} = a.AA_H_Reference")
                        row = db.session.execute(sql).mappings().first() or {}
                        total_soumis = float(row.get('total_soumis') or 0)
                        total_non_soumis = float(row.get('total_non_soumis') or 0)
                        total_tva = float(row.get('total_tva') or 0)
                        total_general = total_non_soumis + total_soumis
                        total_ht = (total_soumis + total_non_soumis) - total_tva
                        return jsonify({
                            'count': count,
                            'total_soumis': total_soumis,
                            'total_non_soumis': total_non_soumis,
                            'total_tva': total_tva,
                            'total_general': total_general,
                            'total_ht': total_ht
                        })
                except Exception:
                    pass

            # Final fallback: return count and zeros
            return jsonify({'count': count, 'total_soumis': 0.0, 'total_non_soumis': 0.0, 'total_tva': 0.0, 'total_general': 0.0, 'total_ht': 0.0})
        except Exception as exc:
            return jsonify({'count': 0, 'total_soumis': 0.0, 'total_non_soumis': 0.0, 'total_tva': 0.0, 'total_general': 0.0, 'total_ht': 0.0, 'error': str(exc)}), 500


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
        # Build WHERE clause; prefix with table alias for joined query
        conditions = ' OR '.join([f"d.{col} = :ref" for col in where_cols])

        # If the primary reference column exists, left-join header view to include AA_H_ETA
        if 'AA_D_Reference' in available:
            sql = text(f"SELECT d.*, h.AA_H_ETA FROM [dbo].[View_AA_Detail] d LEFT JOIN [Dashboard].[dbo].[View_AA_SansFacture] h ON h.AA_H_Reference = d.AA_D_Reference WHERE {conditions} ORDER BY 1")
        else:
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

    try:
        params = {'year': year}
        where = "YEAR(e.FF_H_DateProcess) = :year"
        if month:
            where += " AND MONTH(e.FF_H_DateProcess) = :month"
            params['month'] = month
        if req_type:
            where += " AND UPPER(LTRIM(RTRIM(ISNULL(e.FF_H_TypeFacture,'')))) = :type"
            params['type'] = str(req_type).upper()

        # Sum submitted + non-submitted totals from View_FF_Total when available
        sql = text(f"""
            SELECT
                SUM(COALESCE(t.FF_T_TotalSoumis,0) + COALESCE(t.FF_T_TotalNonSoumis,0)) AS total_soum_non,
                SUM(COALESCE(t.FF_T_TotalSoumis,0)) AS total_soumis,
                SUM(COALESCE(t.FF_T_TotalNonSoumis,0)) AS total_non_soumis,
                SUM(COALESCE(t.FF_T_TotalTTC,0)) AS total_ttc
            FROM dbo.View_FF_Total t
            INNER JOIN dbo.View_FF_Entete e ON t.FF_T_NumFact = e.FF_H_NumFact
            WHERE {where}
        """)

        row = db.session.execute(sql, params).mappings().first()
        if not row:
            return jsonify({'year': year, 'month': month, 'rows': []})
        return jsonify({
            'year': year,
            'month': month,
            'total_soumis': float(row.get('total_soumis') or 0),
            'total_non_soumis': float(row.get('total_non_soumis') or 0),
            'total_soum_non': float(row.get('total_soum_non') or 0),
            'total_ttc': float(row.get('total_ttc') or 0)
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


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

        # compute totals per currency from detail rows for Agent invoices (type 'A')
        try:
            sql = text("""
                SELECT d.FF_D_Devise AS devise, SUM(ISNULL(d.FF_D_MontantTTC,0)) AS s
                FROM dbo.View_FF_Detail d
                JOIN dbo.View_FF_Entete e ON e.FF_H_NumFact = d.FF_D_NumFact
                WHERE UPPER(LTRIM(RTRIM(ISNULL(e.FF_H_TypeFacture,'')))) = 'A'
                  AND YEAR(e.FF_H_DateProcess) = :year
                  AND MONTH(e.FF_H_DateProcess) = :month
                GROUP BY d.FF_D_Devise
            """)
            rows = db.session.execute(sql, {'year': year, 'month': month}).mappings().all()
            totals = {r.get('devise') or 'UNKNOWN': float(r.get('s') or 0) for r in rows}
            return jsonify({'year': year, 'month': month, 'totals': totals})
        except Exception as exc:
            return jsonify({'error': str(exc)}), 500
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/factures/magasinage-totals', methods=['GET'])
@login_required
def get_magasinage_totals():
    """Return sums for Magasinage invoices (TND) for a month/year."""
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
        # inspect totals view for available columns
        total_cols = db.session.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='View_FF_Total'
        """)).scalars().all()
        total_set = {c for c in total_cols}

        # choose TTC and HT columns if available
        ttc_col = 'FF_T_TotalTTC' if 'FF_T_TotalTTC' in total_set else None
        ht_col = None
        for c in ('FF_T_TotalHT_TND', 'FF_T_TotalHT', 'FF_T_Total_HT_TND'):
            if c in total_set:
                ht_col = c
                break

        params = {'month': month, 'year': year}
        ttc_expr = f"SUM(COALESCE(t.{ttc_col},0)) AS total_ttc" if ttc_col else "0 AS total_ttc"
        ht_expr = f"SUM(COALESCE(t.{ht_col},0)) AS total_ht" if ht_col else "0 AS total_ht"

        sql = text(f"""
            SELECT {ttc_expr}, {ht_expr}
            FROM dbo.View_FF_Total t
            JOIN dbo.View_FF_Entete e ON t.FF_T_NumFact = e.FF_H_NumFact
            WHERE UPPER(LTRIM(RTRIM(ISNULL(e.FF_H_TypeFacture,'')))) = 'M'
              AND MONTH(e.FF_H_DateProcess) = :month
              AND YEAR(e.FF_H_DateProcess) = :year
        """)

        row = db.session.execute(sql, params).mappings().first() or {}

        # yearly HT total (same ht_col) for provided year
        if ht_col:
            sql_y = text(f"SELECT SUM(COALESCE(t.{ht_col},0)) AS total_year_ht FROM dbo.View_FF_Total t JOIN dbo.View_FF_Entete e ON t.FF_T_NumFact = e.FF_H_NumFact WHERE UPPER(LTRIM(RTRIM(ISNULL(e.FF_H_TypeFacture,'')))) = 'M' AND YEAR(e.FF_H_DateProcess) = :year")
            ry = db.session.execute(sql_y, {'year': year}).mappings().first() or {}
            total_year_ht = float(ry.get('total_year_ht') or 0)
        else:
            total_year_ht = 0.0

        return jsonify({
            'month': month,
            'year': year,
            'total_ttc': float(row.get('total_ttc') or 0),
            'total_ht': float(row.get('total_ht') or 0),
            'total_year_ht': float(total_year_ht)
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/factures/surestarie-totals', methods=['GET'])
@login_required
def get_surestarie_totals():
    """Return sums for Surestarie invoices (TND) for a month/year."""
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
        total_cols = db.session.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='View_FF_Total'
        """)).scalars().all()
        total_set = {c for c in total_cols}

        ttc_col = 'FF_T_TotalTTC' if 'FF_T_TotalTTC' in total_set else None
        ht_col = None
        for c in ('FF_T_TotalHT_TND', 'FF_T_TotalHT', 'FF_T_Total_HT_TND'):
            if c in total_set:
                ht_col = c
                break

        params = {'month': month, 'year': year}
        ttc_expr = f"SUM(COALESCE(t.{ttc_col},0)) AS total_ttc" if ttc_col else "0 AS total_ttc"
        ht_expr = f"SUM(COALESCE(t.{ht_col},0)) AS total_ht" if ht_col else "0 AS total_ht"

        sql = text(f"""
            SELECT {ttc_expr}, {ht_expr}
            FROM dbo.View_FF_Total t
            JOIN dbo.View_FF_Entete e ON t.FF_T_NumFact = e.FF_H_NumFact
            WHERE UPPER(LTRIM(RTRIM(ISNULL(e.FF_H_TypeFacture,'')))) = 'S'
              AND MONTH(e.FF_H_DateProcess) = :month
              AND YEAR(e.FF_H_DateProcess) = :year
        """)

        row = db.session.execute(sql, params).mappings().first() or {}

        if ht_col:
            sql_y = text(f"SELECT SUM(COALESCE(t.{ht_col},0)) AS total_year_ht FROM dbo.View_FF_Total t JOIN dbo.View_FF_Entete e ON t.FF_T_NumFact = e.FF_H_NumFact WHERE UPPER(LTRIM(RTRIM(ISNULL(e.FF_H_TypeFacture,'')))) = 'S' AND YEAR(e.FF_H_DateProcess) = :year")
            ry = db.session.execute(sql_y, {'year': year}).mappings().first() or {}
            total_year_ht = float(ry.get('total_year_ht') or 0)
        else:
            total_year_ht = 0.0

        return jsonify({
            'month': month,
            'year': year,
            'total_ttc': float(row.get('total_ttc') or 0),
            'total_ht': float(row.get('total_ht') or 0),
            'total_year_ht': float(total_year_ht)
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/debug/agent-sample', methods=['GET'])
@login_required
def debug_agent_sample():
    """Temporary debug endpoint: returns count, totals per currency and sample rows for Agent invoices."""
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    if not year:
        from datetime import datetime
        year = datetime.utcnow().year
    if month is None:
        from datetime import datetime
        month = datetime.utcnow().month

    try:
        # count
        cnt_sql = text("""
            SELECT COUNT(DISTINCT e.FF_H_NumFact) AS cnt
            FROM dbo.View_FF_Entete e
            JOIN dbo.View_FF_Detail d ON e.FF_H_NumFact = d.FF_D_NumFact
            WHERE UPPER(LTRIM(RTRIM(ISNULL(e.FF_H_TypeFacture,'')))) = 'A'
              AND YEAR(e.FF_H_DateProcess) = :year
              AND MONTH(e.FF_H_DateProcess) = :month
        """)
        cnt_row = db.session.execute(cnt_sql, {'year': year, 'month': month}).mappings().first()
        cnt = int(cnt_row.get('cnt') or 0)

        # totals by currency
        totals_sql = text("""
            SELECT d.FF_D_Devise AS devise, SUM(ISNULL(d.FF_D_MontantTTC,0)) AS total_ttc
            FROM dbo.View_FF_Detail d
            JOIN dbo.View_FF_Entete e ON e.FF_H_NumFact = d.FF_D_NumFact
            WHERE UPPER(LTRIM(RTRIM(ISNULL(e.FF_H_TypeFacture,'')))) = 'A'
              AND YEAR(e.FF_H_DateProcess) = :year
              AND MONTH(e.FF_H_DateProcess) = :month
            GROUP BY d.FF_D_Devise
        """)
        rows = db.session.execute(totals_sql, {'year': year, 'month': month}).mappings().all()
        totals = {r.get('devise') or 'UNKNOWN': float(r.get('total_ttc') or 0) for r in rows}

        # sample rows
        sample_sql = text("""
            SELECT TOP 20 e.FF_H_NumFact AS reference, e.FF_H_DateProcess AS date_process,
                   e.FF_H_TypeFacture AS type_facture, d.FF_D_Devise AS devise, d.FF_D_MontantTTC AS montant_ttc
            FROM dbo.View_FF_Entete e
            JOIN dbo.View_FF_Detail d ON e.FF_H_NumFact = d.FF_D_NumFact
            WHERE UPPER(LTRIM(RTRIM(ISNULL(e.FF_H_TypeFacture,'')))) = 'A'
              AND YEAR(e.FF_H_DateProcess) = :year
              AND MONTH(e.FF_H_DateProcess) = :month
            ORDER BY e.FF_H_DateProcess DESC
        """)
        sample_rows = db.session.execute(sample_sql, {'year': year, 'month': month}).mappings().all()
        sample = [dict(r) for r in sample_rows]

        return jsonify({'year': year, 'month': month, 'count': cnt, 'totals': totals, 'sample': sample})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/factures/agent-tnd-monthly', methods=['GET'])
@login_required
def get_agent_tnd_monthly():
    # Compute totals by summing per-AA TotalGeneral (preferred) then fallback
    try:
        sql = text("""
            WITH per_aa AS (
                SELECT h.AA_H_Reference,
                       SUM(ISNULL(t.AA_T_TotalNonSoumis,0)) AS total_non_soumis,
                       SUM(ISNULL(t.AA_T_TotalSoumis,0)) AS total_soumis,
                       SUM(ISNULL(t.AA_T_TotalNonSoumis,0) + ISNULL(t.AA_T_TotalSoumis,0)) AS total_general,
                       SUM(ISNULL(t.AA_T_TotalTVA,0)) AS total_tva
                FROM [Dashboard].[dbo].[View_AA_SansFacture] h
                LEFT JOIN [Dashboard].[dbo].[View_AA_Total] t
                  ON t.AA_T_Reference = h.AA_H_Reference
                GROUP BY h.AA_H_Reference
            )
            SELECT COUNT(1) AS count,
                   SUM(total_non_soumis) AS total_non_soumis,
                   SUM(total_soumis) AS total_soumis,
                   SUM(total_general) AS total_general,
                   SUM(total_tva) AS total_tva
            FROM per_aa
        """)

        r = db.session.execute(sql).mappings().first()
        if r:
            total_non_soumis = float(r.get('total_non_soumis') or 0)
            total_soumis = float(r.get('total_soumis') or 0)
            total_general = float(r.get('total_general') or (total_non_soumis + total_soumis))
            total_tva = float(r.get('total_tva') or 0)
            count = int(r.get('count') or 0)
        else:
            count = 0
            total_non_soumis = total_soumis = total_general = total_tva = 0.0

        total_ht = total_general - total_tva
        return jsonify({'count': count, 'total_non_soumis': total_non_soumis,
                        'total_soumis': total_soumis, 'total_tva': total_tva,
                        'total_general': total_general, 'total_ht': total_ht})
    except Exception:
        # Fallback: aggregate directly from View_AA_Total if per-AA aggregation fails
        try:
            r2 = db.session.execute(text("""
                SELECT
                    SUM(ISNULL(AA_T_TotalNonSoumis,0)) AS total_non_soumis,
                    SUM(ISNULL(AA_T_TotalSoumis,0)) AS total_soumis,
                    SUM(ISNULL(AA_T_TotalTVA,0)) AS total_tva
                FROM [Dashboard].[dbo].[View_AA_Total]
            """)).mappings().first()
            total_non_soumis = float(r2.get('total_non_soumis') or 0)
            total_soumis = float(r2.get('total_soumis') or 0)
            total_tva = float(r2.get('total_tva') or 0)
            total_general = total_non_soumis + total_soumis
            total_ht = total_general - total_tva
            cnt = db.session.execute(text("SELECT COUNT(1) AS cnt FROM [Dashboard].[dbo].[View_AA_SansFacture]")).mappings().first()
            count = int(cnt.get('cnt') or 0) if cnt else 0
            return jsonify({'count': count, 'total_non_soumis': total_non_soumis,
                            'total_soumis': total_soumis, 'total_tva': total_tva,
                            'total_general': total_general, 'total_ht': total_ht})
        except Exception as exc:
            return jsonify({'count': 0, 'total_non_soumis': 0.0,
                            'total_soumis': 0.0, 'total_tva': 0.0,
                            'total_general': 0.0, 'total_ht': 0.0, 'error': str(exc)}), 500
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
        aa_cols = db.session.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'View_AA_AvecFacture'
        """)).scalars().all()
        detail_set = {c for c in detail_cols}
        entete_set = {c for c in entete_cols}
        aa_set = {c for c in aa_cols}

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
            ('FF_H_NomCommercial', 'nom_commercial'),
            ('FF_H_IdCommercial', 'id_commercial'),
            ('FF_H_TypeFacture', 'type_facture'),
            ('FF_H_ETA', 'eta'),
            ('FF_H_House', 'house'),
            ('FF_H_Service', 'service')
        ]

        select_parts = [f"d.{col} AS {alias}" for col, alias in preferred_detail if col in detail_set]
        # include entete columns by joining entete and prefixing with e.
        select_parts += [f"e.{col} AS {alias}" for col, alias in preferred_entete if col in entete_set]
        # include AA commercial fields as an additional fallback source
        if 'AA_H_NomCommercial' in aa_set:
            select_parts.append("a.AA_H_NomCommercial AS AA_H_NomCommercial")
        if 'AA_H_IdCommercial' in aa_set:
            select_parts.append("a.AA_H_IdCommercial AS AA_H_IdCommercial")
        if not select_parts:
            return jsonify({'error': 'Aucune colonne disponible dans View_FF_Detail/View_FF_Entete pour afficher les détails'}), 500

        # build parameterized IN list
        placeholders = ','.join([f":inv{i}" for i in range(len(parts))])
        params = {f"inv{i}": parts[i] for i in range(len(parts))}
        sql = text(f"""
            SELECT {', '.join(select_parts)}
            FROM dbo.View_FF_Detail d
            LEFT JOIN dbo.View_FF_Entete e ON LTRIM(RTRIM(d.FF_D_NumFact)) = LTRIM(RTRIM(e.FF_H_NumFact))
            LEFT JOIN dbo.View_AA_AvecFacture a ON LTRIM(RTRIM(a.AA_H_NumFacture)) = LTRIM(RTRIM(d.FF_D_NumFact))
            WHERE d.FF_D_NumFact IN ({placeholders})
            ORDER BY d.FF_D_NumFact
        """)
        rows = db.session.execute(sql, params).mappings().all()
        details = [dict(r) for r in rows]

        # Secondary fallback: if commercial fields are still empty on detail rows,
        # fetch them directly from header view by invoice number and backfill.
        missing_invoices = []
        for row in details:
            try:
                if (row.get('nom_commercial') is None or str(row.get('nom_commercial')).strip() == '') and row.get('invoice_num'):
                    missing_invoices.append(str(row.get('invoice_num')).strip())
            except Exception:
                continue
        missing_invoices = sorted({inv for inv in missing_invoices if inv})
        if missing_invoices:
            try:
                params_hdr = {}
                placeholders_hdr = []
                for i, inv in enumerate(missing_invoices):
                    k = f"h{i}"
                    placeholders_hdr.append(f":{k}")
                    params_hdr[k] = inv

                hdr_select = ["LTRIM(RTRIM(FF_H_NumFact)) AS invoice_num"]
                if 'FF_H_NomCommercial' in entete_set:
                    hdr_select.append("FF_H_NomCommercial AS nom_commercial")
                else:
                    hdr_select.append("NULL AS nom_commercial")
                if 'FF_H_IdCommercial' in entete_set:
                    hdr_select.append("FF_H_IdCommercial AS id_commercial")
                else:
                    hdr_select.append("NULL AS id_commercial")

                hdr_sql = text(f"SELECT {', '.join(hdr_select)} FROM dbo.View_FF_Entete WHERE LTRIM(RTRIM(FF_H_NumFact)) IN ({', '.join(placeholders_hdr)})")
                hdr_rows = db.session.execute(hdr_sql, params_hdr).mappings().all()
                hdr_map = {str((r.get('invoice_num') or '')).strip(): dict(r) for r in hdr_rows}

                for row in details:
                    inv = str((row.get('invoice_num') or '')).strip()
                    if not inv:
                        continue
                    h = hdr_map.get(inv)
                    if not h:
                        continue
                    if row.get('id_commercial') in (None, '') and h.get('id_commercial') not in (None, ''):
                        row['id_commercial'] = h.get('id_commercial')
                    if row.get('nom_commercial') in (None, '') and h.get('nom_commercial') not in (None, ''):
                        row['nom_commercial'] = h.get('nom_commercial')
            except Exception:
                pass

        # Ensure nom_commercial is populated when only id_commercial exists.
        for row in details:
            try:
                if (row.get('nom_commercial') is None or str(row.get('nom_commercial')).strip() == '') and row.get('id_commercial') not in (None, ''):
                    row['nom_commercial'] = row.get('id_commercial')
                if (row.get('nom_commercial') is None or str(row.get('nom_commercial')).strip() == '') and row.get('AA_H_NomCommercial') not in (None, ''):
                    row['nom_commercial'] = row.get('AA_H_NomCommercial')
                if (row.get('nom_commercial') is None or str(row.get('nom_commercial')).strip() == '') and row.get('AA_H_IdCommercial') not in (None, ''):
                    row['nom_commercial'] = row.get('AA_H_IdCommercial')
            except Exception:
                continue

        # Post-process rows to populate montant_ht_tnd when it's missing.
        # We'll try to compute/resolve values in bulk to avoid issuing one DB query per row.
        freight_cache = {}

        # First pass: try simple per-row computation and collect lookup keys for batch queries
        refs_to_lookup = set()
        pairs_to_lookup = set()
        for row in details:
            try:
                mh_tnd = row.get('montant_ht_tnd')
                if mh_tnd in (None, '') and row.get('montant_ht_tnd_alt') not in (None, ''):
                    mh_tnd = row.get('montant_ht_tnd_alt')

                if mh_tnd not in (None, ''):
                    try:
                        row['montant_ht_tnd'] = float(mh_tnd)
                        continue
                    except Exception:
                        pass

                devise = (row.get('devise') or '').strip().upper()
                montant_ht = row.get('montant_ht')
                if montant_ht not in (None, '') and devise == 'TND':
                    try:
                        row['montant_ht_tnd'] = float(montant_ht)
                        continue
                    except Exception:
                        pass

                montant_ttc = row.get('montant_ttc')
                montant_tva = row.get('montant_tva')
                type_fact = (row.get('type_facture') or '').strip().upper()
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

                # prepare keys for batch lookup (fallback)
                inv = row.get('invoice_num')
                dossier = row.get('dossier')
                house = row.get('house')
                if dossier and house:
                    pairs_to_lookup.add((dossier, house))
                elif inv:
                    refs_to_lookup.add(inv)
            except Exception:
                continue

        # Batch fetch sums from View_FREIGHT_TND by NumFact (refs)
        try:
            if refs_to_lookup:
                params = {}
                placeholders = []
                for i, r in enumerate(sorted(refs_to_lookup)):
                    key = f"r{i}"
                    placeholders.append(f":{key}")
                    params[key] = r
                sql = text(f"SELECT FF_D_NumFact AS ref, SUM(ISNULL(FF_D_MontantHT_TND,0)) AS s FROM dbo.View_FREIGHT_TND WHERE FF_D_NumFact IN ({', '.join(placeholders)}) GROUP BY FF_D_NumFact")
                rows_q = db.session.execute(sql, params).mappings().all()
                for r in rows_q:
                    freight_cache[str(r.get('ref'))] = float(r.get('s') or 0)
        except Exception:
            pass

        # Batch fetch sums from View_FREIGHT_TND by (dossier, house)
        try:
            if pairs_to_lookup:
                # collect unique dossiers and houses for WHERE IN filter
                dossiers = sorted({d for d, h in pairs_to_lookup})
                houses = sorted({h for d, h in pairs_to_lookup})
                params = {}
                d_place = []
                h_place = []
                for i, d in enumerate(dossiers):
                    k = f"d{i}"
                    d_place.append(f":{k}")
                    params[k] = d
                for j, h in enumerate(houses):
                    k = f"h{j}"
                    h_place.append(f":{k}")
                    params[k] = h

                sql = text(f"SELECT FF_D_Dossier AS dossier, FF_D_House AS house, SUM(ISNULL(FF_D_MontantHT_TND,0)) AS s FROM dbo.View_FREIGHT_TND WHERE FF_D_Dossier IN ({', '.join(d_place)}) AND FF_D_House IN ({', '.join(h_place)}) GROUP BY FF_D_Dossier, FF_D_House")
                rows_q = db.session.execute(sql, params).mappings().all()
                for r in rows_q:
                    key = f"{r.get('dossier')}::{r.get('house')}"
                    freight_cache[key] = float(r.get('s') or 0)
        except Exception:
            pass

        # Apply fetched values to rows where available
        for row in details:
            try:
                if row.get('montant_ht_tnd') not in (None, ''):
                    continue
                inv = row.get('invoice_num')
                dossier = row.get('dossier')
                house = row.get('house')
                found = None
                if dossier and house:
                    found = freight_cache.get(f"{dossier}::{house}")
                if found is None and inv:
                    found = freight_cache.get(str(inv))
                if found is not None:
                    row['montant_ht_tnd'] = found
            except Exception:
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
        # indicate container type 'ISOTANK' when equipment contains '26'
        if 'FF_H_EquipoCont' in entete_set:
            select_parts.append("CASE WHEN e.FF_H_EquipoCont LIKE '%26%' THEN 'ISOTANK' WHEN e.FF_H_EquipoCont LIKE '%57%' THEN 'FLEXITANK' WHEN e.FF_H_EquipoCont LIKE '%22%' THEN 'FLEXITANK' WHEN e.FF_H_EquipoCont LIKE '% 2 %' THEN 'FLEXITANK' WHEN e.FF_H_EquipoCont LIKE '%2%' THEN 'FLEXITANK' ELSE NULL END AS cont_info")
            select_parts.append('e.FF_H_EquipoCont AS ff_equipo')
            select_parts.append('e.FF_H_EquipoCont AS FF_H_EquipoCont')
        else:
            select_parts.append("NULL AS cont_info")
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
            # include ISOTANK indicator from entete if present
            if 'FF_H_EquipoCont' in entete_set:
                t_select.append("CASE WHEN e.FF_H_EquipoCont LIKE '%26%' THEN 'ISOTANK' WHEN e.FF_H_EquipoCont LIKE '%57%' THEN 'FLEXITANK' WHEN e.FF_H_EquipoCont LIKE '%22%' THEN 'FLEXITANK' WHEN e.FF_H_EquipoCont LIKE '% 2 %' THEN 'FLEXITANK' WHEN e.FF_H_EquipoCont LIKE '%2%' THEN 'FLEXITANK' ELSE NULL END AS cont_info")
                t_select.append('e.FF_H_EquipoCont AS ff_equipo')
                t_select.append('e.FF_H_EquipoCont AS FF_H_EquipoCont')
            else:
                t_select.append("NULL AS cont_info")
                t_select.append("NULL AS ff_equipo")
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
                    'cont_info': row.get('cont_info'),
                    'ff_equipo': row.get('ff_equipo'),
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
        # Compute simple cases first and collect keys for batch lookup to avoid per-row DB queries.
        freight_cache = {}
        refs_to_lookup = set()
        pairs_to_lookup = set()

        for f in factures:
            try:
                if f.get('total_ht_tnd') not in (None, ''):
                    try:
                        f['total_ht_tnd'] = float(f.get('total_ht_tnd'))
                        continue
                    except Exception:
                        pass

                ttc = f.get('total_ttc')
                tva = f.get('ff_total_tva')
                f_dev = (f.get('devise') or '').strip().upper()
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

                ref = f.get('reference') or f.get('FF_H_NumFact') or f.get('reference')
                dossier = f.get('dossier')
                house = f.get('house')
                if dossier and house:
                    pairs_to_lookup.add((dossier, house))
                elif ref:
                    refs_to_lookup.add(ref)
            except Exception:
                continue

        # Batch queries: by NumFact and by (dossier, house)
        try:
            if refs_to_lookup:
                params = {}
                placeholders = []
                for i, r in enumerate(sorted(refs_to_lookup)):
                    key = f"r{i}"
                    placeholders.append(f":{key}")
                    params[key] = r
                sql = text(f"SELECT FF_D_NumFact AS ref, SUM(ISNULL(FF_D_MontantHT_TND,0)) AS s FROM dbo.View_FREIGHT_TND WHERE FF_D_NumFact IN ({', '.join(placeholders)}) GROUP BY FF_D_NumFact")
                rows_q = db.session.execute(sql, params).mappings().all()
                for r in rows_q:
                    freight_cache[str(r.get('ref'))] = float(r.get('s') or 0)
        except Exception:
            pass

        try:
            if pairs_to_lookup:
                dossiers = sorted({d for d, h in pairs_to_lookup})
                houses = sorted({h for d, h in pairs_to_lookup})
                params = {}
                d_place = []
                h_place = []
                for i, d in enumerate(dossiers):
                    k = f"d{i}"
                    d_place.append(f":{k}")
                    params[k] = d
                for j, h in enumerate(houses):
                    k = f"h{j}"
                    h_place.append(f":{k}")
                    params[k] = h
                sql = text(f"SELECT FF_D_Dossier AS dossier, FF_D_House AS house, SUM(ISNULL(FF_D_MontantHT_TND,0)) AS s FROM dbo.View_FREIGHT_TND WHERE FF_D_Dossier IN ({', '.join(d_place)}) AND FF_D_House IN ({', '.join(h_place)}) GROUP BY FF_D_Dossier, FF_D_House")
                rows_q = db.session.execute(sql, params).mappings().all()
                for r in rows_q:
                    key = f"{r.get('dossier')}::{r.get('house')}"
                    freight_cache[key] = float(r.get('s') or 0)

                # fallback: try Dashboard.dbo if some keys still missing
                missing_refs = [r for r in refs_to_lookup if str(r) not in freight_cache]
                missing_pairs = [p for p in pairs_to_lookup if f"{p[0]}::{p[1]}" not in freight_cache]
                if missing_refs or missing_pairs:
                    params2 = {}
                    placeholders2 = []
                    if missing_refs:
                        for i, r in enumerate(sorted(missing_refs)):
                            key = f"rr{i}"
                            placeholders2.append(f":{key}")
                            params2[key] = r
                        sql2 = text(f"SELECT FF_D_NumFact AS ref, SUM(ISNULL(FF_D_MontantHT_TND,0)) AS s FROM [Dashboard].[dbo].[View_FREIGHT_TND] WHERE FF_D_NumFact IN ({', '.join(placeholders2)}) GROUP BY FF_D_NumFact")
                        rows2 = db.session.execute(sql2, params2).mappings().all()
                        for r in rows2:
                            freight_cache[str(r.get('ref'))] = float(r.get('s') or 0)

                    if missing_pairs:
                        dossiers2 = sorted({d for d, h in missing_pairs})
                        houses2 = sorted({h for d, h in missing_pairs})
                        params3 = {}
                        d_place3 = []
                        h_place3 = []
                        for i, d in enumerate(dossiers2):
                            k = f"dd{i}"
                            d_place3.append(f":{k}")
                            params3[k] = d
                        for j, h in enumerate(houses2):
                            k = f"hh{j}"
                            h_place3.append(f":{k}")
                            params3[k] = h
                        sql3 = text(f"SELECT FF_D_Dossier AS dossier, FF_D_House AS house, SUM(ISNULL(FF_D_MontantHT_TND,0)) AS s FROM [Dashboard].[dbo].[View_FREIGHT_TND] WHERE FF_D_Dossier IN ({', '.join(d_place3)}) AND FF_D_House IN ({', '.join(h_place3)}) GROUP BY FF_D_Dossier, FF_D_House")
                        rows3 = db.session.execute(sql3, params3).mappings().all()
                        for r in rows3:
                            key = f"{r.get('dossier')}::{r.get('house')}"
                            freight_cache[key] = float(r.get('s') or 0)
        except Exception:
            pass

        # Assign found totals back to factures
        for f in factures:
            try:
                if f.get('total_ht_tnd') not in (None, ''):
                    continue
                ref = f.get('reference') or f.get('FF_H_NumFact') or f.get('reference')
                dossier = f.get('dossier')
                house = f.get('house')
                val = None
                if dossier and house:
                    val = freight_cache.get(f"{dossier}::{house}")
                if val is None and ref:
                    val = freight_cache.get(str(ref))
                if val is not None:
                    f['total_ht_tnd'] = val
            except Exception:
                continue
        # Fill cont_info fallback: if cont_info missing, batch-query View_FF_Entete for FF_H_EquipoCont
        try:
            refs_missing_cont = [f.get('reference') for f in factures if (f.get('cont_info') is None or f.get('cont_info')=='') and (f.get('reference') or f.get('FF_H_NumFact'))]
            refs_missing_cont = sorted({str(r) for r in refs_missing_cont if r})
            if refs_missing_cont:
                params = {}
                placeholders = []
                for i, r in enumerate(refs_missing_cont):
                    k = f"r{i}"
                    placeholders.append(f":{k}")
                    params[k] = r
                sql = text(f"SELECT FF_H_NumFact AS ref, FF_H_EquipoCont AS equipo FROM dbo.View_FF_Entete WHERE FF_H_NumFact IN ({', '.join(placeholders)})")
                rows_e = db.session.execute(sql, params).mappings().all()
                equipo_map = {str(r.get('ref')): (r.get('equipo') or '') for r in rows_e}
                for f in factures:
                    try:
                        if f.get('cont_info') not in (None, ''):
                            continue
                        ref = f.get('reference') or f.get('FF_H_NumFact')
                        if not ref:
                            continue
                        eq = str(equipo_map.get(str(ref)) or '').strip()
                        if not eq:
                            continue
                        # priority: '26' -> ISOTANK, then tokens 2/22/57 -> FLEXITANK
                        try:
                            import re
                            tokens = re.findall(r"\d+", eq)
                            if any(t == '26' for t in tokens):
                                f['cont_info'] = 'ISOTANK'
                            elif any(t in ('2', '22') for t in tokens):
                                f['cont_info'] = 'FLEXITANK'
                        except Exception:
                            # conservative fallback to previous substring checks
                            if '26' in eq:
                                f['cont_info'] = 'ISOTANK'
                            elif '22' in eq or '2' in eq:
                                f['cont_info'] = 'FLEXITANK'
                    except Exception:
                        continue
        except Exception:
            pass
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

        # Build SELECT list based on application-visible columns (invoices view)
        # Map UI column keys to DB expressions; keep checks to avoid SQL errors
        req_type = request.args.get('type')
        # Default invoices column keys (matching `columnSets.invoices` in the UI)
        ui_invoice_cols = ['reference','date_process','dossier','nom_client','eta','house','cont_info','service','nom_commercial','ff_total_non_soumis','ff_total_soumis','ff_total_tva','total_ttc','devise']
        ui_agent_cols = ['reference','date_process','dossier','nom_client','eta','house','service','ff_total_non_soumis','ff_total_soumis','ff_total_tva','total_ttc','devise']
        cols_to_use = ui_agent_cols if (req_type and str(req_type).upper() == 'A') else ui_invoice_cols

        select_parts = []
        for key in cols_to_use:
            if key == 'reference':
                # prefer totals view numfact when available
                if 'FF_T_NumFact' in total_set:
                    select_parts.append('COALESCE(t.FF_T_NumFact, e.FF_H_NumFact) AS reference')
                else:
                    select_parts.append('e.FF_H_NumFact AS reference')
            elif key == 'date_process':
                select_parts.append('e.FF_H_DateProcess AS date_process')
            elif key == 'dossier':
                if 'FF_T_Dossier' in total_set:
                    select_parts.append("COALESCE(t.FF_T_Dossier, e.FF_H_Dossier) AS dossier")
                else:
                    select_parts.append('e.FF_H_Dossier AS dossier')
            elif key == 'nom_client':
                select_parts.append('e.FF_H_NomClient AS nom_client' if 'FF_H_NomClient' in entete_set else "NULL AS nom_client")
            elif key == 'eta':
                select_parts.append('e.FF_H_ETA AS eta' if 'FF_H_ETA' in entete_set else "NULL AS eta")
            elif key == 'house':
                if 'FF_T_House' in total_set:
                    select_parts.append("COALESCE(t.FF_T_House, e.FF_H_House) AS house")
                else:
                    select_parts.append('e.FF_H_House AS house' if 'FF_H_House' in entete_set else "NULL AS house")
            elif key == 'cont_info':
                if 'FF_H_EquipoCont' in entete_set:
                    select_parts.append("CASE WHEN e.FF_H_EquipoCont LIKE '%26%' THEN 'ISOTANK' WHEN e.FF_H_EquipoCont LIKE '% 2 %' THEN 'FLEXITANK' WHEN e.FF_H_EquipoCont LIKE '%22%' THEN 'FLEXITANK' WHEN e.FF_H_EquipoCont LIKE '%2%' THEN 'FLEXITANK' ELSE NULL END AS cont_info")
                else:
                    select_parts.append("NULL AS cont_info")
            elif key == 'service':
                select_parts.append('e.FF_H_Service AS service' if 'FF_H_Service' in entete_set else "NULL AS service")
            elif key == 'nom_commercial':
                if 'FF_H_NomCommercial' in entete_set:
                    select_parts.append('e.FF_H_NomCommercial AS nom_commercial')
                elif 'FF_H_IdCommercial' in entete_set:
                    select_parts.append('e.FF_H_IdCommercial AS nom_commercial')
                else:
                    select_parts.append("NULL AS nom_commercial")
            elif key == 'ff_total_non_soumis':
                select_parts.append('t.FF_T_TotalNonSoumis AS ff_total_non_soumis' if 'FF_T_TotalNonSoumis' in total_set else "NULL AS ff_total_non_soumis")
            elif key == 'ff_total_soumis':
                select_parts.append('t.FF_T_TotalSoumis AS ff_total_soumis' if 'FF_T_TotalSoumis' in total_set else "NULL AS ff_total_soumis")
            elif key == 'ff_total_tva':
                select_parts.append('t.FF_T_TotalTVA AS ff_total_tva' if 'FF_T_TotalTVA' in total_set else "NULL AS ff_total_tva")
            elif key == 'total_ttc':
                select_parts.append('t.FF_T_TotalTTC AS total_ttc' if 'FF_T_TotalTTC' in total_set else "NULL AS total_ttc")
            elif key == 'devise':
                if req_type and str(req_type).upper() in ('T','M','S'):
                    select_parts.append("'TND' AS devise")
                else:
                    select_parts.append("(SELECT TOP 1 FF_D_Devise FROM dbo.View_FF_Detail d WHERE d.FF_D_NumFact = e.FF_H_NumFact) AS devise")
            else:
                # generic fallback: try entete then totals
                if key in entete_set:
                    select_parts.append(f"e.{key} AS {key}")
                elif key in total_set:
                    select_parts.append(f"t.{key} AS {key}")
                else:
                    select_parts.append(f"NULL AS {key}")

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
        # Map DB column names to friendly labels used in the application UI
        label_map = {
            'FF_H_NumFact': 'Numéro facture',
            'FF_H_DateProcess': 'Date Process',
            'FF_H_Dossier': 'Dossier',
            'FF_H_NomClient': 'Agent',
            'FF_H_ETA': 'ETA',
            'FF_H_House': 'House',
            'FF_H_Service': 'Service',
            'FF_H_NomCommercial': 'Nom Commercial',
            'FF_H_IdCommercial': 'Nom Commercial',
            'FF_T_TotalNonSoumis': 'Total Non Soumis',
            'FF_T_TotalSoumis': 'Total Soumis',
            'FF_T_TotalTVA': 'Total TVA',
            'FF_T_TotalTTC': 'Total TTC',
            'cont_info': 'Conteneur',
            'FF_H_EquipoCont': 'FF_H_EquipoCont'
        }
        writer = csv.writer(output, delimiter=';')
        # write friendly headers (preserve column order)
        writer.writerow([label_map.get(h, h) for h in headers])
        for r in rows:
            writer.writerow([r.get(h) for h in headers])

        csv_data = output.getvalue()
        return Response(csv_data, mimetype='text/csv', headers={
            'Content-Disposition': f'attachment; filename="{filename_safe}"'
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/factures/ff-list/export.xlsx', methods=['GET'])
@login_required
def export_ff_list_xlsx():
    """Export FF list as XLSX (reuses CSV logic then converts to Excel)."""
    if Workbook is None:
        return jsonify({'error': 'openpyxl is not installed on the server'}), 500
    try:
        resp = export_ff_list_csv()
        resp_obj = resp[0] if isinstance(resp, tuple) else resp
        if getattr(resp_obj, 'mimetype', '') == 'application/json':
            return resp_obj
        csv_bytes = resp_obj.get_data(as_text=True)
        reader = csv.reader(io.StringIO(csv_bytes), delimiter=';')
        wb = Workbook()
        ws = wb.active
        for r_idx, row in enumerate(reader, start=1):
            for c_idx, cell in enumerate(row, start=1):
                ws.cell(row=r_idx, column=c_idx, value=cell)
        for col in ws.columns:
            max_length = 0
            col_letter = None
            for cell in col:
                try:
                    if cell.value:
                        l = len(str(cell.value))
                        if l > max_length:
                            max_length = l
                except Exception:
                    continue
                if col_letter is None:
                    col_letter = cell.column_letter
            if col_letter:
                ws.column_dimensions[col_letter].width = min(max(10, max_length + 2), 60)
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        month = request.args.get('month', '')
        year = request.args.get('year', '')
        req_type = request.args.get('type', 'all')
        filename = f"factures_{req_type}_{month}_{year}.xlsx"
        return Response(out.read(),
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        headers={'Content-Disposition': f'attachment; filename="{filename}"'})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500
