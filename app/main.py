from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import csv, io, os, secrets, json, zipfile, tempfile
from uuid import uuid4

from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from .database import Base, engine, get_db, DB_PATH, IS_SQLITE
from .models import *
from .security import hash_password, verify_password, csrf_token, check_csrf
from .seed import seed_catalog

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="ZAFIRAH Gestión")
def _session_secret():
    env=os.environ.get("ZAFIRAH_SECRET")
    if env: return env
    secret_file=BASE_DIR.parent / "data" / ".session_secret"
    secret_file.parent.mkdir(exist_ok=True)
    if secret_file.exists(): return secret_file.read_text().strip()
    value=secrets.token_urlsafe(48); secret_file.write_text(value); return value
app.add_middleware(SessionMiddleware, secret_key=_session_secret(), same_site="lax", https_only=os.environ.get("COOKIE_SECURE", "0").lower() in {"1","true","yes","on"})
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
Base.metadata.create_all(bind=engine)

# ---------- Helpers ----------
def D(value, default="0") -> Decimal:
    try: return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError): return Decimal(default)

def money(v):
    try: return f"${float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$0,00"

def num(v):
    try:
        s = f"{float(v):,.3f}".rstrip("0").rstrip(".")
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "0"

templates.env.filters["money"] = money
templates.env.filters["num"] = num

def current_user(request: Request, db: Session):
    uid = request.session.get("user_id")
    return db.get(User, uid) if uid else None

def render(request, db, name, **ctx):
    ctx.update({"request": request, "user": current_user(request, db), "csrf": csrf_token(request.session), "today": date.today()})
    return templates.TemplateResponse(name, ctx)

def require_user(request: Request, db: Session):
    u = current_user(request, db)
    if not u:
        raise HTTPException(status_code=401)
    return u

def guard(request: Request, db: Session):
    if not current_user(request, db):
        return RedirectResponse("/login", 303)
    return None

def csrf_guard(request: Request, form):
    if not check_csrf(request.session, form.get("csrf_token")):
        raise HTTPException(400, "Token CSRF inválido")

def flash(request, msg, kind="ok"):
    request.session["flash"] = {"msg": msg, "kind": kind}

def pop_flash(request):
    return request.session.pop("flash", None)

def add_movement(db, entity_type, obj, delta, reason, source_type=None, source_id=None):
    obj.stock = D(obj.stock) + D(delta)
    db.add(InventoryMovement(entity_type=entity_type, entity_id=obj.id, entity_name=obj.name,
                             qty_delta=D(delta), balance_after=D(obj.stock), reason=reason,
                             source_type=source_type, source_id=source_id))

def parse_date(s, default=None):
    try: return datetime.strptime(s, "%Y-%m-%d").date()
    except: return default or date.today()

def get_or_create_material(db: Session, raw_name: str):
    """Resolve an insumo by name; create it automatically when it does not exist."""
    name = " ".join(str(raw_name or "").strip().split())
    if not name:
        return None
    material = (db.query(Material)
                .filter(func.lower(Material.name) == name.lower())
                .first())
    if material:
        if not material.active:
            material.active = True
        return material
    material = Material(
        sku=f"AUTO-{uuid4().hex[:10].upper()}",
        name=name,
        unit="unidad",
        avg_cost=D0,
        stock=D0,
        min_stock=D0,
        active=True,
    )
    db.add(material)
    db.flush()
    return material

def get_or_create_product(db: Session, raw_name: str):
    """Resolve a producto by name; create it automatically when it does not exist."""
    name = " ".join(str(raw_name or "").strip().split())
    if not name:
        return None
    product = (db.query(Product)
               .filter(func.lower(Product.name) == name.lower())
               .first())
    if product:
        if not product.active:
            product.active = True
        return product
    product = Product(
        sku=f"AUTO-P-{uuid4().hex[:10].upper()}",
        name=name,
        category="Otros",
        sale_price=D0,
        cost=D0,
        stock=D0,
        min_stock=D0,
        active=True,
    )
    db.add(product)
    db.flush()
    return product


