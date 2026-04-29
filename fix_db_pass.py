import sys
sys.path.append('./services/backend')
from app.auth.security import hash_password
import sqlite3

new_hash = hash_password('Zafu@104021')
conn = sqlite3.connect('services/backend/auth.db')
cursor = conn.cursor()
cursor.execute("UPDATE users SET password_hash = ? WHERE email = ?", (new_hash, '1447954419@qq.com'))
conn.commit()
conn.close()
print('Success')
