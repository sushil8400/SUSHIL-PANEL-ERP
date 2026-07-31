from flask import Flask,render_template,request,redirect,url_for,session,send_file
import sqlite3,os,io
from werkzeug.security import generate_password_hash,check_password_hash
from openpyxl import Workbook
app=Flask(__name__);app.secret_key=os.getenv("SECRET_KEY","change-me")
DB="erp.db"
def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def init():
 c=db();c.executescript("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,password TEXT);CREATE TABLE IF NOT EXISTS costings(id INTEGER PRIMARY KEY,customer TEXT,project TEXT,panel TEXT,total REAL);CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY,costing_id INTEGER,sno INTEGER,brand TEXT,description TEXT,rating TEXT,catalogue TEXT,qty REAL,lp REAL,discount REAL,net REAL,final REAL);")
 if not c.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():c.execute("INSERT INTO users(username,password) VALUES(?,?)",("admin",generate_password_hash("Admin@123")))
 c.commit();c.close()
def auth(f):
 def w(*a,**k):
  if "u" not in session:return redirect("/login")
  return f(*a,**k)
 w.__name__=f.__name__;return w
@app.route("/login",methods=["GET","POST"])
def login():
 if request.method=="POST":
  c=db();u=c.execute("SELECT * FROM users WHERE username=?",(request.form["username"],)).fetchone();c.close()
  if u and check_password_hash(u["password"],request.form["password"]):session["u"]=u["username"];return redirect("/")
 return render_template("login.html")
@app.route("/logout")
def logout():session.clear();return redirect("/login")
@app.route("/")
@auth
def home():
 c=db();rows=c.execute("SELECT * FROM costings ORDER BY id DESC").fetchall();c.close();return render_template("home.html",rows=rows)
@app.route("/new",methods=["GET","POST"])
@auth
def new():
 if request.method=="POST":
  f=request.form;c=db();cur=c.cursor();cur.execute("INSERT INTO costings(customer,project,panel,total) VALUES(?,?,?,0)",(f["customer"],f["project"],f["panel"]));cid=cur.lastrowid;total=0
  for i,d in enumerate(f.getlist("description[]")):
   q=float(f.getlist("qty[]")[i]or 0);lp=float(f.getlist("lp[]")[i]or 0);di=float(f.getlist("discount[]")[i]or 0);net=lp*(100-di)/100;final=net*q;total+=final
   cur.execute("INSERT INTO items(costing_id,sno,brand,description,rating,catalogue,qty,lp,discount,net,final) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(cid,i+1,f.getlist("brand[]")[i],d,f.getlist("rating[]")[i],f.getlist("catalogue[]")[i],q,lp,di,net,final))
  cur.execute("UPDATE costings SET total=? WHERE id=?",(total,cid));c.commit();c.close();return redirect("/")
 return render_template("new.html")
init()
if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)))
