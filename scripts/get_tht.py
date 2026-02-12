import os, sys
# ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app import create_app, db
from sqlalchemy import text

app = create_app()

refs = [
"EXPINV2026-000709",
"EXPINV2026-000711",
"EXPINV2026-000714",
"IMPINV2026-000728",
"EXPINV2026-000772",
"EXPINV2026-000773",
"EXPINV2026-000778",
"EXPINV2026-000808",
"EXPINV2026-000810",
"EXPINV2026-000850",
"EXPINV2026-000874",
"EXPINV2026-000875",
"EXPINV2026-000878",
"EXPINV2026-000879",
"EXPINV2026-000984",
]

with app.app_context():
    out = {}
    sql = text("""
        SELECT D.FF_D_NumFact as ref,
               SUM(CASE WHEN D.FF_D_MontantHT_TND IS NOT NULL
                        THEN D.FF_D_MontantHT_TND
                        ELSE (ISNULL(D.FF_D_MontantTTC,0) - ISNULL(D.FF_D_MontantTVA,0)) END) AS tht
        FROM dbo.View_FF_Detail D
        WHERE D.FF_D_NumFact = :ref
        GROUP BY D.FF_D_NumFact
    """)
    for r in refs:
        try:
            row = db.session.execute(sql, {'ref': r}).mappings().first()
            tht = float(row['tht']) if row and row['tht'] is not None else 0.0
        except Exception as e:
            tht = f"ERROR: {e}"
        out[r] = tht
    import json
    print(json.dumps(out, indent=2, ensure_ascii=False))
