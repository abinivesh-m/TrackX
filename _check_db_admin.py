import sqlite3, sys, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

db = sqlite3.connect(os.path.join('backend', 'trackx.db'))
cur = db.cursor()
cur.execute("SELECT username, is_active, is_admin FROM users")
rows = cur.fetchall()
print("users:", rows)
row = db.execute("SELECT hashed_password FROM users WHERE username='admin@trackx.com'").fetchone()
if row:
    from passlib.context import CryptContext
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    for pw in ('admin123', 'dev_admin_password_change_for_production', 'admin@trackx.com'):
        print(repr(pw), '->', ctx.verify(pw, row[0]))
else:
    print("no admin@trackx.com in trackx.db")
db.close()