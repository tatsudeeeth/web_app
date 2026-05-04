import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
import mariadb
from werkzeug.security import check_password_hash, generate_password_hash
from collections import OrderedDict
from datetime import date
import json

def get_conn():
    return mariadb.connect(
        host="192.168.2.5",
        port=3306,
        user="tester",
        password="test_pass",
        database="test",
        autocommit=True,
    )

'''
def get_conn() -> mariadb.Connection :
    return mariadb.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"],
        database=os.environ["DB_NAME"],
        autocommit=True,
    )
'''

def create_admin():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM employee WHERE account = ?;",
        ("admin", )
    )
    id = cur.fetchone()
    cur.close()

    if id is None:
        try:
            password = generate_pass("admin")

            cur = conn.cursor()

            cur.execute(
                "INSERT INTO employee (code, account, password_hash) VALUES (?, ?, ?);",
                ('AT0001', 'admin', password)
            )
            cur.close()

        except mariadb.IntegrityError:
            pass

    conn.close()


def authentication(account, password) -> tuple:

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, password_hash, need_change_pass FROM employee WHERE account = ?;",
        (account, )
    )
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user and check_password_hash(user[1], password):
        session["id"] = user[0]
        return True, user[2]

    return False, None


def generate_pass(password):
    return generate_password_hash(
        password,
        method="scrypt:32768:8:1"
    )


def get_department():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM depart WHERE is_active = 1;"
    )
    departs = cur.fetchall()
    cur.close()
    conn.close()
    return departs


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")


@app.route("/")
def index():
    if "user_id" in session:
        return f"ログイン中: {session['username']} <a href='/logout'>ログアウト</a>"
    # return "<a href='/'>ログイン</a>"
    return render_template("login.html")


@app.get("/login_error")
def login_error():
    return render_template("login.html")


@app.get("/reset_password")
def reset_password():
    return render_template("reset_password.html")


@app.post("/update_password")
def update_password():
    password = [
        request.form.get("pass0"),
        request.form.get("pass1"),
        request.form.get("pass2"),
    ]

    if password[1] != password[2]:
        flash("パスワードが一致しません")
        return render_template("reset_password.html")

    res = authentication(session["account"], password[0])

    if not res[0]:
        flash("現在のパスワードが一致しません")
        return render_template("reset_password.html")

    if password[0] == password[1]:
        flash("現在のパスワードと新しいパスワードが一致しています")
        return render_template("reset_password.html")

    password_hash = generate_pass(password[1])

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "UPDATE employee SET need_change_pass = 0, password_hash = ? WHERE id = ?;",
        (password_hash, session["id"])
    )

    cur.close()
    conn.close()
    flash("パスワードの再設定を行いました")
    return render_template("home.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/home", methods=["GET", "POST"])
def home():

    if request.method == "POST":
        account = request.form.get("account")
        password = request.form.get("password")
        if not account or not password:
            flash("ユーザー名とパスワードを入力してください")
            return redirect(url_for("login_error"))
        res, needs = authentication(account, password)
        if not res:
            flash("ユーザー名またはパスワードが正しくありません")
            return redirect(url_for("login_error"))
        session["account"] = account
        if needs == 1:
            return redirect(url_for("reset_password"))

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT updated_day, information FROM info ORDER BY updated_day DESC, id DESC LIMIT 20;"
    )

    rows = cur.fetchall()
    cur.close()

    cur = conn.cursor(dictionary=True)
    cur.execute(
        "select "
        "ace1.pushed_dt as begin, "
        "ace2.pushed_dt as end "
        "from attendance_summary asm "
        "right join calendar on asm.target_day = calendar.cal_date "
        "left join employee on asm.e_id = employee.id "
        "left join attendance_pair ap on asm.id = ap.s_id "
        "left join attendance as ace1 on ap.start_a_id = ace1.id "
        "left join attendance as ace2 on ap.end_a_id = ace2.id "
        "where employee.id = ? and date(cal_date) = ? and record_type = ?  "
        "order by cal_date, asm.id;",
        (session["id"], date.today(), "勤務時間")
    )
    row = cur.fetchone()
    
    cur.close()
    conn.close()

    begin = ""
    end = ""

    if row is not None:
        if row.get("begin") is not None:
            begin = row["begin"]

        if row.get("end") is not None:
            end = row["end"]

    return render_template("home.html", rows=rows, begin=begin, end=end)


