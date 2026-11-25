import os,secrets,hmac
from flask import Flask,request,session,redirect,render_template_string,abort
import psycopg
from werkzeug.security import check_password_hash
app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_SECURE=True,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax")
def db(): return psycopg.connect(os.environ["DATABASE_URL"])
def page(body,**kw):
 return render_template_string("""<!doctype html><html lang="uz"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AVENTO AVTO PRO</title><style>body{font:16px system-ui;background:#f1f4f8;color:#14243b;margin:0}header{background:#14243b;color:white;padding:20px}main{max-width:850px;margin:auto;padding:20px}input,select,button{box-sizing:border-box;width:100%;padding:12px;margin:5px 0;border:1px solid #bbb;border-radius:8px}button{background:#14243b;color:white}section{background:white;padding:16px;margin:12px 0;border-radius:12px}a{color:#24538a}</style><header>AVENTO AVTO PRO</header><main>"""+body+"</main></html>",**kw)
@app.before_request
def protect():
 if request.endpoint in ('login','health'): return
 if not session.get('admin'): return redirect('/login')
 if request.method=='POST' and not hmac.compare_digest(request.form.get('csrf',''),session.get('csrf','!')): abort(403)
@app.get('/health')
def health(): return 'OK'
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  if request.form.get('email')==os.environ.get('ADMIN_EMAIL') and check_password_hash(os.environ.get('ADMIN_PASSWORD_HASH',''),request.form.get('password','')):
   session.clear();session['admin']=True;session['csrf']=secrets.token_hex(32);return redirect('/')
  return 'Login yoki parol noto‘g‘ri',401
 return page('<section><h2>Kirish</h2><form method="post"><input name="email" type="email" required placeholder="Email"><input name="password" type="password" required placeholder="Parol"><button>Kirish</button></form></section>')
@app.route('/',methods=['GET','POST'])
def home():
 with db() as c:
  if request.method=='POST':
   f=request.form
   if f['action']=='vehicle': c.execute("INSERT INTO vehicles(vin,model,color,price) VALUES(%s,%s,%s,%s)",(f['vin'],f['model'],f['color'],f['price']))
   elif f['action']=='customer': c.execute("INSERT INTO customers(full_name,passport,jshshir,phone) VALUES(%s,%s,%s,%s)",(f['name'],f['passport'],f['jshshir'] or None,f['phone']))
   elif f['action']=='sale':
    v=c.execute("SELECT price FROM vehicles WHERE id=%s AND status='available' FOR UPDATE",(f['vehicle'],)).fetchone()
    if not v: abort(409)
    c.execute("INSERT INTO contracts(vehicle_id,customer_id,total) VALUES(%s,%s,%s)",(f['vehicle'],f['customer'],v[0]))
    c.execute("UPDATE vehicles SET status='sold' WHERE id=%s",(f['vehicle'],))
   return redirect('/')
  vehicles=c.execute("SELECT id,model,vin,price,status FROM vehicles ORDER BY id DESC").fetchall()
  customers=c.execute("SELECT id,full_name FROM customers ORDER BY id DESC").fetchall()
  contracts=c.execute("SELECT id,total,vat,created_at FROM contracts ORDER BY id DESC").fetchall()
 return page("""<section><h2>Avtomobillar ombori</h2><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="action" value="vehicle"><input name="model" placeholder="Model" required><input name="vin" placeholder="VIN" required><input name="color" placeholder="Rang"><input name="price" type="number" min="0" required placeholder="Narx (UZS)"><button>Avtomobil qo‘shish</button></form>{% for v in vehicles %}<p>{{v[1]}} · {{v[2]}} · {{v[3]}} · {{v[4]}}</p>{% endfor %}</section><section><h2>Xaridorlar</h2><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="action" value="customer"><input name="name" required placeholder="F.I.Sh."><input name="passport" placeholder="Pasport"><input name="jshshir" pattern="[0-9]{14}" placeholder="JSHSHIR"><input name="phone" placeholder="Telefon"><button>Saqlash</button></form></section><section><h2>Shartnoma</h2><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="action" value="sale"><select name="vehicle" required>{% for v in vehicles if v[4]=='available' %}<option value="{{v[0]}}">{{v[1]}} {{v[2]}}</option>{% endfor %}</select><select name="customer" required>{% for c in customers %}<option value="{{c[0]}}">{{c[1]}}</option>{% endfor %}</select><button>Sotuvni tasdiqlash</button></form></section><section><h2>Arxiv</h2>{% for c in contracts %}<p>№{{c[0]}} · {{c[1]}} UZS · QQS {{c[2]}}</p>{% endfor %}</section>""",csrf=session['csrf'],vehicles=vehicles,customers=customers,contracts=contracts)
