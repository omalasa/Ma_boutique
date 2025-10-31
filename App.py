import os
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from datetime import date, datetime
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
import pandas as pd
import io

# ====== INITIALISATION DE LA BASE ======
def init_db():
    conn = sqlite3.connect("ventes.db")
    c = conn.cursor()
    # Table produit
    c.execute("""
        CREATE TABLE IF NOT EXISTS produit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL
        )
    """)
    # Table ventes
    c.execute("""
        CREATE TABLE IF NOT EXISTS ventes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produit TEXT,
            quantite INTEGER,
            prix_unitaire REAL,
            total REAL,
            date TEXT
        )
    """)
    # Table approvisionnements
    c.execute("""
        CREATE TABLE IF NOT EXISTS approvisionnements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produit TEXT,
            quantite INTEGER,
            prix_achat_unitaire REAL,
            total_achat REAL,
            date TEXT
        )
    """)
    # Table utilisateurs
    c.execute("""
        CREATE TABLE IF NOT EXISTS utilisateurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    # Création admin par défaut
    c.execute("SELECT * FROM utilisateurs WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = generate_password_hash("admin123")
        c.execute("INSERT INTO utilisateurs (username, password) VALUES (?, ?)", ("admin", hashed_pw))
    conn.commit()
    conn.close()

# ====== FLASK APP ======
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey123")  # clé secrète pour déploiement

# ====== DECORATEUR LOGIN ======
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ====== LOGIN ======
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect("ventes.db")
        c = conn.cursor()
        c.execute("SELECT password FROM utilisateurs WHERE username=?", (username,))
        row = c.fetchone()
        conn.close()
        if row and check_password_hash(row[0], password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            error = "Nom d'utilisateur ou mot de passe incorrect"
    return render_template('login.html', error=error)

# ====== LOGOUT ======
@app.route('/logout')
@login_required
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

# ====== INDEX ======
@app.route('/', methods=['GET'])
@login_required
def index():
    recherche = request.args.get('recherche', '')
    conn = sqlite3.connect("ventes.db")
    c = conn.cursor()
    if recherche:
        c.execute("SELECT * FROM ventes WHERE produit LIKE ? OR date LIKE ? ORDER BY date DESC",
                  (f"%{recherche}%", f"%{recherche}%"))
    else:
        c.execute("SELECT * FROM ventes ORDER BY date DESC")
    ventes = c.fetchall()
    total_general = sum([vente[4] for vente in ventes])
    conn.close()
    return render_template("index.html", ventes=ventes, total_general=total_general,
                           recherche=recherche, username=session['username'])

# ====== AJOUTER UNE VENTE ======
@app.route('/ajouter', methods=['GET', 'POST'])
@login_required
def ajouter():
    if request.method == 'POST':
        produit = request.form['produit']
        quantite = int(request.form['quantite'])
        prix_unitaire = float(request.form['prix_unitaire'])
        total = quantite * prix_unitaire
        date_vente = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect("ventes.db")
        c = conn.cursor()
        c.execute("INSERT INTO ventes (produit, quantite, prix_unitaire, total, date) VALUES (?, ?, ?, ?, ?)",
                  (produit, quantite, prix_unitaire, total, date_vente))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    # dans ajouter(), en GET :
    conn = sqlite3.connect("ventes.db")
    c = conn.cursor()
    c.execute("SELECT nom FROM produit ORDER BY nom")
    produits = [row[0] for row in c.fetchall()]
    conn.close()
    return render_template("ajouter.html", produits=produits, username=session['username'])

# ====== APPROVISIONNEMENT ======
@app.route('/approvisionnement', methods=['GET', 'POST'])
@login_required
def approvisionnement():
    conn = sqlite3.connect("ventes.db")
    c = conn.cursor()
    if request.method == 'POST':
        produit = request.form['produit']
        quantite = int(request.form['quantite'])
        prix_achat_unitaire = float(request.form['prix_achat_unitaire'])
        total_achat = quantite * prix_achat_unitaire
        date_achat = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO approvisionnements (produit, quantite, prix_achat_unitaire, total_achat, date) VALUES (?, ?, ?, ?, ?)",
                  (produit, quantite, prix_achat_unitaire, total_achat, date_achat))
        conn.commit()
        return redirect(url_for('approvisionnement'))
    c.execute("SELECT * FROM approvisionnements ORDER BY date DESC")
    approv = c.fetchall()
    conn.close()

    conn = sqlite3.connect("ventes.db")
    c = conn.cursor()
    c.execute("SELECT nom FROM produit ORDER BY nom")
    produits = [row[0] for row in c.fetchall()]

    # ensuite récupère aussi les approv existants
    c.execute("SELECT * FROM approvisionnements ORDER BY date DESC")
    approv = c.fetchall()
    conn.close()
    return render_template("approvisionnement.html", approv=approv, produits=produits, username=session['username'])

# ====== BILAN ======
@app.route('/bilan')
@login_required
def bilan():
    conn = sqlite3.connect("ventes.db")
    c = conn.cursor()
    aujourd_hui = date.today().strftime("%Y-%m-%d")
    mois_actuel = date.today().strftime("%Y-%m")
    c.execute("SELECT SUM(total) FROM ventes WHERE date LIKE ?", (f"{aujourd_hui}%",))
    total_ventes_jour = c.fetchone()[0] or 0
    c.execute("SELECT SUM(total) FROM ventes WHERE date LIKE ?", (f"{mois_actuel}%",))
    total_ventes_mois = c.fetchone()[0] or 0
    c.execute("SELECT SUM(total_achat) FROM approvisionnements WHERE date LIKE ?", (f"{aujourd_hui}%",))
    total_achats_jour = c.fetchone()[0] or 0
    c.execute("SELECT SUM(total_achat) FROM approvisionnements WHERE date LIKE ?", (f"{mois_actuel}%",))
    total_achats_mois = c.fetchone()[0] or 0
    resultat_jour = total_ventes_jour - total_achats_jour
    resultat_mois = total_ventes_mois - total_achats_mois
    conn.close()
    return render_template("bilan.html",
                           aujourd_hui=aujourd_hui,
                           total_ventes_jour=total_ventes_jour,
                           total_achats_jour=total_achats_jour,
                           resultat_jour=resultat_jour,
                           total_ventes_mois=total_ventes_mois,
                           total_achats_mois=total_achats_mois,
                           resultat_mois=resultat_mois,
                           username=session['username'])


# ---- Gestion des produits ----
@app.route('/produits', methods=['GET'])
@login_required   # si tu utilises login_required ; sinon retire cette ligne
def produits_liste():
    conn = sqlite3.connect("ventes.db")
    c = conn.cursor()
    c.execute("SELECT id, nom FROM produit ORDER BY nom")
    produits = c.fetchall()
    conn.close()
    return render_template("produits.html", produits=produits)

@app.route('/produits/ajouter', methods=['POST'])
@login_required
def produits_ajouter():
    nom = request.form.get('nom', '').strip()
    if not nom:
        # tu peux flasher un message si tu utilises flash
        return redirect(url_for('produits_liste'))

    conn = sqlite3.connect("ventes.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO produit (nom) VALUES (?)", (nom,))
        conn.commit()
    except sqlite3.IntegrityError:
        # produit existant — ignore ou gérer l'erreur
        pass
    conn.close()
    return redirect(url_for('produits_liste'))

@app.route('/produits/modifier/<int:id>', methods=['POST'])
@login_required
def produits_modifier(id):
    nom = request.form.get('nom', '').strip()
    if nom:
        conn = sqlite3.connect("ventes.db")
        c = conn.cursor()
        c.execute("UPDATE produit SET nom=? WHERE id=?", (nom, id))
        conn.commit()
        conn.close()
    return redirect(url_for('produits_liste'))

@app.route('/produits/supprimer/<int:id>', methods=['GET'])
@login_required
def produits_supprimer(id):
    conn = sqlite3.connect("ventes.db")
    c = conn.cursor()
    c.execute("DELETE FROM produit WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('produits_liste'))

# ==========================
# EXPORTATION PDF
# ==========================
@app.route('/export_pdf')
@login_required
def export_pdf():
    try:
        conn = sqlite3.connect("ventes.db")
        c = conn.cursor()
        c.execute("SELECT date, produit, quantite, prix_unitaire, total FROM ventes")
        ventes = c.fetchall()
        conn.close()

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm)
        styles = getSampleStyleSheet()
        elements = []

        titre_style = ParagraphStyle(
            name="Titre",
            parent=styles["Heading1"],
            fontName="Times-Roman",
            fontSize=18,
            textColor=colors.HexColor("#1E90FF"),
            alignment=1,
            spaceAfter=20
        )
        elements.append(Paragraph("Bilan des Ventes", titre_style))
        elements.append(Spacer(1, 10))

        data = [["Date", "Produit", "Quantité", "Prix unitaire", "Total (FCFA)"]]
        total_general = 0

        for vente in ventes:
            date_v, produit, quantite, prix_unitaire, total = vente
            total_fmt = f"{int(total):,}".replace(",", " ")
            data.append([date_v, produit, str(quantite), prix_unitaire, total_fmt])
            total_general += int(total)

        data.append(["", "", "", "Total :", f"{total_general:,}".replace(",", " ")])

        table = Table(data, colWidths=[3.5*cm, 6*cm, 3*cm, 3.5*cm, 3.5*cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ]))

        elements.append(table)
        doc.build(elements)

        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name="Bilan_ventes.pdf", mimetype="application/pdf")
    except Exception as e:
        return f"Erreur lors de la génération du PDF : {e}"


# ==========================
# EXPORTATION EXCEL
# ==========================
@app.route('/export/excel')
@login_required
def export_excel():
    conn = sqlite3.connect("ventes.db")
    df = pd.read_sql_query("SELECT * FROM ventes ORDER BY date DESC", conn)
    conn.close()

    if df.empty:
        return "Aucune vente à exporter."

    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, sheet_name="Ventes")
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="ventes.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# ==========================

@app.route("/utilisateurs", methods=["GET", "POST"])
def utilisateurs():
    if "username" not in session:
        return redirect(url_for("login"))
    
    # Seul l'admin peut accéder à la gestion des utilisateurs
    if session["username"] != "admin":
        return redirect(url_for("index"))

    conn = sqlite3.connect("ventes.db")
    c = conn.cursor()

    # Ajout d'un utilisateur
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        if username and password:
            try:
                hashed_pw = generate_password_hash(password)
                c.execute("INSERT INTO utilisateurs (username, password) VALUES (?, ?)", (username, hashed_pw))
                conn.commit()
                message = f"✅ Utilisateur '{username}' ajouté avec succès."
            except sqlite3.IntegrityError:
                message = f"⚠️ Le nom d'utilisateur '{username}' existe déjà."
        else:
            message = "⚠️ Tous les champs sont requis."
    else:
        message = ""

    # Récupérer tous les utilisateurs
    c.execute("SELECT id, username FROM utilisateurs")
    users = c.fetchall()
    conn.close()

    return render_template("utilisateurs.html", utilisateurs=users, message=message)

# ==========================
@app.route("/modifier/<int:id>", methods=["GET", "POST"])
def modifier_vente(id):
    if "username" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("ventes.db")
    c = conn.cursor()

    # Récupérer la vente à modifier
    c.execute("SELECT id, produit, quantite, prix_unitaire, total, date FROM ventes WHERE id = ?", (id,))
    vente = c.fetchone()

    if not vente:
        conn.close()
        flash("Vente introuvable.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        produit = request.form["produit"]
        quantite = int(request.form["quantite"])
        prix_unitaire = float(request.form["prix_unitaire"])
        total = quantite * prix_unitaire
        date_vente = request.form["date"]

        # Mise à jour de la vente
        c.execute("""
            UPDATE ventes
            SET produit = ?, quantite = ?, prix_unitaire = ?, total = ?, date = ?
            WHERE id = ?
        """, (produit, quantite, prix_unitaire, total, date_vente, id))
        conn.commit()
        conn.close()

        flash("✅ Vente modifiée avec succès.", "success")
        return redirect(url_for("index"))

    conn.close()
    return render_template("modifier_vente.html", vente=vente)

# ==========================
@app.route("/supprimer/<int:id>")
def supprimer_vente(id):
    if "username" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("ventes.db")
    c = conn.cursor()
    c.execute("DELETE FROM ventes WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    flash("❌ Vente supprimée avec succès.", "info")
    return redirect(url_for("index"))



# ====== LANCEMENT DU SERVEUR ======
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)