@app.get("/attendance")
def attendance():
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "select cal_date, ace1.calc_dt as begin, ace2.calc_dt as end, record_type "
        "from calendar "
        "left join attendance_summary as asm on calendar.cal_date = asm.target_day "
        "left join employee on asm.e_id = employee.id "
        "left join attendance_pair as ap on asm.id = ap.s_id "
        "left join attendance as ace1 on ap.start_a_id = ace1.id "
        "left join attendance as ace2 on ap.end_a_id = ace2.id "
        "where (employee.id = ? or asm.e_id is null) and month(cal_date) = ? "
        "order by cal_date, ap.id;",
        (session["id"], date.today().month)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    grouped = OrderedDict()

    for row in rows:
        day = row["cal_date"]
        if day not in grouped:
            grouped[day] = []

        grouped[day].append(row)

    return render_template("attendance.html", grouped=grouped)


@app.post("/in_time")
def in_time():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("CALL set_start_time(?)", (session["id"],))
    cur.close()
    conn.close()
    return redirect(url_for("home"))


@app.post("/out_time")
def out_time():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("CALL set_end_time(?)", (session["id"],))
    cur.close()
    conn.close()
    return redirect(url_for("home"))


@app.get("/workflow")
def workflow():

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT status, title, CONCAT(family_name, first_name), requested_at, request_type "
        "FROM attendance_application "
        "LEFT JOIN employee ON attendance_application.requested_by = employee.id "
        "WHERE requested_by = ? "
        "ORDER BY requested_at DESC;",
        (session["id"], )
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("workflow.html", rows=rows)


@app.get("/workflow/flow1")
def flow1():
    fields = ["title", "department", "requested_at", "requested_by", "request_type", "reason", "start_day", "end_day",
              "start_time", "end_time", "status"]
    request_type = [
        "遅刻",
        "早退",
        "欠勤",
        "有休",
        "半休(午前休)",
        "半休(午後休)",
        "代休",
        "特休",
        "慶弔休",
        "赴任休",
        "その他"
    ]
    form_data = {f: None for f in fields}
    return render_template("flow1.html", departments=get_department(), form_data=form_data, request_type=request_type, today=date.today())


@app.post("/flow1/add")
def flow1_add():
    fields = ["title", "department", "requested_at", "requested_by", "request_type", "reason", "start_day", "end_day", "start_time", "end_time"]
    request_type = [
        "遅刻",
        "早退",
        "欠勤",
        "有休",
        "半休(午前休)",
        "半休(午後休)",
        "代休",
        "特休",
        "慶弔休",
        "赴任休",
        "その他"
    ]

    data = {f: request.form.get(f) for f in fields}

    for i in ["end_day", "start_time", "end_time"]:
        if not data[i]:
            data[i] = None

    if data["request_type"] == "遅刻":
        if data["start_time"] is None:
            flash("遅刻申請の場合は出勤時刻必須です")
            return render_template("flow1.html", form_data=data, departments=get_department(), request_type=request_type)

    if data["request_type"] == "早退":
        if data["end_day"] is None:
            flash("早退申請の場合は退勤時刻は必須です")
            return render_template("flow1.html", form_data=data, departments=get_department(), request_type=request_type)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM employee WHERE CONCAT(family_name, first_name) = ?"
    ,(data["requested_by"],)
    )

    data["requested_by"] = cur.fetchone()[0]
    cur.close()

    values = [data[f] for f in fields]
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO attendance_application (title, department, requested_at, requested_by, request_type, reason, start_day, end_day, start_time, end_time) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"
        ,values
    )
    cur.close()
    conn.close()
    return redirect(url_for("workflow"))


@app.get("/workflow/flow2")
def flow2():
    return render_template("flow2.html")


