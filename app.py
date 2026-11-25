import os,secrets,hmac
from flask import Flask,request,session,redirect,render_template_string,abort
import psycopg
from werkzeug.security import check_password_hash
app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_SECURE=True,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax")
def db():
 c=psycopg.connect(os.environ["DATABASE_URL"])
 with c.transaction():
  c.execute("SELECT pg_advisory_xact_lock(872314)")
  c.execute(open(os.path.join(os.path.dirname(__file__),"schema.sql")).read())
  c.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS seller_phone text")
 c.commit()
 return c
def page(body,**kw):
 return render_template_string("""<!doctype html><html lang="uz"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AVENTO AVTO PRO</title><style>body{font:16px system-ui;background:#f1f4f8;color:#14243b;margin:0}header{background:#14243b;color:white;padding:20px}main{max-width:850px;margin:auto;padding:20px}input,select,button{box-sizing:border-box;width:100%;padding:12px;margin:5px 0;border:1px solid #bbb;border-radius:8px}button{background:#14243b;color:white}section{background:white;padding:20px;margin:16px 0;border-radius:16px;box-shadow:0 4px 20px #14243b0d}.stats{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.stat{background:white;padding:18px;border-radius:14px}.stat strong{display:block;font-size:28px}nav{display:flex;flex-wrap:wrap;gap:12px;padding:16px 0}nav a{background:#14243b;color:white;padding:10px;border-radius:8px;text-decoration:none}a{color:#24538a}</style><header>AVENTO AVTO PRO 2.0</header><main>"""+body+"</main></html>",**kw)
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
  if request.form.get('email')==os.environ.get('ADMIN_EMAIL') and (check_password_hash(os.environ['ADMIN_PASSWORD_HASH'],request.form.get('password','')) if os.environ.get('ADMIN_PASSWORD_HASH') else bool(os.environ.get('ADMIN_PASSWORD')) and hmac.compare_digest(os.environ['ADMIN_PASSWORD'].encode(),request.form.get('password','').encode())):
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
    c.execute("INSERT INTO contracts(vehicle_id,customer_id,total,seller_phone) VALUES(%s,%s,%s,%s)",(f['vehicle'],f['customer'],v[0],f['seller_phone']))
    c.execute("UPDATE vehicles SET status='sold' WHERE id=%s",(f['vehicle'],))
   return redirect('/')
  vehicles=c.execute("SELECT id,model,vin,price,status FROM vehicles ORDER BY id DESC").fetchall()
  customers=c.execute("SELECT id,full_name FROM customers ORDER BY id DESC").fetchall()
  contracts=c.execute("SELECT id,total,vat,created_at FROM contracts ORDER BY id DESC").fetchall()
 return page("""<h1>Boshqaruv paneli</h1><div class="stats"><div class="stat"><strong>{{vehicles|selectattr("4","equalto","available")|list|length}}</strong>Ombordagi avtomobillar</div><div class="stat"><strong>{{contracts|length}}</strong>Shartnomalar</div><div class="stat"><strong>{{customers|length}}</strong>Xaridorlar</div><div class="stat"><strong>{{vehicles|selectattr("4","equalto","sold")|list|length}}</strong>Sotilgan avtomobillar</div></div><nav><a href="#sale">Yangi shartnoma</a><a href="#stock">Ombor</a><a href="#buyers">Xaridorlar</a><a href="#archive">Arxiv</a></nav><section id="stock"><h2>Avtomobillar ombori</h2><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="action" value="vehicle"><input name="model" placeholder="Model" required><input name="vin" placeholder="VIN" required><input name="color" placeholder="Rang"><input name="price" type="number" min="0" step="0.01" required placeholder="Umumiy narx (QQS bilan)" oninput="let t=Number(this.value)||0,n=Math.round(t/1.12*100)/100;document.getElementById('vatpreview').textContent='QQSsiz: '+n.toLocaleString()+' so‘m | QQS: '+(t-n).toLocaleString()+' so‘m'"><p id="vatpreview"></p><button>Avtomobil qo‘shish</button></form>{% for v in vehicles %}<p>{{v[1]}} · {{v[2]}} · {{v[3]}} · {{v[4]}}</p>{% endfor %}</section><section id="buyers"><h2>Xaridorlar</h2><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="action" value="customer"><input name="name" required placeholder="F.I.Sh."><input name="passport" placeholder="Pasport"><input name="jshshir" pattern="[0-9]{14}" placeholder="JSHSHIR"><input name="phone" type="tel" required placeholder="Xaridor telefoni"><button>Saqlash</button></form></section><section id="sale"><h2>Shartnoma</h2><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="action" value="sale"><select name="vehicle" required>{% for v in vehicles if v[4]=='available' %}<option value="{{v[0]}}">{{v[1]}} {{v[2]}}</option>{% endfor %}</select><select name="customer" required>{% for c in customers %}<option value="{{c[0]}}">{{c[1]}}</option>{% endfor %}</select><input name="seller_phone" type="tel" required value="+998 94 926 00 34" placeholder="Sotuvchi telefoni"><button>Sotuvni tasdiqlash</button></form></section><section id="archive"><h2>Arxiv</h2>{% for c in contracts %}<p>№{{c[0]}} · {{c[1]}} UZS · QQS {{c[2]}} · <a href="/contract/{{c[0]}}/xlsx">Excel</a> · <a href="/contract/{{c[0]}}/print">Chop etish / PDF</a></p>{% endfor %}</section>""",csrf=session['csrf'],vehicles=vehicles,customers=customers,contracts=contracts)

@app.get('/contract/<int:id>/<fmt>')
def export_contract(id,fmt):
 from io import BytesIO
 from flask import send_file
 from openpyxl import Workbook
 with db() as conn:
  r=conn.execute("SELECT c.id,c.created_at,v.model,v.vin,v.color,b.full_name,b.passport,b.jshshir,b.phone,c.seller_phone,c.net,c.vat,c.total FROM contracts c JOIN vehicles v ON v.id=c.vehicle_id JOIN customers b ON b.id=c.customer_id WHERE c.id=%s",(id,)).fetchone()
 if not r: abort(404)
 labels=['Raqam','Sana','Model','VIN','Rang','Xaridor','Pasport','JSHSHIR','Xaridor telefoni','Sotuvchi telefoni','QQSsiz narx','QQS','Jami']
 rows=list(zip(labels,[str(x) if x is not None else '' for x in r]))
 if fmt=='xlsx':
  w=Workbook();s=w.active;s.title='Sotuv ma’lumotlari';s.append(['AVENTO AVTO — sotuv ma’lumotlari']);s.append(['Shartnoma emas'])
  for k,v in rows:
   s.append([k,v]);s.cell(s.max_row,2).data_type='s'
  s.column_dimensions['A'].width=25;s.column_dimensions['B'].width=45
  out=BytesIO();w.save(out);out.seek(0)
  return send_file(out,as_attachment=True,download_name=f'avento-{id}.xlsx')
 if fmt=='print':
  return page('<h2>Sotuv ma’lumotlari №{{id}}</h2><p>Shartnoma emas</p>{% for k,v in rows %}<p><b>{{k}}</b>: {{v}}</p>{% endfor %}<button onclick="window.print()">Chop etish / PDF saqlash</button>',id=id,rows=rows)
 abort(404)