@app.exception_handler(401)
async def unauthorized(request: Request, exc):
    return RedirectResponse("/login", 303)

@app.middleware("http")
async def add_flash(request: Request, call_next):
    response = await call_next(request)
    return response

# ---------- Auth ----------
@app.get("/setup", response_class=HTMLResponse)
def setup_get(request: Request, db: Session = Depends(get_db)):
    if db.query(User).count(): return RedirectResponse("/login", 303)
    return render(request, db, "setup.html")

@app.post("/setup")
async def setup_post(request: Request, db: Session = Depends(get_db)):
    if db.query(User).count(): return RedirectResponse("/login", 303)
    form = await request.form(); csrf_guard(request, form)
    username = str(form.get("username", "admin")).strip()
    password = str(form.get("password", ""))
    if len(password) < 8:
        return render(request, db, "setup.html", error="La contraseña debe tener al menos 8 caracteres.")
    u = User(username=username, password_hash=hash_password(password)); db.add(u); db.commit(); db.refresh(u)
    if form.get("seed_catalog"): seed_catalog(db)
    request.session["user_id"] = u.id
    flash(request, "ZAFIRAH Gestión quedó configurado.")
    return RedirectResponse("/", 303)

@app.get("/login", response_class=HTMLResponse)
def login_get(request: Request, db: Session = Depends(get_db)):
    if not db.query(User).count(): return RedirectResponse("/setup", 303)
    return render(request, db, "login.html")

@app.post("/login")
async def login_post(request: Request, db: Session = Depends(get_db)):
    form=await request.form(); csrf_guard(request, form)
    u=db.query(User).filter(User.username==str(form.get("username","")).strip()).first()
    if not u or not verify_password(str(form.get("password","")), u.password_hash):
        return render(request, db, "login.html", error="Usuario o contraseña incorrectos.")
    request.session["user_id"]=u.id; flash(request,"Sesión iniciada."); return RedirectResponse("/",303)

@app.post("/logout")
async def logout(request: Request):
    form=await request.form(); csrf_guard(request, form); request.session.clear(); return RedirectResponse("/login",303)

# ---------- Dashboard ----------
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    start=date.today().replace(day=1)
    sales=db.query(Sale).filter(Sale.status=="active", Sale.date>=start).all()
    revenue=sum((D(s.total) for s in sales),D0); gross=sum((D(s.profit) for s in sales),D0)
    expenses=sum((D(x.amount) for x in db.query(Expense).filter(Expense.status=="active", Expense.date>=start).all()),D0)
    low_products=db.query(Product).filter(Product.active==True, Product.stock<=Product.min_stock).order_by(Product.stock).limit(8).all()
    low_materials=db.query(Material).filter(Material.active==True, Material.stock<=Material.min_stock).order_by(Material.stock).limit(8).all()
    recent=db.query(Sale).order_by(Sale.id.desc()).limit(8).all()
    return render(request,db,"dashboard.html", revenue=revenue, gross=gross, expenses=expenses, net=gross-expenses,
                  low_products=low_products, low_materials=low_materials, recent=recent, flash=pop_flash(request))

