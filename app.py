
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
import sqlite3, os, io
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from openpyxl import Workbook

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "CHANGE-THIS-SECRET-KEY")
DB = os.path.join(os.path.dirname(__file__), "erp.db")

def con():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    db=con(); cur=db.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT);
    CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY, name TEXT, contact TEXT, email TEXT, address TEXT);
    CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY, customer_id INTEGER, name TEXT, location TEXT, status TEXT);
    CREATE TABLE IF NOT EXISTS costings(id INTEGER PRIMARY KEY, number TEXT UNIQUE, customer TEXT, project TEXT, panel TEXT,
      material REAL, labour REAL, fabrication REAL, busbar REAL, wiring REAL, overhead REAL, packing REAL, transport REAL,
      profit_pct REAL, gst_pct REAL, final REAL, created_at TEXT);
    CREATE TABLE IF NOT EXISTS costing_items(id INTEGER PRIMARY KEY, costing_id INTEGER, sno INTEGER, description TEXT,
      rating TEXT, catalogue TEXT, qty REAL, lp REAL, discount REAL, discount_amount REAL, final_price REAL);
    """)
    if not cur.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
        cur.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",
                    ("admin", generate_password_hash("Admin@123"), "Admin"))
    db.commit(); db.close()

def login_required(f):
    @wraps(f)
    def w(*a,**k):
        if "user" not in session: return redirect(url_for("login"))
        return f(*a,**k)
    return w

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=request.form["username"].strip(); p=request.form["password"]
        db=con(); row=db.execute("SELECT * FROM users WHERE username=?",(u,)).fetchone(); db.close()
        if row and check_password_hash(row["password"],p):
            session["user"]=row["username"]; session["role"]=row["role"]; return redirect(url_for("dashboard"))
        flash("Invalid username or password")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/")
@login_required
def dashboard():
    db=con()
    stats={"customers":db.execute("SELECT COUNT(*) n FROM customers").fetchone()["n"],
           "projects":db.execute("SELECT COUNT(*) n FROM projects").fetchone()["n"],
           "costings":db.execute("SELECT COUNT(*) n FROM costings").fetchone()["n"]}
    recent=db.execute("SELECT * FROM costings ORDER BY id DESC LIMIT 8").fetchall(); db.close()
    return render_template("dashboard.html",stats=stats,recent=recent)

@app.route("/customers",methods=["GET","POST"])
@login_required
def customers():
    db=con()
    if request.method=="POST":
        db.execute("INSERT INTO customers(name,contact,email,address) VALUES(?,?,?,?)",
                   (request.form["name"],request.form["contact"],request.form["email"],request.form["address"]))
        db.commit(); flash("Customer saved")
    rows=db.execute("SELECT * FROM customers ORDER BY id DESC").fetchall(); db.close()
    return render_template("customers.html",rows=rows)

@app.route("/projects",methods=["GET","POST"])
@login_required
def projects():
    db=con()
    if request.method=="POST":
        db.execute("INSERT INTO projects(customer_id,name,location,status) VALUES(?,?,?,?)",
                   (request.form["customer_id"],request.form["name"],request.form["location"],request.form["status"]))
        db.commit(); flash("Project saved")
    customers=db.execute("SELECT * FROM customers ORDER BY name").fetchall()
    rows=db.execute("""SELECT p.*,c.name customer FROM projects p LEFT JOIN customers c ON c.id=p.customer_id ORDER BY p.id DESC""").fetchall()
    db.close(); return render_template("projects.html",customers=customers,rows=rows)

@app.route("/costing/new")
@login_required
def new_costing():
    return render_template("costing.html")

@app.route("/costing/save",methods=["POST"])
@login_required
def save_costing():
    f=request.form
    def num(x): 
        try:return float(f.get(x,0) or 0)
        except:return 0
    material=num("material"); extras=sum(num(x) for x in ["labour","fabrication","busbar","wiring","overhead","packing","transport"])
    profit=(material+extras)*num("profit")/100
    taxable=material+extras+profit; gst=taxable*num("gst")/100; final=taxable+gst
    number="CST-"+datetime.now().strftime("%Y%m%d-%H%M%S")
    db=con(); cur=db.cursor()
    cur.execute("""INSERT INTO costings(number,customer,project,panel,material,labour,fabrication,busbar,wiring,overhead,packing,transport,profit_pct,gst_pct,final,created_at)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (number,f.get("customer"),f.get("project"),f.get("panel"),material,num("labour"),num("fabrication"),num("busbar"),num("wiring"),num("overhead"),num("packing"),num("transport"),num("profit"),num("gst"),final,datetime.now().strftime("%d-%m-%Y %H:%M")))
    cid=cur.lastrowid
    desc=f.getlist("description[]")
    for i,d in enumerate(desc):
        q=float(f.getlist("qty[]")[i] or 0); lp=float(f.getlist("lp[]")[i] or 0); dis=float(f.getlist("discount[]")[i] or 0)
        da=q*lp*dis/100; fp=q*lp-da
        cur.execute("INSERT INTO costing_items(costing_id,sno,description,rating,catalogue,qty,lp,discount,discount_amount,final_price) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (cid,i+1,d,f.getlist("rating[]")[i],f.getlist("catalogue[]")[i],q,lp,dis,da,fp))
    db.commit(); db.close(); flash("Costing saved: "+number); return redirect(url_for("costings"))

@app.route("/costings")
@login_required
def costings():
    db=con(); rows=db.execute("SELECT * FROM costings ORDER BY id DESC").fetchall(); db.close()
    return render_template("costings.html",rows=rows)

@app.route("/export/<int:cid>")
@login_required
def export(cid):
    db=con(); c=db.execute("SELECT * FROM costings WHERE id=?",(cid,)).fetchone()
    items=db.execute("SELECT * FROM costing_items WHERE costing_id=? ORDER BY sno",(cid,)).fetchall(); db.close()
    wb=Workbook(); ws=wb.active; ws.title="Costing"
    ws.append(["SUSHIL PANEL ERP - COSTING"]); ws.append(["Costing No",c["number"]]); ws.append(["Customer",c["customer"]]); ws.append(["Project",c["project"]]); ws.append(["Panel",c["panel"]]); ws.append([])
    ws.append(["S.No.","Description","Rating","Type/Catalogue","Qty","LP Price","Discount %","Discount Amount","Final Price"])
    for x in items: ws.append([x["sno"],x["description"],x["rating"],x["catalogue"],x["qty"],x["lp"],x["discount"],x["discount_amount"],x["final_price"]])
    ws.append([]); ws.append(["FINAL SELLING PRICE","","","","","","","",c["final"]])
    bio=io.BytesIO(); wb.save(bio); bio.seek(0)
    return send_file(bio,as_attachment=True,download_name=c["number"]+".xlsx",mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__=="__main__":
    init_db()
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)
