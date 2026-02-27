from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, text

# Charger .env du projet en écrasant les variables existantes
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'), override=True)
url = os.getenv('DATABASE_URL')
print('Using URL:', url)

try:
    eng = create_engine(url)
    with eng.connect() as conn:
        ver = conn.execute(text("SELECT @@VERSION")).scalar()
        print('SQL Server version:', ver)
        # Check key views
        try:
            cnt = conn.execute(text("SELECT COUNT(*) FROM dbo.View_AA_SansFacture")).scalar()
            print('View_AA_SansFacture count:', cnt)
        except Exception as e:
            print('View_AA_SansFacture check failed:', e)
        try:
            total = conn.execute(text("SELECT SUM(COALESCE(AA_T_TotalSoumis,0)+COALESCE(AA_T_TotalNonSoumis,0)) FROM dbo.View_AA_Total")).scalar()
            print('Sum View_AA_Total:', total)
        except Exception as e:
            print('View_AA_Total check failed:', e)
except Exception as e:
    import traceback
    traceback.print_exc()
