from flask import Flask,request,redirect,url_for,session,render_template,flash
import sqlite3,os
from werkzeug.security import generate_password_hash,check_password_hash
app=Flask(__name__);app.secret_key=os.environ.get("SECRET_KEY","change-me")
DB="erp.db"
def con():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def init():
 c=con();c.executescript("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,password TEXT);CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,description TEXT,rating TEXT,catalogue TEXT UNIQUE,lp REAL);CREATE TABLE IF NOT EXISTS costings(id INTEGER PRIMARY KEY,number TEXT,customer TEXT,project TEXT,panel TEXT,material REAL,labour REAL,busbar REAL,fabrication REAL,miscellaneous REAL,overhead REAL,profit REAL,gst REAL,total REAL,created TEXT);CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY,costing_id INTEGER,description TEXT,rating TEXT,catalogue TEXT,qty REAL,lp REAL,discount REAL,net REAL);""")
 if not c.execute("SELECT 1 FROM users").fetchone():c.execute("INSERT INTO users(username,password) VALUES(?,?)",("admin",generate_password_hash("Admin@123")))
 if not c.execute("SELECT 1 FROM products").fetchone():c.executemany("INSERT INTO products(description,rating,catalogue,lp) VALUES(?,?,?,?)",[("MCB SP","6A SP 10kA","BB10060C",0),("MCB SP","32A SP 10kA","BB10320C",0),("MCCB","63A 4P 10kA","EM90984OOHO",0),("MCCB","400A 4P 36kA","CM98403OOROOG",0),("MCCB MICROPROCESSOR","1000A 4P 50kA","CM96112OOOOX1",0),("CHANGE OVER","1000A 4P","CO51000OOOO",0)])
 c.commit();c.close()
@app.before_request
def b():init()
def req(f):
 from functools import wraps
 @wraps(f)
 def w(*a,**k):
  if not session.get("u"):return redirect("/login")
  return f(*a,**k)
 return w
@app.route("/login",methods=["GET","POST"])
def login():
 if request.method=="POST":
  c=con();r=c.execute("SELECT * FROM users WHERE username=?",(request.form["username"],)).fetchone();c.close()
  if r and check_password_hash(r["password"],request.form["password"]):session["u"]=r["username"];return redirect("/")
  flash("Wrong login")
 return render_template("login.html")
@app.route("/logout")
def logout():session.clear();return redirect("/login")
@app.route("/")
@req
def home():
 c=con();rows=c.execute("SELECT * FROM costings ORDER BY id DESC").fetchall();c.close();return render_template("home.html",rows=rows)
@app.route("/products",methods=["GET","POST"])
@req
def products():
 c=con()
 if request.method=="POST":
  try:c.execute("INSERT INTO products(description,rating,catalogue,lp) VALUES(?,?,?,?)",(request.form["description"],request.form["rating"],request.form["catalogue"],float(request.form["lp"] or 0)));c.commit();flash("Product added")
  except Exception as e:flash(str(e))
 rows=c.execute("SELECT * FROM products ORDER BY description").fetchall();c.close();return render_template("products.html",rows=rows)
@app.route("/new")
@req
def new():
 c=con();p=[dict(x) for x in c.execute("SELECT * FROM products ORDER BY description")];c.close();return render_template("new.html",products=p)
@app.route("/save",methods=["POST"])
@req
def save():
 f=request.form
 def n(x):
  try:return float(f.get(x) or 0)
  except:return 0
 material=n("material");labour=n("labour");busbar=n("busbar");fab=n("fabrication");misc=n("miscellaneous");over=n("overhead");sub=material+labour+busbar+fab+misc+over;profit=sub*n("profit")/100;tax=sub+profit;gst=tax*n("gst")/100;total=tax+gst
 from datetime import datetime
 c=con();cur=c.cursor();num="CST-"+datetime.now().strftime("%Y%m%d-%H%M%S");cur.execute("INSERT INTO costings(number,customer,project,panel,material,labour,busbar,fabrication,miscellaneous,overhead,profit,gst,total,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(num,f.get("customer"),f.get("project"),f.get("panel"),material,labour,busbar,fab,misc,over,n("profit"),n("gst"),total,datetime.now().strftime("%d-%m-%Y %H:%M")));cid=cur.lastrowid
 for i,d in enumerate(f.getlist("description[]")):
  q=float(f.getlist("qty[]")[i] or 0);lp=float(f.getlist("lp[]")[i] or 0);di=float(f.getlist("discount[]")[i] or 0);cur.execute("INSERT INTO items(costing_id,description,rating,catalogue,qty,lp,discount,net) VALUES(?,?,?,?,?,?,?,?)",(cid,d,f.getlist("rating[]")[i],f.getlist("catalogue[]")[i],q,lp,di,q*lp*(1-di/100)))
 c.commit();c.close();return redirect("/")
if __name__=="__main__":init();app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