@app.get("/workflow/flow3")
def flow3():
    return render_template("flow3.html")


@app.get("/info")
def info():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, updated_day, information FROM info ORDER BY updated_day DESC, id DESC LIMIT 20"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("info.html", rows=rows)


@app.post("/info/add")
def info_add():
    info_val = request.form.get("information", "").strip()
#    if not info_val.isdigit():
#        flash("information は整数で入力してください。")
#        return redirect(url_for("info_manage"))

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO info (information) VALUES (?)",
        (
            info_val,
        )
    )
    cur.close()
    conn.close()
    flash("追加しました。")
    return redirect(url_for("info"))


@app.post("/info/delete/<int:id>")
def info_delete(id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM info WHERE id = ?",
        (id,)
    )
    cur.close()
    conn.close()
    flash(f"id={id} を削除しました。")
    return redirect(url_for("info"))


@app.get("/order")
def order():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT code, id FROM production_order ORDER BY code DESC LIMIT 30;"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("order.html", rows=rows)


@app.get("/order/<int:id>")
def order_detail(id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT code FROM production_order WHERE id = ?;",
        (id,)
    )
    code = cur.fetchone()[0]
    cur.close()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT * FROM production_order_detail WHERE order_id = ? ORDER BY code;",
        (id,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("order_detail.html", rows=rows, code=code)


@app.get("/depart")
def depart():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name FROM depart WHERE is_active = 1 ORDER BY id;"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("depart.html", rows=rows)


@app.post("/depart/add")
def depart_add():
    name = request.form.get("name")
    #    if not info_val.isdigit():
    #        flash("information は整数で入力してください。")
    #        return redirect(url_for("info_manage"))


    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO depart (name) VALUES (?)",
            (
                name,
            )
        )

    except mariadb.IntegrityError:
        flash("既に存在する部署名です。")

    cur.close()
    conn.close()

    flash("追加しました。")
    return redirect(url_for("depart"))


@app.post("/depart/delete/<int:id>")
def depart_delete(id:int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE depart SET is_active = 0 WHERE id = ?;",
        (id,)
    )
    cur.close()
    conn.close()
    return redirect(url_for("depart"))


@app.get("/employee")
def employee():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, code, CONCAT(family_name, first_name) AS name FROM employee "
        "WHERE account != ? "
        "ORDER BY id;",
        ("admin",)
    )

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("employee.html", rows=rows)


@app.post("/employee/password/<int:id>")
def set_employee_password(id: int):

    password = generate_pass(request.form.get("password"))
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "UPDATE employee SET need_change_pass = 1, password_hash = ? WHERE id = ?;",
        (password, id)
    )

    cur.close()
    conn.close()
    flash("パスワードを設定しました")
    return redirect(url_for("employee"))


@app.get("/route")
def route():
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT route.id, title, CONCAT(family_name, ' ', first_name) creator FROM route "
        "LEFT JOIN employee ON creator = employee.id "
        "WHERE status = 0 ORDER BY id;"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("route.html", rows=rows,)


@app.get("/route/editor")
@app.get("/route/editor/<int:id>")
def route_edit(id: int = None):
    rows1 = []
    rows2 = []

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, CONCAT(family_name, ' ', first_name) AS name FROM employee "
        "WHERE retire = 0 AND account != ?;",
        ("admin",)
    )

    employees = cur.fetchall()
    cur.close()

    if id is None:
        rows2.append([])

    else:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id, title FROM route "
            "WHERE is_master = 1 AND status = 0 AND id = ?;",
            (id,)
        )
        rows1 = cur.fetchone()

        cur.execute(
            "SELECT id, rule, ordered + 1 as ordered FROM route_block "
            "WHERE r_id = ? ORDER BY ordered;",
            (rows1["id"], )
        )
        rows = cur.rowcount
        b_id = []
        for i in range(rows):
            record = cur.fetchone()
            rows2.append(record)
            b_id.append(record["id"])

        for i, n in enumerate(b_id):
            cur.execute(
                "SELECT CONVERT(e_id, CHAR) AS id, CONCAT(family_name, ' ', first_name) AS label "
                "FROM route_member "
                "LEFT JOIN employee ON route_member.e_id = employee.id "
                "WHERE b_id = ?;",
                (n,)
            )
            records = cur.fetchall()
            rows2[i]["members"] = records
            rows2[i]["value"] = records

        cur.close()

    conn.close()
    return render_template(
        "route_editor.html",
        employees=employees,
        rows1=rows1,
        rows2=rows2,
    )


