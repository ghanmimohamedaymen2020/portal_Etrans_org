from dotenv import load_dotenv
load_dotenv('.env', override=True)

import json
from app import create_app
from app.models.user import User

app = create_app()
c = app.test_client()

with app.app_context():
    u = User.query.first()
    if not u:
        print("ERROR: aucun utilisateur en base")
        exit(1)

with c.session_transaction() as s:
    s['_user_id'] = str(u.id)
    s['_fresh'] = True

r = c.get('/api/admin/summary')
print('STATUS=', r.status_code)
if r.status_code == 200:
    d = json.loads(r.data)
    print('total_users=', d.get('total_users'))
    print('active_users=', d.get('active_users'))
    print('connexions_today=', d.get('connexions_today'))
    print('connected_now=', d.get('connected_now'))
    print('roles=', d.get('roles'))
    print('activity_labels=', d.get('activity', {}).get('labels'))
    print('API_OK')
else:
    print('ERROR body=', r.data.decode())
