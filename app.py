from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
import sqlite3
import os
import io
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from openpyxl import Workbook

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "CHANGE-THIS-SECRET-KEY")

DB = os.path.join(os.path.dirname(__file__), "erp.db")


def con():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    db = con()
    cur = db.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    );

    CREATE TABLE IF NOT EXISTS customers(
        id INTEGER PRIMARY KEY,
        name TEXT,
        contact TEXT,
        email TEXT,
        address TEXT
    );

    CREATE TABLE IF NOT EXISTS projects(
        id INTEGER PRIMARY KEY,
        customer_id INTEGER,
        name TEXT,
        location TEXT,
        status TEXT
    );

    CREATE TABLE IF NOT EXISTS costings(
        id INTEGER PRIMARY KEY,
        number TEXT UNIQUE,
        customer TEXT,
        project TEXT,
        panel TEXT,
        material REAL,
        labour REAL,
        fabrication REAL,
        busbar REAL,
        wiring REAL,
        overhead REAL,
        packing REAL,
        transport REAL,
        profit_pct REAL,
        gst_pct REAL,
        final REAL,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS costing_items(
        id INTEGER PRIMARY KEY,
        costing_id INTEGER,
        sno INTEGER,
        description TEXT,
        rating TEXT,
        catalogue TEXT,
        qty REAL,
        lp REAL,
        discount REAL,
        discount_amount REAL,
        final_price REAL
    );
    """)

    user = cur.execute(
        "SELECT 1 FROM users WHERE username=?",
        ("admin",)
    ).fetchone()

    if not user:
        cur.execute(
            "INSERT INTO users(username,password,role) VALUES(?,?,?)",
            (
                "admin",
                generate_password_hash("Admin@123"),
                "Admin"
            )
        )

    db.commit()
    db.close()


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return wrapper


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"]

        db = con()

        row = db.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

        db.close()

        if row and check_password_hash(
            row["password"],
            password
        ):

            session["user"] = row["username"]
            session["role"] = row["role"]

            return redirect(
                url_for("dashboard")
            )

        flash("Invalid username or password")

    return render_template("login.html")


@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


@app.route("/export/<int:cid>")
@login_required
def export(cid):

    db = con()

    stats = {
        "customers": db.execute(
            "SELECT COUNT(*) AS n FROM customers"
        ).fetchone()["n"],

        "projects": db.execute(
            "SELECT COUNT(*) AS n FROM projects"
        ).fetchone()["n"],

        "costings": db.execute(
            "SELECT COUNT(*) AS n FROM costings"
        ).fetchone()["n"]
    }

    recent = db.execute(
        "SELECT * FROM costings "
        "ORDER BY id DESC LIMIT 8"
    ).fetchall()

    db.close()

    return render_template(
        "dashboard.html",
        stats=stats,
        recent=recent
    )


@app.route(
    "/customers",
    methods=["GET", "POST"]
)
@login_required
def customers():

    db = con()

    if request.method == "POST":

        db.execute(
            """
            INSERT INTO customers(
                name,
                contact,
                email,
                address
            )
            VALUES(?,?,?,?)
            """,
            (
                request.form["name"],
                request.form["contact"],
                request.form["email"],
                request.form["address"]
            )
        )

        db.commit()

        flash("Customer saved")

    rows = db.execute(
        "SELECT * FROM customers "
        "ORDER BY id DESC"
    ).fetchall()

    db.close()

    return render_template(
        "customers.html",
        rows=rows
    )


@app.route(
    "/projects",
    methods=["GET", "POST"]
)
@login_required
def projects():

    db = con()

    if request.method == "POST":

        db.execute(
            """
            INSERT INTO projects(
                customer_id,
                name,
                location,
                status
            )
            VALUES(?,?,?,?)
            """,
            (
                request.form["customer_id"],
                request.form["name"],
                request.form["location"],
                request.form["status"]
            )
        )

        db.commit()

        flash("Project saved")

    customer_rows = db.execute(
        "SELECT * FROM customers "
        "ORDER BY name"
    ).fetchall()

    rows = db.execute(
        """
        SELECT
            p.*,
            c.name AS customer

        FROM projects p

        LEFT JOIN customers c
        ON c.id = p.customer_id

        ORDER BY p.id DESC
        """
    ).fetchall()

    db.close()

    return render_template(
        "projects.html",
        customers=customer_rows,
        rows=rows
    )


@app.route("/costing/new")
@login_required
def new_costing():

    return render_template(
        "costing.html"
    )


@app.route(
    "/costing/save",
    methods=["POST"]
)
@login_required
def save_costing():

    form = request.form

    def num(name):

        try:
            return float(
                form.get(name, 0) or 0
            )

        except (ValueError, TypeError):
            return 0

    material = num("material")

    extras = sum(
        num(name)
        for name in [
            "labour",
            "fabrication",
            "busbar",
            "wiring",
            "overhead",
            "packing",
            "transport"
        ]
    )

    profit = (
        (material + extras)
        * num("profit")
        / 100
    )

    taxable = (
        material
        + extras
        + profit
    )

    gst = (
        taxable
        * num("gst")
        / 100
    )

    final = taxable + gst

    number = (
        "CST-"
        + datetime.now().strftime(
            "%Y%m%d-%H%M%S"
        )
    )

    db = con()

    cur = db.cursor()

    cur.execute(
        """
        INSERT INTO costings(
            number,
            customer,
            project,
            panel,
            material,
            labour,
            fabrication,
            busbar,
            wiring,
            overhead,
            packing,
            transport,
            profit_pct,
            gst_pct,
            final,
            created_at
        )
        VALUES(
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )
        """,
        (
            number,
            form.get("customer"),
            form.get("project"),
            form.get("panel"),
            material,
            num("labour"),
            num("fabrication"),
            num("busbar"),
            num("wiring"),
            num("overhead"),
            num("packing"),
            num("transport"),
            num("profit"),
            num("gst"),
            final,
            datetime.now().strftime(
                "%d-%m-%Y %H:%M"
            )
        )
    )

    costing_id = cur.lastrowid

    descriptions = form.getlist(
        "description[]"
    )

    qty_list = form.getlist(
        "qty[]"
    )

    lp_list = form.getlist(
        "lp[]"
    )

    discount_list = form.getlist(
        "discount[]"
    )

    rating_list = form.getlist(
        "rating[]"
    )

    catalogue_list = form.getlist(
        "catalogue[]"
    )

    for i, description in enumerate(
        descriptions
    ):

        qty = float(
            qty_list[i] or 0
        )

        lp = float(
            lp_list[i] or 0
        )

        discount = float(
            discount_list[i] or 0
        )

        discount_amount = (
            qty
            * lp
            * discount
            / 100
        )

        final_price = (
            qty * lp
            - discount_amount
        )

        cur.execute(
            """
            INSERT INTO costing_items(
                costing_id,
                sno,
                description,
                rating,
                catalogue,
                qty,
                lp,
                discount,
                discount_amount,
                final_price
            )
            VALUES(
                ?,?,?,?,?,?,?,?,?,?
            )
            """,
            (
                costing_id,
                i + 1,
                description,
                rating_list[i],
                catalogue_list[i],
                qty,
                lp,
                discount,
                discount_amount,
                final_price
            )
        )

    db.commit()

    db.close()

    flash(
        "Costing saved: "
        + number
    )

    return redirect(
        url_for("costings")
    )


@app.route("/costings")
@login_required
def costings():

    db = con()

    rows = db.execute(
        "SELECT * FROM costings "
        "ORDER BY id DESC"
    ).fetchall()

    db.close()

    return render_template(
        "costings.html",
        rows=rows
    )


@app.route("/export/<int:cid>")
@login_required
def export(cid):

    db = con()

    costing = db.execute(
        "SELECT * FROM costings "
        "WHERE id=?",
        (cid,)
    ).fetchone()

    items = db.execute(
        """
        SELECT *
        FROM costing_items

        WHERE costing_id=?

        ORDER BY sno
        """,
        (cid,)
    ).fetchall()

    db.close()

    wb = Workbook()

    ws = wb.active

    ws.title = "Costing"

    ws.append([
        "SUSHIL PANEL ERP - COSTING"
    ])

    ws.append([
        "Costing No",
        costing["number"]
    ])

    ws.append([
        "Customer",
        costing["customer"]
    ])

    ws.append([
        "Project",
        costing["project"]
    ])

    ws.append([
        "Panel",
        costing["panel"]
    ])

    ws.append([])

    ws.append([
        "S.No.",
        "Description",
        "Rating",
        "Type/Catalogue",
        "Qty",
        "LP Price",
        "Discount %",
        "Discount Amount",
        "Final Price"
    ])

    for item in items:

        ws.append([
            item["sno"],
            item["description"],
            item["rating"],
            item["catalogue"],
            item["qty"],
            item["lp"],
            item["discount"],
            item["discount_amount"],
            item["final_price"]
        ])

    ws.append([])

    ws.append([
        "FINAL SELLING PRICE",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        costing["final"]
    ])

    output = io.BytesIO()

    wb.save(output)

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=(
            costing["number"]
            + ".xlsx"
        ),
        mimetype=(
            "application/"
            "vnd.openxmlformats-"
            "officedocument."
            "spreadsheetml.sheet"
        )
    )


init_db()


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=False
    )
