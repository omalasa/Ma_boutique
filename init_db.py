import sqlite3
from flask_bcrypt import Bcrypt
from flask import Flask

app = Flask(__name__)
bcrypt = Bcrypt(app)

conn = sqlite3.connect("boutique.db")
c = conn.cursor()

# Création de la table utilisateurs
c.execute("""
CREATE TABLE IF NOT EXISTS utilisateurs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT UNIQUE NOT NULL,
    mot_de_passe TEXT NOT NULL
)
""")

# Ajout d’un compte admin par défaut
mdp_hash = bcrypt.generate_password_hash("1234").decode("utf-8")
try:
    c.execute("INSERT INTO utilisateurs (nom, mot_de_passe) VALUES (?, ?)", ("admin", mdp_hash))
except sqlite3.IntegrityError:
    pass  # déjà existant

conn.commit()
conn.close()

print("✅ Base de données initialisée avec utilisateur admin (mot de passe : 1234)")