@app.post("/route/editor/submit")
def route_editor_save():

    rules = request.form.getlist("rule[]")
    members = request.form.getlist("members[]")

    conn = get_conn()
    conn.begin()
    cur = conn.cursor()

    result = True

    try:
        r_id = request.form.get("r_id")
        title = request.form.get("title")
        if not r_id:
            cur.execute(
                "INSERT INTO route (title, creator) VALUES (?, ?);",
                (title, session["id"])
            )
            r_id = cur.lastrowid

        else:
            # 与えられたidが存在するか確認
            cur.execute(
                "SELECT 1 FROM route WHERE id = ?;",
                (r_id,)
            )

            if cur.fetchone()[0] == 1:  # idが実在する場合は更新し、子データは削除
                cur.execute(
                    "UPDATE route SET title = ?, creator = ? WHERE id = ?;",
                    (title, session["id"], r_id)
                )
                cur.execute(
                    "DELETE FROM route_block WHERE r_id = ?;",
                    (r_id,)
                )

            else:  # idが実在しない場合は終了
                result = False

        if result:
            length = len(rules)

            for i in range(length):

                cur.execute(
                    "INSERT INTO route_block (r_id, rule, ordered) VALUES (?, ?, ?);",
                    (r_id, rules[i], i)
                )
                b_id = cur.lastrowid

                mem = json.loads(members[i]) if members[i] else[]
                values = []
                # ブラウザで表示されている従業員名、idと、
                # employeeテーブルのidに対応する従業員名が一致するか確認
                for item in mem:
                    cur.execute(
                        "SELECT CONCAT(family_name, ' ', first_name) AS name FROM employee WHERE id = ?;",
                        (item["id"],)
                    )
                    name = cur.fetchone()[0]
                    if name != item["label"]:
                        result = False
                        break
                    values.append([item["id"], b_id])

                if not result:
                    break

                if values:
                    cur.executemany(
                        "INSERT INTO route_member (e_id, b_id) VALUES (?, ?);",
                        values
                    )

    except mariadb.IntegrityError:
        result = False

    except Exception as e:
        print(e)
        result = False

    cur.close()
    if result:
        conn.commit()
    else:
        conn.rollback()

    conn.close()
    if not result:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, CONCAT(family_name, ' ', first_name) AS name FROM employee "
            "WHERE retire = 0 AND account != ?;",
            ("admin",)
        )
        employees = cur.fetchall()
        cur.close()
        conn.close()

        rows1 = {r: request.form.get(r) for r in ["r_id", "title"]}

        rules = request.form.getlist("rule[]")

        members = request.form.getlist("members[]")

        rows2 = []
        for i, rule in enumerate(rules):
            rows2.append({
                "rule": rule,
                "members": json.loads(members[i]) if members[i] else[],
                "ordered": i + 1,
                "value": json.loads(members[i]) if members[i] else[],
            })

        return render_template("route_editor.html",
            #"route_editor.html",
            employees=employees,
            rows1=rows1,
            rows2=rows2
        )

    return redirect(url_for("route"))


@app.post("/route/editor/delete/<int:id>")
def route_delete(id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM route WHERE id = ?;",
        (id,)
    )
    cur.close()
    conn.close()
    return redirect(url_for("route"))


@app.get("/test")
def test():
    return render_template("table_test.html")


@app.get("/test2")
def test2():
    return render_template("table_test2.html")


@app.get("/test3")
def test3():
    return render_template("table_test3.html")


if __name__ == "__main__":
    create_admin()
    # Dockerで外から見えるように 0.0.0.0
    app.run(host="0.0.0.0", port=5000, debug=True)
