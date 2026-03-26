"""Routes API — Freight, Annual Summary, Dashboard Summary, Exports."""
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


@api_bp.route('/factures/aa-detail/export-xlsx', methods=['GET'])
@login_required
def export_aa_detail_xlsx():
    """Export AA detail as XLSX by converting existing CSV export output to Excel.
    This avoids duplicating SQL logic: it calls `export_aa_detail_csv()` then parses CSV.
    Requires `openpyxl` to be installed.
    """
    if Workbook is None:
        return jsonify({'error': 'openpyxl is not installed on the server'}), 500
    try:
        # Reuse CSV export function to obtain CSV data
        resp = export_aa_detail_csv()
        if isinstance(resp, tuple):
            # export_aa_detail_csv may return (response, status)
            resp_obj = resp[0]
        else:
            resp_obj = resp

        # If CSV exporter returned a JSON error, propagate it
        if getattr(resp_obj, 'mimetype', '') == 'application/json':
            return resp_obj

        csv_bytes = resp_obj.get_data(as_text=True)
        reader = csv.reader(io.StringIO(csv_bytes), delimiter=';')

        wb = Workbook()
        ws = wb.active
        for r_idx, row in enumerate(reader, start=1):
            for c_idx, cell in enumerate(row, start=1):
                ws.cell(row=r_idx, column=c_idx, value=cell)

        # adjust column widths lightly
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

        filename = 'aa_sans_facture.xlsx'
        return Response(out.read(), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


# Compatibility alias: accept .xlsx extension used by some clients
@api_bp.route('/factures/aa-detail/export.xlsx', methods=['GET'])
@login_required
def export_aa_detail_xlsx_alias():
    return export_aa_detail_xlsx()