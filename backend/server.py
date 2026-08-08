from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os, logging, jwt, bcrypt, httpx, asyncio
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from pydantic import BaseModel, EmailStr
from typing import Optional, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("swipeupcar")

client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALG = "HS256"
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "SWIPEUPCAR")
COMMISSION = 0.05

app = FastAPI()
api = APIRouter(prefix="/api")

# ---------- helpers ----------
def hash_pw(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_pw(p, h): return bcrypt.checkpw(p.encode(), h.encode())
def make_token(uid): return jwt.encode({"sub": uid, "exp": datetime.now(timezone.utc)+timedelta(days=7)}, JWT_SECRET, algorithm=JWT_ALG)
def oid(x):
    try: return ObjectId(x)
    except Exception: return None

def clean_user(u):
    if not u: return None
    u = dict(u); u["id"] = str(u.pop("_id")); u.pop("password_hash", None)
    return u

async def current_user(request: Request):
    token = None
    ah = request.headers.get("Authorization", "")
    if ah.startswith("Bearer "): token = ah[7:]
    if not token: raise HTTPException(401, "Non authentifié")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError: raise HTTPException(401, "Session expirée")
    except jwt.InvalidTokenError: raise HTTPException(401, "Jeton invalide")
    u = await db.users.find_one({"_id": oid(payload["sub"])})
    if not u: raise HTTPException(401, "Utilisateur introuvable")
    return u

async def send_email(to, subject, html):
    if not EMAIL_KEY:
        logger.info(f"[EMAIL skip] {to}: {subject}"); return
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                headers={"X-Email-Key": EMAIL_KEY},
                json={"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME})
        r.raise_for_status()
        logger.info(f"[EMAIL sent] {to}: {subject}")
    except Exception as e:
        logger.error(f"[EMAIL fail] {to}: {e}")

def mail_tpl(title, body):
    return f"""<table width="100%" cellpadding="0" cellspacing="0" style="background:#F4EDE2;padding:24px;font-family:Arial,sans-serif">
    <tr><td align="center"><table width="560" cellpadding="0" cellspacing="0" style="background:#FBF8F2;border-radius:14px;overflow:hidden">
    <tr><td style="background:#1A1714;padding:20px 28px;color:#fff;font-size:22px;font-weight:bold">SWIPEUP<span style="color:#B71C1C">CAR</span></td></tr>
    <tr><td style="padding:28px"><h1 style="color:#1A1714;font-size:22px;margin:0 0 12px">{title}</h1><div style="color:#40382f;font-size:15px;line-height:1.6">{body}</div></td></tr>
    <tr><td style="padding:18px 28px;background:#EFE6D6;color:#6B6259;font-size:12px">SWIPEUPCAR — plateforme de mise en relation automobile. Ceci est un email transactionnel.</td></tr>
    </table></td></tr></table>"""

# ---------- models ----------
class RegisterIn(BaseModel):
    firstName: str; lastName: str = ""; email: EmailStr; password: str
    phone: str = ""; role: str = "PARTICULIER"
    company: Optional[str] = None; siret: Optional[str] = None; iban: Optional[str] = None
    proType: Optional[str] = None; city: Optional[str] = None
SERVICE_TYPES = {"GARAGE", "PNEUMATIQUE", "LAVAGE"}
class ServiceIn(BaseModel):
    name: str; price: float = 0; duration: str = ""
class ProfileIn(BaseModel):
    city: str = ""; description: str = ""; company: str = ""
class ApptIn(BaseModel):
    providerId: str; serviceName: str; price: float = 0; date: str; time: str
class LoginIn(BaseModel):
    email: EmailStr; password: str
class VehicleIn(BaseModel):
    brand: str; model: str; year: int; cat: str; km: int = 0; power: int = 0
    fuel: str; gear: str; seats: int = 5; doors: int = 5; color: str = ""
    price: float; priceWe: float = 0; priceWeek: float = 0; city: str; dept: str = ""
    lat: float = 46.6; lng: float = 2.2; deposit: float = 1000; minAge: int = 21
    mileageInc: int = 250; features: List[str] = []; images: List[str] = []
    desc: str = ""; status: str = "pending"
class BookingIn(BaseModel):
    vehicleId: str; frm: str; to: str

# ---------- auth ----------
@api.post("/auth/register")
async def register(data: RegisterIn):
    email = data.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Cet email est déjà utilisé.")
    role = data.role if data.role in ("PARTICULIER", "LOUEUR", "PRO") else "PARTICULIER"
    doc = {"firstName": data.firstName, "lastName": data.lastName, "email": email,
           "password_hash": hash_pw(data.password), "phone": data.phone, "role": role,
           "verified": False, "created_at": datetime.now(timezone.utc).isoformat()}
    if role == "LOUEUR":
        doc.update({"company": data.company, "siret": data.siret, "iban": data.iban,
                    "proStatus": "En vérification", "rating": 0, "rentals": 0,
                    "since": str(datetime.now().year), "satisfaction": 0})
    if role == "PRO":
        pt = data.proType if data.proType in SERVICE_TYPES else "LAVAGE"
        doc.update({"company": data.company, "siret": data.siret, "proType": pt,
                    "city": data.city or "", "lat": 46.6, "lng": 2.2, "description": "",
                    "proStatus": "En vérification", "rating": 0, "jobs": 0,
                    "since": str(datetime.now().year), "services": []})
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    await send_email(email, "Bienvenue sur SWIPEUPCAR",
        mail_tpl("Compte créé 🎉", f"Bonjour {data.firstName}, votre compte SWIPEUPCAR est actif." + (
            " Votre dossier professionnel est en cours de vérification par notre équipe." if role in ("LOUEUR","PRO") else "")))
    if role in ("LOUEUR", "PRO"):
        admin = await db.users.find_one({"role": "ADMIN"})
        if admin: await send_email(admin["email"], "Nouveau professionnel à valider", mail_tpl("Pro en attente", f"{data.company or data.firstName} ({role}) vient de s'inscrire."))
    return {"token": make_token(str(res.inserted_id)), "user": clean_user(doc)}

@api.post("/auth/login")
async def login(data: LoginIn):
    u = await db.users.find_one({"email": data.email.lower()})
    if not u or not verify_pw(data.password, u["password_hash"]):
        raise HTTPException(401, "Email ou mot de passe incorrect.")
    return {"token": make_token(str(u["_id"])), "user": clean_user(u)}

@api.get("/auth/me")
async def me(u=Depends(current_user)):
    return clean_user(u)

# ---------- vehicles ----------
async def vehicle_out(v):
    v = dict(v); v["id"] = str(v.pop("_id"))
    o = await db.users.find_one({"_id": oid(v["owner"])}) if v.get("owner") else None
    if o:
        v["ownerName"] = o.get("company") or o.get("firstName")
        v["ownerFirst"] = o.get("firstName"); v["ownerVerified"] = o.get("verified", False)
        v["ownerRating"] = o.get("rating", 0); v["ownerRentals"] = o.get("rentals", 0)
        v["ownerSince"] = o.get("since", "2026"); v["ownerSatisfaction"] = o.get("satisfaction", 0)
    return v

@api.get("/vehicles")
async def list_vehicles():
    out = [await vehicle_out(v) for v in await db.vehicles.find({"status": "approved"}).to_list(500)]
    return out

@api.get("/vehicles/{vid}")
async def get_vehicle(vid: str):
    v = await db.vehicles.find_one({"_id": oid(vid)})
    if not v: raise HTTPException(404, "Véhicule introuvable")
    out = await vehicle_out(v)
    bk = await db.bookings.find({"vehicleId": vid, "status": "confirmed"}).to_list(200)
    out["booked"] = [{"frm": b["frm"], "to": b["to"]} for b in bk]
    return out

@api.get("/vehicles/owner/mine")
async def my_vehicles(u=Depends(current_user)):
    return [await vehicle_out(v) for v in await db.vehicles.find({"owner": str(u["_id"])}).to_list(500)]

@api.post("/vehicles")
async def add_vehicle(data: VehicleIn, u=Depends(current_user)):
    if u["role"] not in ("LOUEUR", "ADMIN"): raise HTTPException(403, "Réservé aux loueurs")
    doc = data.model_dump(); doc["owner"] = str(u["_id"]); doc["rating"] = 0; doc["reviews"] = 0
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.vehicles.insert_one(doc)
    return {"id": str(res.inserted_id)}

@api.delete("/vehicles/{vid}")
async def del_vehicle(vid: str, u=Depends(current_user)):
    v = await db.vehicles.find_one({"_id": oid(vid)})
    if not v: raise HTTPException(404)
    if v["owner"] != str(u["_id"]) and u["role"] != "ADMIN": raise HTTPException(403, "Non autorisé")
    await db.vehicles.delete_one({"_id": oid(vid)})
    return {"ok": True}

@api.post("/vehicles/{vid}/submit")
async def submit_vehicle(vid: str, u=Depends(current_user)):
    v = await db.vehicles.find_one({"_id": oid(vid)})
    if not v or v["owner"] != str(u["_id"]): raise HTTPException(403)
    await db.vehicles.update_one({"_id": oid(vid)}, {"$set": {"status": "pending"}})
    return {"ok": True}

# ---------- bookings ----------
def days_between(a, b):
    return max(1, (datetime.fromisoformat(b) - datetime.fromisoformat(a)).days)

@api.post("/bookings")
async def create_booking(data: BookingIn, u=Depends(current_user)):
    v = await db.vehicles.find_one({"_id": oid(data.vehicleId)})
    if not v or v["status"] != "approved": raise HTTPException(400, "Véhicule indisponible.")
    clash = await db.bookings.find_one({"vehicleId": data.vehicleId, "status": "confirmed",
        "$nor": [{"to": {"$lte": data.frm}}, {"frm": {"$gte": data.to}}]})
    if clash: raise HTTPException(409, "Ces dates ne sont plus disponibles.")
    days = days_between(data.frm, data.to)
    total = round(days * v["price"]); commission = round(total * COMMISSION)
    ref = "SUC-" + os.urandom(3).hex().upper()
    owner = await db.users.find_one({"_id": oid(v["owner"])})
    doc = {"ref": ref, "userId": str(u["_id"]), "ownerId": v["owner"], "vehicleId": data.vehicleId,
           "frm": data.frm, "to": data.to, "days": days, "total": total, "commission": commission,
           "ownerAmount": total - commission, "status": "confirmed", "paid": True,
           "vehicleTitle": f"{v['brand']} {v['model']}", "vehicleImage": (v.get("images") or [""])[0],
           "clientName": u["firstName"], "ownerName": owner.get("company") or owner.get("firstName") if owner else "",
           "createdAt": datetime.now(timezone.utc).isoformat()}
    res = await db.bookings.insert_one(doc)
    await db.users.update_one({"_id": oid(v["owner"])}, {"$inc": {"rentals": 1}})
    await send_email(u["email"], f"Réservation confirmée — {ref}",
        mail_tpl("Réservation confirmée ✅", f"Votre réservation <b>{v['brand']} {v['model']}</b> du {data.frm} au {data.to} est confirmée.<br>Montant payé : <b>{total} €</b> (dont commission SWIPEUPCAR 5% : {commission} €).<br>Référence : <b>{ref}</b>"))
    if owner:
        await send_email(owner["email"], f"Nouvelle réservation — {ref}",
            mail_tpl("Nouvelle réservation 🚗", f"Vous avez reçu une réservation pour <b>{v['brand']} {v['model']}</b>.<br>Montant net (95%) : <b>{total-commission} €</b><br>Référence : {ref}"))
    doc.pop("_id", None); doc["id"] = str(res.inserted_id)
    return doc

@api.get("/bookings/mine")
async def my_bookings(u=Depends(current_user)):
    rows = await db.bookings.find({"userId": str(u["_id"])}).sort("createdAt", -1).to_list(500)
    for r in rows: r["id"] = str(r.pop("_id"))
    return rows

@api.get("/bookings/owner")
async def owner_bookings(u=Depends(current_user)):
    rows = await db.bookings.find({"ownerId": str(u["_id"])}).sort("createdAt", -1).to_list(500)
    for r in rows: r["id"] = str(r.pop("_id"))
    return rows

# ---------- providers (services: garage/pneus/lavage) - RDV only ----------
def provider_pub(u):
    return {"id": str(u["_id"]), "firstName": u.get("firstName"), "company": u.get("company"),
            "proType": u.get("proType"), "city": u.get("city",""), "lat": u.get("lat",46.6), "lng": u.get("lng",2.2),
            "description": u.get("description",""), "services": u.get("services",[]),
            "verified": u.get("verified",False), "rating": u.get("rating",0), "jobs": u.get("jobs",0), "since": u.get("since","2026")}

@api.get("/providers")
async def list_providers(type: str):
    us = await db.users.find({"role":"PRO","proType":type,"proStatus":"Validé"}).to_list(300)
    return [provider_pub(u) for u in us]

@api.get("/providers/{pid}")
async def get_provider(pid: str):
    u = await db.users.find_one({"_id": oid(pid), "role":"PRO"})
    if not u: raise HTTPException(404, "Professionnel introuvable")
    return provider_pub(u)

@api.get("/providers/me/profile")
async def my_provider(u=Depends(current_user)):
    if u["role"] != "PRO": raise HTTPException(403)
    return clean_user(u)

@api.post("/providers/service")
async def add_service(data: ServiceIn, u=Depends(current_user)):
    if u["role"] != "PRO": raise HTTPException(403)
    await db.users.update_one({"_id": u["_id"]}, {"$push": {"services": data.model_dump()}})
    return {"ok": True}

@api.delete("/providers/service/{name}")
async def del_service(name: str, u=Depends(current_user)):
    if u["role"] != "PRO": raise HTTPException(403)
    await db.users.update_one({"_id": u["_id"]}, {"$pull": {"services": {"name": name}}})
    return {"ok": True}

@api.post("/providers/profile")
async def update_profile(data: ProfileIn, u=Depends(current_user)):
    if u["role"] != "PRO": raise HTTPException(403)
    upd = {k: v for k, v in data.model_dump().items() if v}
    await db.users.update_one({"_id": u["_id"]}, {"$set": upd})
    return {"ok": True}

# ---------- appointments (RDV, sans paiement) ----------
@api.post("/appointments")
async def create_appt(data: ApptIn, u=Depends(current_user)):
    p = await db.users.find_one({"_id": oid(data.providerId), "role":"PRO"})
    if not p or p.get("proStatus") != "Validé": raise HTTPException(400, "Professionnel indisponible.")
    ref = "RDV-" + os.urandom(3).hex().upper()
    doc = {"ref": ref, "userId": str(u["_id"]), "providerId": data.providerId, "proType": p.get("proType"),
           "serviceName": data.serviceName, "price": data.price, "date": data.date, "time": data.time,
           "status": "confirmé", "clientName": u["firstName"], "providerName": p.get("company") or p.get("firstName"),
           "createdAt": datetime.now(timezone.utc).isoformat()}
    res = await db.appointments.insert_one(doc)
    await db.users.update_one({"_id": p["_id"]}, {"$inc": {"jobs": 1}})
    await send_email(u["email"], f"Rendez-vous confirmé — {ref}",
        mail_tpl("Rendez-vous confirmé ✅", f"Votre RDV « {data.serviceName} » chez <b>{doc['providerName']}</b> le {data.date} à {data.time} est confirmé.<br>Référence : <b>{ref}</b>"))
    await send_email(p["email"], f"Nouveau rendez-vous — {ref}",
        mail_tpl("Nouveau rendez-vous 📅", f"Nouveau RDV « {data.serviceName} » le {data.date} à {data.time} (client : {u['firstName']}).<br>Référence : {ref}"))
    doc["id"] = str(res.inserted_id); doc.pop("_id", None)
    return doc

@api.get("/appointments/mine")
async def my_appts(u=Depends(current_user)):
    rows = await db.appointments.find({"userId": str(u["_id"])}).sort("createdAt", -1).to_list(500)
    for r in rows: r["id"] = str(r.pop("_id"))
    return rows

@api.get("/appointments/pro")
async def pro_appts(u=Depends(current_user)):
    rows = await db.appointments.find({"providerId": str(u["_id"])}).sort("createdAt", -1).to_list(500)
    for r in rows: r["id"] = str(r.pop("_id"))
    return rows

# ---------- admin ----------
async def require_admin(u=Depends(current_user)):
    if u["role"] != "ADMIN": raise HTTPException(403, "Réservé à l'administration")
    return u

@api.get("/admin/overview")
async def admin_overview(u=Depends(require_admin)):
    bookings = await db.bookings.find().sort("createdAt", -1).to_list(1000)
    users = await db.users.find().to_list(1000)
    vehicles = await db.vehicles.find().to_list(1000)
    for b in bookings: b["id"] = str(b.pop("_id"))
    appts = await db.appointments.find().sort("createdAt", -1).to_list(1000)
    for a in appts: a["id"] = str(a.pop("_id"))
    return {
        "ca": sum(b["total"] for b in bookings),
        "commission": sum(b["commission"] for b in bookings),
        "bookings": bookings,
        "appointments": appts,
        "owners": [clean_user(x) for x in users if x["role"] == "LOUEUR"],
        "providers": [provider_pub(x) for x in users if x["role"] == "PRO"],
        "clients": [clean_user(x) for x in users if x["role"] == "PARTICULIER"],
        "vehicles": [await vehicle_out(v) for v in vehicles],
        "pendingVehicles": sum(1 for v in vehicles if v["status"] == "pending"),
        "pendingOwners": sum(1 for x in users if x["role"] in ("LOUEUR","PRO") and x.get("proStatus") not in (None, "Validé")),
    }

@api.post("/admin/owners/{uid}/{action}")
async def admin_owner(uid: str, action: str, u=Depends(require_admin)):
    o = await db.users.find_one({"_id": oid(uid)})
    if not o: raise HTTPException(404)
    if action == "validate":
        await db.users.update_one({"_id": oid(uid)}, {"$set": {"proStatus": "Validé", "verified": True}})
        await send_email(o["email"], "Compte loueur validé ✅", mail_tpl("Vous êtes validé !", "Votre compte loueur SWIPEUPCAR est validé. Vous pouvez publier vos véhicules."))
    elif action == "refuse":
        await db.users.update_one({"_id": oid(uid)}, {"$set": {"proStatus": "Refusé"}})
        await send_email(o["email"], "Candidature refusée", mail_tpl("Candidature refusée", "Votre candidature loueur n'a pas été retenue."))
    return {"ok": True}

@api.post("/admin/vehicles/{vid}/{action}")
async def admin_vehicle(vid: str, action: str, request: Request, u=Depends(require_admin)):
    v = await db.vehicles.find_one({"_id": oid(vid)})
    if not v: raise HTTPException(404)
    owner = await db.users.find_one({"_id": oid(v["owner"])})
    if action == "approve":
        await db.vehicles.update_one({"_id": oid(vid)}, {"$set": {"status": "approved"}})
        if owner: await send_email(owner["email"], "Véhicule approuvé ✅", mail_tpl("Annonce en ligne", f"Votre véhicule <b>{v['brand']} {v['model']}</b> est approuvé et visible publiquement."))
    elif action == "reject":
        body = await request.json()
        reason = body.get("reason", "Non conforme")
        await db.vehicles.update_one({"_id": oid(vid)}, {"$set": {"status": "rejected", "rejectReason": reason}})
        if owner: await send_email(owner["email"], "Véhicule refusé", mail_tpl("Annonce refusée", f"Votre véhicule <b>{v['brand']} {v['model']}</b> a été refusé : {reason}"))
    return {"ok": True}

# ---------- seed ----------
IMG = {
 "orange":"https://images.unsplash.com/photo-1763933356125-69476dc6eb5d?w=900&q=80",
 "sedan":"https://images.unsplash.com/photo-1612895889733-814f45ae878f?w=900&q=80",
 "ferrari":"https://images.unsplash.com/photo-1730298876364-2cab8e09d0a4?w=900&q=80",
 "aston":"https://images.unsplash.com/photo-1730302551882-99cb98b4adc4?w=900&q=80",
 "bmwx":"https://images.unsplash.com/photo-1604657645490-c228a616c7ee?w=900&q=80",
 "hyundai":"https://images.unsplash.com/photo-1587580945215-5d4aabb2c8ef?w=900&q=80",
 "rav4":"https://images.unsplash.com/photo-1615887110697-0819ec23465f?w=900&q=80",
 "crv":"https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=900&q=80",
}

@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    admin_email = os.environ["ADMIN_EMAIL"].lower()
    if not await db.users.find_one({"email": admin_email}):
        await db.users.insert_one({"firstName": "Admin", "lastName": "SUC", "email": admin_email,
            "password_hash": hash_pw(os.environ["ADMIN_PASSWORD"]), "role": "ADMIN", "verified": True})
    # demo loueurs + client
    async def ensure_user(email, pw, doc):
        ex = await db.users.find_one({"email": email})
        if ex: return str(ex["_id"])
        doc["email"] = email; doc["password_hash"] = hash_pw(pw)
        r = await db.users.insert_one(doc); return str(r.inserted_id)
    l1 = await ensure_user("loueur@swipeupcar.fr", "loueur123", {"firstName":"Thomas","lastName":"Martin","role":"LOUEUR","verified":True,"proStatus":"Validé","siret":"81234567800012","company":"Martin Auto Location","rating":4.9,"rentals":118,"since":"2023","satisfaction":98})
    l2 = await ensure_user("sophie@swipeupcar.fr", "loueur123", {"firstName":"Sophie","lastName":"Durand","role":"LOUEUR","verified":True,"proStatus":"Validé","siret":"75234567800045","company":"Durand Mobilité","rating":4.7,"rentals":64,"since":"2024","satisfaction":95})
    await ensure_user("client@swipeupcar.fr", "client123", {"firstName":"Julie","lastName":"Bernard","role":"PARTICULIER","verified":True,"phone":"0600000000"})
    if await db.vehicles.count_documents({}) == 0:
        seed = [
          {"owner":l1,"brand":"BMW","model":"Série 5","year":2022,"cat":"Berline","km":28000,"power":190,"fuel":"Diesel","gear":"Automatique","seats":5,"doors":5,"color":"Noir","price":120,"priceWe":220,"priceWeek":700,"city":"Paris","dept":"75","lat":48.8566,"lng":2.3522,"rating":4.9,"reviews":42,"status":"approved","deposit":1500,"minAge":23,"mileageInc":200,"features":["GPS","CarPlay","Caméra","Climatisation"],"images":[IMG["sedan"],IMG["aston"]],"desc":"Berline premium idéale pour vos déplacements pro et week-ends."},
          {"owner":l1,"brand":"Renault","model":"Clio","year":2023,"cat":"Citadine","km":12000,"power":90,"fuel":"Essence","gear":"Manuelle","seats":5,"doors":5,"color":"Gris","price":39,"priceWe":70,"priceWeek":230,"city":"Lyon","dept":"69","lat":45.764,"lng":4.8357,"rating":4.7,"reviews":63,"status":"approved","deposit":600,"minAge":19,"mileageInc":250,"features":["CarPlay","Android Auto","Climatisation"],"images":[IMG["crv"]],"desc":"Citadine économique, parfaite pour la ville."},
          {"owner":l2,"brand":"Tesla","model":"Model 3","year":2023,"cat":"Premium","km":15000,"power":283,"fuel":"Électrique","gear":"Automatique","seats":5,"doors":5,"color":"Blanc","price":99,"priceWe":180,"priceWeek":600,"city":"Bordeaux","dept":"33","lat":44.8378,"lng":-0.5792,"rating":4.95,"reviews":31,"status":"approved","deposit":2000,"minAge":23,"mileageInc":300,"features":["GPS","Caméra","Toit panoramique","CarPlay"],"images":[IMG["sedan"]],"desc":"100% électrique, technologie de pointe, silence absolu."},
          {"owner":l2,"brand":"Peugeot","model":"3008","year":2021,"cat":"SUV","km":41000,"power":130,"fuel":"Diesel","gear":"Automatique","seats":5,"doors":5,"color":"Bleu","price":75,"priceWe":135,"priceWeek":450,"city":"Marseille","dept":"13","lat":43.2965,"lng":5.3698,"rating":4.6,"reviews":28,"status":"approved","deposit":1000,"minAge":21,"mileageInc":250,"features":["GPS","Caméra","Climatisation","Siège bébé"],"images":[IMG["rav4"],IMG["hyundai"]],"desc":"SUV familial confortable et spacieux."},
          {"owner":l1,"brand":"Porsche","model":"911","year":2022,"cat":"Sportive","km":9000,"power":450,"fuel":"Essence","gear":"Automatique","seats":2,"doors":2,"color":"Rouge","price":390,"priceWe":720,"priceWeek":2400,"city":"Nice","dept":"06","lat":43.7102,"lng":7.262,"rating":5.0,"reviews":12,"status":"approved","deposit":5000,"minAge":28,"mileageInc":150,"features":["GPS","CarPlay","Caméra"],"images":[IMG["ferrari"],IMG["orange"]],"desc":"L'expérience sportive ultime pour un week-end d'exception."},
          {"owner":l2,"brand":"Volkswagen","model":"Transporter","year":2020,"cat":"Utilitaire","km":88000,"power":150,"fuel":"Diesel","gear":"Manuelle","seats":3,"doors":4,"color":"Blanc","price":69,"priceWe":120,"priceWeek":400,"city":"Lille","dept":"59","lat":50.6292,"lng":3.0573,"rating":4.4,"reviews":19,"status":"approved","deposit":900,"minAge":23,"mileageInc":300,"features":["Climatisation","GPS"],"images":[IMG["crv"]],"desc":"Utilitaire pour vos déménagements et livraisons."},
          {"owner":l1,"brand":"Audi","model":"Q5","year":2023,"cat":"SUV","km":18000,"power":204,"fuel":"Hybride","gear":"Automatique","seats":5,"doors":5,"color":"Gris","price":110,"priceWe":200,"priceWeek":650,"city":"Toulouse","dept":"31","lat":43.6047,"lng":1.4442,"rating":4.8,"reviews":24,"status":"approved","deposit":1500,"minAge":23,"mileageInc":250,"features":["GPS","CarPlay","Android Auto","Caméra","Toit panoramique"],"images":[IMG["bmwx"],IMG["rav4"]],"desc":"SUV hybride élégant, faible consommation."},
          {"owner":l2,"brand":"Fiat","model":"500","year":2022,"cat":"Citadine","km":22000,"power":70,"fuel":"Essence","gear":"Manuelle","seats":4,"doors":3,"color":"Rouge","price":34,"priceWe":60,"priceWeek":200,"city":"Nantes","dept":"44","lat":47.2184,"lng":-1.5536,"rating":4.6,"reviews":37,"status":"approved","deposit":500,"minAge":19,"mileageInc":250,"features":["Climatisation","CarPlay"],"images":[IMG["orange"]],"desc":"Petite citadine iconique et fun."},
        ]
        await db.vehicles.insert_many(seed)
    # demo service providers (RDV)
    async def ensure_pro(email, pw, doc):
        if await db.users.find_one({"email": email}): return
        doc["email"]=email; doc["password_hash"]=hash_pw(pw); doc["role"]="PRO"; doc["verified"]=True; doc["proStatus"]="Validé"
        await db.users.insert_one(doc)
    await ensure_pro("garage@swipeupcar.fr","pro123",{"firstName":"Karim","company":"Garage Central Auto","proType":"GARAGE","city":"Paris","lat":48.8566,"lng":2.3522,"description":"Entretien toutes marques, mécanique et révisions.","rating":4.8,"jobs":230,"since":"2022","services":[{"name":"Vidange + filtres","price":89,"duration":"1h"},{"name":"Révision complète","price":190,"duration":"2h"},{"name":"Plaquettes de frein","price":150,"duration":"1h30"}]})
    await ensure_pro("pneus@swipeupcar.fr","pro123",{"firstName":"Léa","company":"SpeedPneus Lyon","proType":"PNEUMATIQUE","city":"Lyon","lat":45.764,"lng":4.8357,"description":"Montage, équilibrage et géométrie.","rating":4.7,"jobs":180,"since":"2023","services":[{"name":"Montage 2 pneus","price":40,"duration":"45min"},{"name":"Montage 4 pneus","price":70,"duration":"1h"},{"name":"Géométrie","price":60,"duration":"45min"}]})
    await ensure_pro("lavage@swipeupcar.fr","pro123",{"firstName":"Hugo","company":"BullePro Detailing","proType":"LAVAGE","city":"Bordeaux","lat":44.8378,"lng":-0.5792,"description":"Lavage premium et detailing intérieur/extérieur.","rating":4.9,"jobs":310,"since":"2021","services":[{"name":"Lavage extérieur","price":25,"duration":"30min"},{"name":"Complet int/ext","price":59,"duration":"1h30"},{"name":"Detailing premium","price":149,"duration":"4h"}]})
    logger.info("Seed complete")

app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"], allow_headers=["*"])

@app.on_event("shutdown")
async def shutdown():
    client.close()
