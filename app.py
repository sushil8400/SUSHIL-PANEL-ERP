
from flask import Flask, render_template, request, redirect, url_for, session, send_file
import sqlite3, os, io
from datetime import datetime
from openpyxl import Workbook
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY","CHANGE-ME")
DB=os.path.join(os.path.dirname(__file__),"erp.db")

LK_PRODUCTS=[
("Ammeter Selector Switch","Line Currents with OFF with CT","61325 SAB13TDYR","6A",410),
("Ammeter Selector Switch","Line Currents with OFF with CT","61325 SBB13TDYR","10A",425),
("Ammeter Selector Switch","Line Currents with OFF with CT","61325 SCB03TDYR","16A",645),
("Ammeter Selector Switch","Direct Currents with OFF without CT","71000 SCB03TDYR","16A",1975),
("Ammeter Selector Switch","Direct Currents with OFF without CT","71000 SEB03TDYR","25A",2350),
("Ammeter Selector Switch","Direct Currents with OFF without CT","71000 SFB03TDYR","32A",2820),
("Voltmeter Selector Switch","Voltage between Phases with OFF","61312 SAB13TDYR","6A",300),
("Voltmeter Selector Switch","Voltage between Phases with OFF","61312 SBB13TDYR","10A",390),
("Voltmeter Selector Switch","Voltage between Phases with OFF","61312 SCB03TDYR","16A",575),
("Voltmeter Selector Switch","Phase & Neutral with OFF","61313 SAB13TDYR","6A",540),
("Voltmeter Selector Switch","Phase & Neutral with OFF","61313 SBB13TDYR","10A",755),
("Voltmeter Selector Switch","Phase & Neutral with OFF","61313 SCB03TDYR","16A",1085),
("Breaker Control Switch","1 Trip + 1 Close","73257SEB03PGBB","25A",1505),
("Breaker Control Switch","2 Trip + 2 Close","72009SEB03PGBB","25A",1765),
("Multi Step Switch","1P 3W W/O OFF","61049","6A",280),
("Multi Step Switch","2P 3W W/O OFF","61069","6A",410),
("Multi Step Switch","1P 4W W/O OFF","61050","6A",310),
("Multi Step Switch","2P 4W W/O OFF","61070","6A",460),
]

def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init():
 c=db()
 c.executescript("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,password TEXT);
 CREATE TABLE IF NOT EXISTS costings(id INTEGER PRIMARY KEY,number TEXT,customer TEXT,project TEXT,panel TEXT,material REAL,labour REAL,busbar REAL,fabrication REAL,misc REAL,overhead REAL,profit REAL,gst REAL,grand REAL,created TEXT);
 CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY,costing_id INTEGER,description TEXT,rating TEXT,catalogue TEXT,qty REAL,lp REAL,discount REAL,net REAL);""")
 if not c.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
  c.execute("INSERT INTO users(username,password) VALUES(?,?)",("admin",generate_password_hash("Admin@123")))
 c.commit();c.close()
def login_required(f):
 @wraps(f)
 def w(*a,**k):
  if not session.get("user"): return redirect(url_for("login"))
  return f(*a,**k)
 return w

@app.route("/login",methods=["GET","POST"])
def login():
 if request.method=="POST":
  r=db().execute("SELECT * FROM users WHERE username=?",(request.form["username"],)).fetchone()
  if r and check_password_hash(r["password"],request.form["password"]):
   session["user"]=r["username"]; return redirect("/")
  return render_template("login.html",error="Invalid login")
 return render_template("login.html")
@app.route("/logout")
def logout(): session.clear(); return redirect("/login")
@app.route("/")
@login_required
def home():
 c=db(); rows=c.execute("SELECT * FROM costings ORDER BY id DESC").fetchall();c.close()
 return render_template("home.html",rows=rows)
@app.route("/new",methods=["GET","POST"])
@login_required
def new():
 if request.method=="POST":
  f=request.form
  def n(x): 
   try:return float(f.get(x,0) or 0)
   except:return 0
  desc=f.getlist("description[]"); qty=f.getlist("qty[]"); lp=f.getlist("lp[]"); disc=f.getlist("discount[]")
  nets=[]
  for i in range(len(desc)):
   try:nets.append(float(qty[i] or 0)*float(lp[i] or 0)*(1-float(disc[i] or 0)/100))
   except:nets.append(0)
  material=sum(nets); labour=n("labour"); busbar=n("busbar"); fabrication=n("fabrication"); misc=n("misc"); overhead=n("overhead")
  subtotal=material+labour+busbar+fabrication+misc+overhead
  profit=subtotal*n("profit_pct")/100; taxable=subtotal+profit; gst=taxable*n("gst_pct")/100; grand=taxable+gst
  c=db(); num="CST-"+datetime.now().strftime("%Y%m%d-%H%M%S")
  cur=c.execute("INSERT INTO costings(number,customer,project,panel,material,labour,busbar,fabrication,misc,overhead,profit,gst,grand,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(num,f.get("customer"),f.get("project"),f.get("panel"),material,labour,busbar,fabrication,misc,overhead,profit,gst,grand,datetime.now().strftime("%d-%m-%Y %H:%M")))
  cid=cur.lastrowid
  for i,d in enumerate(desc):
   c.execute("INSERT INTO items(costing_id,description,rating,catalogue,qty,lp,discount,net) VALUES(?,?,?,?,?,?,?,?)",(cid,d,f.getlist("rating[]")[i],f.getlist("catalogue[]")[i],float(qty[i] or 0),float(lp[i] or 0),float(disc[i] or 0),nets[i]))
  c.commit();c.close();return redirect("/")
 return render_template("new.html",products=LK_PRODUCTS)
@app.route("/edit/<int:cid>",methods=["GET","POST"])
@login_required
def edit(cid):
 # Existing costing can be opened; use duplicate/edit workflow to preserve data safely.
 c=db(); row=c.execute("SELECT * FROM costings WHERE id=?",(cid,)).fetchone(); its=c.execute("SELECT * FROM items WHERE costing_id=?",(cid,)).fetchall();c.close()
 return render_template("edit.html",row=row,items=its,products=LK_PRODUCTS)
@app.route("/export/<int:cid>")
@login_required
def export(cid):
 c=db();r=c.execute("SELECT * FROM costings WHERE id=?",(cid,)).fetchone();its=c.execute("SELECT * FROM items WHERE costing_id=?",(cid,)).fetchall();c.close()
 wb=Workbook();ws=wb.active;ws.title="Costing"
 ws.append(["SUSHIL PANEL ERP - LK COSTING"]);ws.append(["Costing No",r["number"]]);ws.append(["Customer",r["customer"]]);ws.append(["Project",r["project"]]);ws.append(["Panel",r["panel"]]);ws.append([])
 ws.append(["S.No.","Description","Rating","Catalogue","Qty","LP Price","Discount %","Net Price"])
 for i,x in enumerate(its,1):ws.append([i,x["description"],x["rating"],x["catalogue"],x["qty"],x["lp"],x["discount"],x["net"]])
 ws.append([]);ws.append(["Material Total",r["material"]]);ws.append(["Labour",r["labour"]]);ws.append(["Busbar",r["busbar"]]);ws.append(["Fabrication",r["fabrication"]]);ws.append(["Miscellaneous",r["misc"]]);ws.append(["Overhead",r["overhead"]]);ws.append(["Profit",r["profit"]]);ws.append(["GST",r["gst"]]);ws.append(["GRAND TOTAL",r["grand"]])
 b=io.BytesIO();wb.save(b);b.seek(0)
 return send_file(b,as_attachment=True,download_name=r["number"]+".xlsx",mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
init()