# ---------- Generic master data ----------
@app.get("/products", response_class=HTMLResponse)
def products(request:Request, db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    items=db.query(Product).order_by(Product.category,Product.name).all()
    return render(request,db,"products.html",items=items,flash=pop_flash(request))

@app.get("/products/new", response_class=HTMLResponse)
def product_new(request:Request, db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    return render(request,db,"product_form.html",item=None)

@app.get("/products/{item_id}/edit", response_class=HTMLResponse)
def product_edit(item_id:int, request:Request, db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    return render(request,db,"product_form.html",item=db.get(Product,item_id))

@app.post("/products/save")
async def product_save(request:Request, db:Session=Depends(get_db)):
    require_user(request,db); f=await request.form(); csrf_guard(request,f)
    item=db.get(Product,int(f.get("id"))) if f.get("id") else Product()
    old_stock=D(item.stock or 0)
    item.sku=str(f.get("sku","")).strip(); item.name=str(f.get("name","")).strip(); item.category=str(f.get("category","Otros")).strip()
    item.sale_price=D(f.get("sale_price")); item.cost=D(f.get("cost")); item.min_stock=D(f.get("min_stock")); item.active=bool(f.get("active"))
    if not item.id: db.add(item); db.flush()
    new_stock=D(f.get("stock")); delta=new_stock-old_stock
    if delta: add_movement(db,"product",item,delta,"Ajuste manual")
    db.commit(); flash(request,"Producto guardado."); return RedirectResponse("/products",303)

@app.get("/materials", response_class=HTMLResponse)
def materials(request:Request, db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    return render(request,db,"materials.html",items=db.query(Material).order_by(Material.name).all(),flash=pop_flash(request))

@app.get("/materials/new", response_class=HTMLResponse)
def material_new(request:Request, db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    return render(request,db,"material_form.html",item=None)

@app.get("/materials/{item_id}/edit", response_class=HTMLResponse)
def material_edit(item_id:int,request:Request,db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    return render(request,db,"material_form.html",item=db.get(Material,item_id))

@app.post("/materials/save")
async def material_save(request:Request,db:Session=Depends(get_db)):
    require_user(request,db); f=await request.form(); csrf_guard(request,f)
    item=db.get(Material,int(f.get("id"))) if f.get("id") else Material()
    old_stock=D(item.stock or 0)
    item.sku=str(f.get("sku","")).strip(); item.name=str(f.get("name","")).strip(); item.unit=str(f.get("unit","unidad")).strip()
    item.avg_cost=D(f.get("avg_cost")); item.min_stock=D(f.get("min_stock")); item.active=bool(f.get("active"))
    if not item.id: db.add(item); db.flush()
    new_stock=D(f.get("stock")); delta=new_stock-old_stock
    if delta: add_movement(db,"material",item,delta,"Ajuste manual")
    db.commit(); flash(request,"Insumo guardado."); return RedirectResponse("/materials",303)

# ---------- Recipes ----------
@app.get("/recipes", response_class=HTMLResponse)
def recipes(request:Request,db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    rs=db.query(Recipe).options(joinedload(Recipe.product),joinedload(Recipe.items).joinedload(RecipeItem.material)).all()
    return render(request,db,"recipes.html",items=rs,flash=pop_flash(request))

@app.get("/recipes/new", response_class=HTMLResponse)
def recipe_new(request:Request,db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    return render(request,db,"recipe_form.html",recipe=None,products=db.query(Product).filter(Product.active==True).order_by(Product.name).all(),materials=db.query(Material).filter(Material.active==True).order_by(Material.name).all())

@app.get("/recipes/{rid}/edit", response_class=HTMLResponse)
def recipe_edit(rid:int,request:Request,db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    rec=db.query(Recipe).options(joinedload(Recipe.items)).filter(Recipe.id==rid).first()
    return render(request,db,"recipe_form.html",recipe=rec,products=db.query(Product).filter(Product.active==True).order_by(Product.name).all(),materials=db.query(Material).filter(Material.active==True).order_by(Material.name).all())

@app.post("/recipes/save")
async def recipe_save(request:Request,db:Session=Depends(get_db)):
    require_user(request,db); f=await request.form(); csrf_guard(request,f)
    rid=f.get("id")
    product=None
    product_name=str(f.get("product_name","")).strip()
    if product_name:
        product=get_or_create_product(db,product_name)
    elif f.get("product_id"):
        product=db.get(Product,int(f.get("product_id")))
    if not product:
        flash(request,"Indicá un producto para la receta.","error")
        return RedirectResponse("/recipes/new",303)
    rec=db.get(Recipe,int(rid)) if rid else db.query(Recipe).filter(Recipe.product_id==product.id).first()
    if not rec: rec=Recipe(product_id=product.id); db.add(rec)
    rec.product_id=product.id; rec.yield_qty=max(D(f.get("yield_qty"),"1"),Decimal("0.001")); rec.notes=str(f.get("notes","")).strip() or None
    rec.items.clear()
    names=f.getlist("material_name"); qtys=f.getlist("qty")
    # Compatibilidad con formularios viejos que todavía envíen material_id.
    if not names:
        mids=f.getlist("material_id")
        names=[db.get(Material,int(mid)).name if mid and db.get(Material,int(mid)) else "" for mid in mids]
    for name,q in zip(names,qtys):
        qty=D(q)
        material=get_or_create_material(db,name)
        if material and qty>0:
            rec.items.append(RecipeItem(material_id=material.id,qty=qty))
    db.commit(); flash(request,"Receta guardada."); return RedirectResponse("/recipes",303)

# ---------- Contacts ----------
def contacts_page(model, template, request, db):
    if (r:=guard(request,db)): return r
    return render(request,db,template,items=db.query(model).order_by(model.name).all(),flash=pop_flash(request))

@app.get("/suppliers",response_class=HTMLResponse)
def suppliers(request:Request,db:Session=Depends(get_db)): return contacts_page(Supplier,"contacts.html",request,db)
@app.get("/customers",response_class=HTMLResponse)
def customers(request:Request,db:Session=Depends(get_db)): return contacts_page(Customer,"contacts.html",request,db)

@app.post("/contacts/save")
async def contact_save(request:Request,db:Session=Depends(get_db)):
    require_user(request,db); f=await request.form(); csrf_guard(request,f)
    kind=str(f.get("kind")); model=Supplier if kind=="supplier" else Customer
    obj=db.get(model,int(f.get("id"))) if f.get("id") else model()
    obj.name=str(f.get("name","")).strip(); obj.phone=str(f.get("phone","")).strip() or None; obj.email=str(f.get("email","")).strip() or None; obj.notes=str(f.get("notes","")).strip() or None
    db.add(obj); db.commit(); flash(request,"Registro guardado."); return RedirectResponse("/suppliers" if kind=="supplier" else "/customers",303)

# ---------- Purchases ----------
@app.get("/purchases",response_class=HTMLResponse)
def purchases(request:Request,db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    items=db.query(Purchase).options(joinedload(Purchase.supplier),joinedload(Purchase.items).joinedload(PurchaseItem.material)).order_by(Purchase.id.desc()).limit(300).all()
    return render(request,db,"purchases.html",items=items,flash=pop_flash(request))

@app.get("/purchases/new",response_class=HTMLResponse)
def purchase_new(request:Request,db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    return render(request,db,"purchase_form.html",suppliers=db.query(Supplier).order_by(Supplier.name).all(),materials=db.query(Material).filter(Material.active==True).order_by(Material.name).all())

def recalc_material_cost(db, material_id):
    rows=(db.query(PurchaseItem).join(Purchase).filter(PurchaseItem.material_id==material_id,Purchase.status=="active").all())
    q=sum((D(r.qty) for r in rows),D0); total=sum((D(r.qty)*D(r.unit_cost) for r in rows),D0)
    m=db.get(Material,material_id)
    if q>0: m.avg_cost=total/q

@app.post("/purchases/save")
async def purchase_save(request:Request,db:Session=Depends(get_db)):
    require_user(request,db); f=await request.form(); csrf_guard(request,f)
    p=Purchase(supplier_id=int(f.get("supplier_id")) if f.get("supplier_id") else None,date=parse_date(str(f.get("date"))),notes=str(f.get("notes","")).strip() or None)
    db.add(p); db.flush(); total=D0; affected=[]
    names=f.getlist("material_name")
    qtys=f.getlist("qty"); costs=f.getlist("unit_cost")
    # Compatibilidad con formularios viejos que todavía envíen material_id.
    if not names:
        mids=f.getlist("material_id")
        names=[db.get(Material,int(mid)).name if mid and db.get(Material,int(mid)) else "" for mid in mids]
    for name,q,c in zip(names,qtys,costs):
        qty=D(q); cost=D(c)
        m=get_or_create_material(db,name)
        if not m or qty<=0: continue
        sub=qty*cost; total+=sub; affected.append(m.id)
        db.add(PurchaseItem(purchase_id=p.id,material_id=m.id,qty=qty,unit_cost=cost,subtotal=sub))
        add_movement(db,"material",m,qty,f"Compra #{p.id}","purchase",p.id)
    p.total=total
    db.flush()
    for mid in set(affected): recalc_material_cost(db,mid)
    db.commit(); flash(request,"Compra registrada y stock actualizado."); return RedirectResponse("/purchases",303)

@app.post("/purchases/{pid}/void")
async def purchase_void(pid:int,request:Request,db:Session=Depends(get_db)):
    require_user(request,db); f=await request.form(); csrf_guard(request,f)
    p=db.query(Purchase).options(joinedload(Purchase.items).joinedload(PurchaseItem.material)).get(pid)
    if p and p.status=="active":
        for it in p.items: add_movement(db,"material",it.material,-D(it.qty),f"Anulación compra #{p.id}","purchase_void",p.id)
        p.status="void"; db.flush()
        for it in p.items: recalc_material_cost(db,it.material_id)
        db.commit(); flash(request,"Compra anulada; el stock fue revertido.")
    return RedirectResponse("/purchases",303)

# ---------- Sales ----------
@app.get("/sales",response_class=HTMLResponse)
def sales(request:Request,db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    items=db.query(Sale).options(joinedload(Sale.customer),joinedload(Sale.items).joinedload(SaleItem.product)).order_by(Sale.id.desc()).limit(300).all()
    return render(request,db,"sales.html",items=items,flash=pop_flash(request))

@app.get("/sales/new",response_class=HTMLResponse)
def sale_new(request:Request,db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    return render(request,db,"sale_form.html",customers=db.query(Customer).order_by(Customer.name).all(),products=db.query(Product).filter(Product.active==True).order_by(Product.name).all())

@app.post("/sales/save")
async def sale_save(request:Request,db:Session=Depends(get_db)):
    require_user(request,db); f=await request.form(); csrf_guard(request,f)
    s=Sale(customer_id=int(f.get("customer_id")) if f.get("customer_id") else None,date=parse_date(str(f.get("date"))),payment_method=str(f.get("payment_method","Efectivo")),channel=str(f.get("channel","Directa")),notes=str(f.get("notes","")).strip() or None)
    db.add(s); db.flush(); total=D0; cogs=D0
    parsed=[]
    names=f.getlist("product_name")
    pids=f.getlist("product_id")
    qtys=f.getlist("qty"); prices=f.getlist("unit_price")
    count=max(len(names),len(pids),len(qtys),len(prices))
    for i in range(count):
        name=names[i] if i < len(names) else ""
        pid=pids[i] if i < len(pids) else ""
        q=qtys[i] if i < len(qtys) else ""
        price=prices[i] if i < len(prices) else ""
        qty=D(q)
        if qty<=0: continue
        p=get_or_create_product(db,name) if str(name).strip() else (db.get(Product,int(pid)) if pid else None)
        if not p: continue
        up=D(price) if D(price)>0 else D(p.sale_price)
        if D(p.stock)<qty:
            db.rollback(); flash(request,f"Stock insuficiente de {p.name}.","error"); return RedirectResponse("/sales/new",303)
        parsed.append((p,qty,up))
    for p,qty,up in parsed:
        sub=qty*up; cost=qty*D(p.cost); total+=sub; cogs+=cost
        db.add(SaleItem(sale_id=s.id,product_id=p.id,qty=qty,unit_price=up,unit_cost=D(p.cost),subtotal=sub))
        add_movement(db,"product",p,-qty,f"Venta #{s.id}","sale",s.id)
    s.total=total; s.cogs=cogs; s.profit=total-cogs
    db.commit(); flash(request,"Venta registrada; stock y ganancia actualizados."); return RedirectResponse("/sales",303)

@app.post("/sales/{sid}/void")
async def sale_void(sid:int,request:Request,db:Session=Depends(get_db)):
    require_user(request,db); f=await request.form(); csrf_guard(request,f)
    s=db.query(Sale).options(joinedload(Sale.items).joinedload(SaleItem.product)).get(sid)
    if s and s.status=="active":
        for it in s.items: add_movement(db,"product",it.product,D(it.qty),f"Anulación venta #{s.id}","sale_void",s.id)
        s.status="void"; db.commit(); flash(request,"Venta anulada; el stock fue repuesto.")
    return RedirectResponse("/sales",303)

# ---------- Production ----------
@app.get("/production",response_class=HTMLResponse)
def production(request:Request,db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    items=db.query(ProductionRun).options(joinedload(ProductionRun.product)).order_by(ProductionRun.id.desc()).limit(300).all()
    return render(request,db,"production.html",items=items,flash=pop_flash(request))

@app.get("/production/new",response_class=HTMLResponse)
def production_new(request:Request,db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    products=db.query(Product).filter(Product.active==True).order_by(Product.name).all()
    return render(request,db,"production_form.html",products=products)

@app.post("/production/save")
async def production_save(request:Request,db:Session=Depends(get_db)):
    require_user(request,db); f=await request.form(); csrf_guard(request,f)
    product_name=str(f.get("product_name","")).strip()
    p=get_or_create_product(db,product_name) if product_name else (db.get(Product,int(f.get("product_id"))) if f.get("product_id") else None)
    qty=D(f.get("qty"))
    if not p or qty<=0:
        flash(request,"Producto o cantidad inválida.","error"); return RedirectResponse("/production/new",303)
    p=db.query(Product).options(joinedload(Product.recipe).joinedload(Recipe.items).joinedload(RecipeItem.material)).filter(Product.id==p.id).first()
    requirements=[]; total_cost=D0
    if p.recipe:
        factor=qty/D(p.recipe.yield_qty)
        for ri in p.recipe.items:
            needed=D(ri.qty)*factor
            if D(ri.material.stock)<needed:
                flash(request,f"Insumo insuficiente: {ri.material.name}. Necesitás {num(needed)} {ri.material.unit}.","error"); return RedirectResponse("/production/new",303)
            requirements.append((ri.material,needed)); total_cost+=needed*D(ri.material.avg_cost)
    else:
        manual_unit_cost=D(f.get("unit_cost_manual"))
        if manual_unit_cost<=0:
            manual_unit_cost=D(p.cost)
        total_cost=qty*manual_unit_cost
    run=ProductionRun(product_id=p.id,date=parse_date(str(f.get("date"))),qty=qty,total_cost=total_cost,unit_cost=(total_cost/qty if qty else D0),notes=str(f.get("notes","")).strip() or None)
    db.add(run); db.flush()
    for m,needed in requirements:
        db.add(ProductionItem(production_id=run.id, material_id=m.id, qty=needed, unit_cost=D(m.avg_cost), subtotal=needed*D(m.avg_cost)))
        add_movement(db,"material",m,-needed,f"Producción #{run.id}: {p.name}","production",run.id)
    old_qty=D(p.stock); old_value=old_qty*D(p.cost)
    add_movement(db,"product",p,qty,f"Producción #{run.id}","production",run.id)
    if D(p.stock)>0: p.cost=(old_value+total_cost)/D(p.stock)
    db.commit()
    if p.recipe:
        flash(request,"Producción registrada; insumos descontados y producto terminado ingresado.")
    else:
        flash(request,"Lote registrado sin receta. Se sumó al stock sin descontar insumos.","ok")
    return RedirectResponse("/production",303)

@app.post("/production/{rid}/void")
async def production_void(rid:int,request:Request,db:Session=Depends(get_db)):
    require_user(request,db); f=await request.form(); csrf_guard(request,f)
    run=db.query(ProductionRun).options(joinedload(ProductionRun.product),joinedload(ProductionRun.items).joinedload(ProductionItem.material)).filter(ProductionRun.id==rid).first()
    if run and run.status=="active":
        p=run.product
        if D(p.stock)<D(run.qty): flash(request,"No se puede anular: ya no hay suficiente stock del producto terminado.","error"); return RedirectResponse("/production",303)
        current_stock=D(p.stock); current_value=current_stock*D(p.cost)
        add_movement(db,"product",p,-D(run.qty),f"Anulación producción #{run.id}","production_void",run.id)
        for it in run.items: add_movement(db,"material",it.material,D(it.qty),f"Anulación producción #{run.id}","production_void",run.id)
        remaining=D(p.stock); reversed_value=D(run.qty)*D(run.unit_cost)
        if remaining>0 and current_value>=reversed_value: p.cost=(current_value-reversed_value)/remaining
        elif remaining==0: p.cost=D0
        run.status="void"; db.commit(); flash(request,"Producción anulada; inventarios revertidos.")
    return RedirectResponse("/production",303)

# ---------- Expenses ----------
@app.get("/expenses",response_class=HTMLResponse)
def expenses(request:Request,db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    return render(request,db,"expenses.html",items=db.query(Expense).order_by(Expense.id.desc()).limit(500).all(),flash=pop_flash(request))

@app.post("/expenses/save")
async def expense_save(request:Request,db:Session=Depends(get_db)):
    require_user(request,db); f=await request.form(); csrf_guard(request,f)
    x=Expense(date=parse_date(str(f.get("date"))),category=str(f.get("category","Otros")),description=str(f.get("description","")).strip(),amount=D(f.get("amount")))
    db.add(x); db.commit(); flash(request,"Gasto registrado."); return RedirectResponse("/expenses",303)

@app.post("/expenses/{eid}/void")
async def expense_void(eid:int,request:Request,db:Session=Depends(get_db)):
    require_user(request,db); f=await request.form(); csrf_guard(request,f); x=db.get(Expense,eid)
    if x: x.status="void"; db.commit(); flash(request,"Gasto anulado.")
    return RedirectResponse("/expenses",303)


@app.get("/account",response_class=HTMLResponse)
def account_get(request:Request,db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    return render(request,db,"account.html",flash=pop_flash(request))

@app.post("/account/password")
async def account_password(request:Request,db:Session=Depends(get_db)):
    u=require_user(request,db); f=await request.form(); csrf_guard(request,f)
    current=str(f.get("current_password","")); new=str(f.get("new_password","")); confirm=str(f.get("confirm_password",""))
    if not verify_password(current,u.password_hash): flash(request,"La contraseña actual no es correcta.","error")
    elif len(new)<8: flash(request,"La nueva contraseña debe tener al menos 8 caracteres.","error")
    elif new!=confirm: flash(request,"La confirmación no coincide.","error")
    else:
        u.password_hash=hash_password(new); db.commit(); flash(request,"Contraseña actualizada.")
    return RedirectResponse("/account",303)

# ---------- Reports / movements ----------
@app.get("/reports",response_class=HTMLResponse)
def reports(request:Request,db:Session=Depends(get_db),start:str|None=None,end:str|None=None):
    if (r:=guard(request,db)): return r
    d1=parse_date(start, date.today().replace(day=1)) if start else date.today().replace(day=1); d2=parse_date(end,date.today()) if end else date.today()
    sales=db.query(Sale).filter(Sale.status=="active",Sale.date>=d1,Sale.date<=d2).all(); expenses=db.query(Expense).filter(Expense.status=="active",Expense.date>=d1,Expense.date<=d2).all()
    revenue=sum((D(s.total) for s in sales),D0); cogs=sum((D(s.cogs) for s in sales),D0); gross=revenue-cogs; ex=sum((D(x.amount) for x in expenses),D0)
    sale_items=db.query(SaleItem).join(Sale).options(joinedload(SaleItem.product)).filter(Sale.status=="active",Sale.date>=d1,Sale.date<=d2).all()
    by_product={}
    for it in sale_items:
        row=by_product.setdefault(it.product.name,{"qty":D0,"revenue":D0,"cogs":D0})
        row["qty"]+=D(it.qty); row["revenue"]+=D(it.subtotal); row["cogs"]+=D(it.qty)*D(it.unit_cost)
    ranked=sorted(by_product.items(),key=lambda x:x[1]["revenue"],reverse=True)
    return render(request,db,"reports.html",start=d1,end=d2,revenue=revenue,cogs=cogs,gross=gross,expenses=ex,net=gross-ex,ranked=ranked)

@app.get("/movements",response_class=HTMLResponse)
def movements(request:Request,db:Session=Depends(get_db)):
    if (r:=guard(request,db)): return r
    items=db.query(InventoryMovement).order_by(InventoryMovement.id.desc()).limit(1000).all()
    return render(request,db,"movements.html",items=items)

# ---------- CSV / backup ----------
def csv_response(filename, headers, rows):
    sio=io.StringIO(); w=csv.writer(sio,delimiter=";"); w.writerow(headers); w.writerows(rows)
    data=("\ufeff"+sio.getvalue()).encode("utf-8")
    return StreamingResponse(iter([data]),media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="{filename}"'})

@app.get("/export/sales.csv")
def export_sales(request:Request,db:Session=Depends(get_db)):
    require_user(request,db); rows=[]
    for s in db.query(Sale).order_by(Sale.date).all(): rows.append([s.id,s.date,s.status,s.customer.name if s.customer else "",s.payment_method,s.channel,s.total,s.cogs,s.profit])
    return csv_response("ventas_zafirah.csv",["ID","Fecha","Estado","Cliente","Pago","Canal","Total","Costo","Ganancia"],rows)

@app.get("/export/stock.csv")
def export_stock(request:Request,db:Session=Depends(get_db)):
    require_user(request,db); rows=[]
    for p in db.query(Product).order_by(Product.name): rows.append(["Producto",p.sku,p.name,"unidad",p.stock,p.min_stock,p.cost,p.sale_price])
    for m in db.query(Material).order_by(Material.name): rows.append(["Insumo",m.sku,m.name,m.unit,m.stock,m.min_stock,m.avg_cost,""])
    return csv_response("stock_zafirah.csv",["Tipo","SKU","Nombre","Unidad","Stock","Mínimo","Costo","Precio"],rows)

def _jsonable(v):
    if isinstance(v, (datetime, date, Decimal)):
        return str(v)
    return v

def _table_rows(db, model):
    cols = [c.name for c in model.__table__.columns]
    out = []
    for obj in db.query(model).order_by(model.id).all():
        out.append({c: _jsonable(getattr(obj, c)) for c in cols})
    return out

@app.get("/backup")
def backup(request:Request,db:Session=Depends(get_db)):
    require_user(request,db)
    models = [User, Product, Material, Recipe, RecipeItem, Supplier, Customer, Purchase, PurchaseItem, Sale, SaleItem, ProductionRun, ProductionItem, Expense, InventoryMovement]
    payload = {
        "app": "ZAFIRAH Gestión",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "database": "sqlite" if IS_SQLITE else "postgresql",
        "tables": {m.__tablename__: _table_rows(db, m) for m in models},
    }
    fd, path = tempfile.mkstemp(prefix="zafirah_backup_", suffix=".zip")
    os.close(fd)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("zafirah_backup.json", json.dumps(payload, ensure_ascii=False, indent=2))
    filename=f"zafirah_backup_{datetime.now():%Y%m%d_%H%M%S}.zip"
    return FileResponse(path,filename=filename,media_type="application/zip")

@app.get("/health")
def health(): return {"ok":True,"app":"ZAFIRAH Gestión"}
