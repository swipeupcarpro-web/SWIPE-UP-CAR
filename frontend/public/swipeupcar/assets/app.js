/* SWIPEUPCAR - client API (backend réel FastAPI+MongoDB, JWT).
   Entités serveur : comptes, véhicules, réservations. Favoris/messages/avis : stockage local navigateur. */
const API_ROOT = window.location.origin + '/api';
const money=n=>Number(n).toLocaleString('fr-FR')+' €';
const uid=p=>p+Math.random().toString(36).slice(2,8).toUpperCase();
const todayISO=()=>new Date().toISOString().slice(0,10);
const addDays=(d,n)=>{const x=new Date(d);x.setDate(x.getDate()+n);return x.toISOString().slice(0,10)};
const daysBetween=(a,b)=>Math.max(1,Math.round((new Date(b)-new Date(a))/864e5));

const IMG={
  orange:'https://images.unsplash.com/photo-1763933356125-69476dc6eb5d?w=900&q=80',
  sedan:'https://images.unsplash.com/photo-1612895889733-814f45ae878f?w=900&q=80',
  ferrari:'https://images.unsplash.com/photo-1730298876364-2cab8e09d0a4?w=900&q=80',
  aston:'https://images.unsplash.com/photo-1730302551882-99cb98b4adc4?w=900&q=80',
  bmwx:'https://images.unsplash.com/photo-1604657645490-c228a616c7ee?w=900&q=80',
  hyundai:'https://images.unsplash.com/photo-1587580945215-5d4aabb2c8ef?w=900&q=80',
  rav4:'https://images.unsplash.com/photo-1615887110697-0819ec23465f?w=900&q=80',
  crv:'https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=900&q=80',
};

/* ---- API (synchronous XHR so page code stays simple) ---- */
function apiSync(path, method='GET', body){
  const x=new XMLHttpRequest();
  try{ x.open(method, API_ROOT+path, false);
    x.setRequestHeader('Content-Type','application/json');
    const t=localStorage.getItem('suc_token'); if(t) x.setRequestHeader('Authorization','Bearer '+t);
    x.send(body?JSON.stringify(body):null);
  }catch(e){ return {error:'Réseau indisponible', status:0}; }
  let j={}; try{ j=JSON.parse(x.responseText||'{}'); }catch(e){}
  if(x.status<200||x.status>=300) return {error:(j.detail||('Erreur '+x.status)), status:x.status};
  return j;
}

/* ---- STATE (mirror of server data + local store) ---- */
const STATE={session:null,vehicles:[],bookings:[],users:[],settings:{commission:0.05},admin:null};
function localGet(){try{return JSON.parse(localStorage.getItem('suc_local'))||{}}catch(e){return{}}}
function loadState(){
  STATE.admin=null;
  const t=localStorage.getItem('suc_token'); STATE.session=null;
  if(t){ const me=apiSync('/auth/me'); if(me&&!me.error) STATE.session=me; else localStorage.removeItem('suc_token'); }
  let vehicles=apiSync('/vehicles'); if(vehicles.error) vehicles=[];
  let bookings=[]; const s=STATE.session;
  if(s){
    if(s.role==='PARTICULIER'){ const b=apiSync('/bookings/mine'); if(!b.error) bookings=b; }
    else if(s.role==='LOUEUR'){ const own=apiSync('/vehicles/owner/mine'); if(!own.error){ const ids=new Set(own.map(v=>v.id)); vehicles=vehicles.filter(v=>!ids.has(v.id)).concat(own);} const b=apiSync('/bookings/owner'); if(!b.error) bookings=b; }
    else if(s.role==='ADMIN'){ const ov=apiSync('/admin/overview'); if(!ov.error){ vehicles=ov.vehicles; bookings=ov.bookings; STATE.admin=ov; STATE.settings.commission = ov.ca? (ov.commission/ov.ca):0.05; STATE.settings.commission=0.05; } }
  }
  bookings.forEach(b=>{ b.from=b.frm; });
  STATE.vehicles=vehicles; STATE.bookings=bookings;
  const um={}; if(s) um[s.id]=s;
  vehicles.forEach(v=>{ if(v.owner&&!um[v.owner]) um[v.owner]={id:v.owner,firstName:v.ownerFirst||v.ownerName,company:v.ownerName,verified:v.ownerVerified,rating:v.ownerRating,rentals:v.ownerRentals,since:v.ownerSince,satisfaction:v.ownerSatisfaction}; });
  bookings.forEach(b=>{ if(b.userId&&!um[b.userId]) um[b.userId]={id:b.userId,firstName:b.clientName}; if(b.ownerId&&!um[b.ownerId]) um[b.ownerId]={id:b.ownerId,firstName:b.ownerName,company:b.ownerName}; });
  if(STATE.admin){ (STATE.admin.owners||[]).forEach(o=>um[o.id]=o); (STATE.admin.clients||[]).forEach(o=>um[o.id]=o); }
  STATE.users=Object.values(um);
}
window.SUC_refresh=loadState;

const DB={
  get(){ const l=localGet(); return {users:STATE.users,vehicles:STATE.vehicles,bookings:STATE.bookings,session:STATE.session,settings:STATE.settings,admin:STATE.admin,favorites:l.favorites||{},notifications:l.notifications||{},conversations:l.conversations||[],reviews:l.reviews||[]}; },
  set(db){ const l=localGet(); if(db.favorites)l.favorites=db.favorites; if(db.notifications)l.notifications=db.notifications; if(db.conversations)l.conversations=db.conversations; if(db.reviews)l.reviews=db.reviews; localStorage.setItem('suc_local',JSON.stringify(l)); },
};

/* ---- Auth ---- */
const Session={ get(){return STATE.session}, clear(){localStorage.removeItem('suc_token');STATE.session=null} };
function login(email,pw){ const r=apiSync('/auth/login','POST',{email,password:pw}); if(r.error) return null; localStorage.setItem('suc_token',r.token); loadState(); return STATE.session; }
function register(data){ data.origin_url=window.location.origin; const r=apiSync('/auth/register','POST',data); if(r.error) return {err:r.error}; localStorage.setItem('suc_token',r.token); loadState(); return {user:STATE.session}; }
function logout(){ Session.clear(); localStorage.removeItem('suc_local'); location.href='index.html'; }
function resetDemo(){ localStorage.removeItem('suc_local'); toast('Cache local réinitialisé'); setTimeout(()=>location.reload(),600); }

/* ---- Favorites / notifications (local) ---- */
function toggleFav(vid){const u=Session.get();if(!u){toast('Connectez-vous pour ajouter aux favoris');return false;}const r=apiSync('/favorites/'+vid,'POST');if(r.error){toast('Erreur');return false;}STATE.session.favorites=STATE.session.favorites||[];if(r.favorited){if(!STATE.session.favorites.includes(vid))STATE.session.favorites.push(vid);}else{STATE.session.favorites=STATE.session.favorites.filter(x=>x!==vid);}toast(r.favorited?'Ajouté aux favoris ♥':'Retiré des favoris');return r.favorited;}
function isFav(vid){const u=Session.get();if(!u)return false;return (u.favorites||[]).includes(vid);}
function notify(userId,text){ const db=DB.get(); db.notifications[userId]=db.notifications[userId]||[]; db.notifications[userId].unshift({id:uid('N'),text,date:new Date().toISOString(),read:false}); DB.set(db); }

/* ---- Messaging anti-bypass filter ---- */
const CONTACT_RE=/(\b0[1-9]([ .-]?\d{2}){4}\b)|(\+33)|([a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,})|(wa\.me|whatsapp|instagram|snap(chat)?|telegram|t\.me|facebook|https?:\/\/|www\.)/i;
function containsContact(t){ return CONTACT_RE.test(t); }

/* ---- Booking (server enforces availability + commission) ---- */
function overlaps(vid,from,to){ return STATE.bookings.some(b=>b.vehicleId===vid&&['confirmed','pending'].includes(b.status)&&!(to<=b.frm||from>=b.to)); }
function createBooking({vehicleId,from,to}){ const r=apiSync('/bookings','POST',{vehicleId,frm:from,to}); if(r.error) return {err:r.error}; r.from=r.frm; STATE.bookings.unshift(r); notify(STATE.session.id,`Réservation confirmée : ${r.vehicleTitle} (${r.ref})`); return {booking:r}; }

/* ---- UI ---- */
function initials(u){ return ((u.firstName||'?')[0]+(u.lastName||'')[0]).toUpperCase(); }
function renderNav(){
  const u=Session.get(); let right;
  if(!u){ right=`<a href="connexion.html" class="nav-link hide-mobile">Se connecter</a><a href="inscription.html" class="btn btn-red" style="padding:9px 18px" data-testid="nav-signup">S'inscrire</a>`; }
  else{
    const space=u.role==='ADMIN'?'admin.html':u.role==='LOUEUR'?'loueur.html':u.role==='PRO'?'pro.html':'compte.html';
    const nnotif=(DB.get().notifications[u.id]||[]).filter(n=>!n.read).length;
    right=`<a href="messages.html" class="nav-link hide-mobile" data-testid="nav-messages"><i class="fa-regular fa-comment"></i></a>
    <a href="${space}" class="nav-link hide-mobile" style="position:relative"><i class="fa-regular fa-bell"></i>${nnotif?`<span style="position:absolute;top:-2px;right:-8px;background:var(--red);color:#fff;font-size:10px;border-radius:999px;padding:1px 5px">${nnotif}</span>`:''}</a>
    <a href="${space}" class="chip" data-testid="nav-account"><span style="width:26px;height:26px;border-radius:50%;background:var(--carbon);color:#fff;display:grid;place-items:center;font-size:12px;font-weight:700">${initials(u)}</span>${u.firstName}</a>
    <button class="btn btn-ghost" style="padding:8px 14px" onclick="logout()" data-testid="nav-logout">Quitter</button>`;
  }
  const el=document.getElementById('nav'); if(!el) return;
  el.innerHTML=`<div style="position:sticky;top:0;z-index:100;background:rgba(244,237,226,.85);backdrop-filter:blur(12px);border-bottom:1px solid var(--line)">
    <div class="container" style="display:flex;align-items:center;gap:22px;height:66px">
      <a href="index.html" style="display:flex;align-items:center;gap:10px"><img src="assets/logo.png" alt="SWIPEUPCAR" style="height:46px;width:46px;border-radius:50%"><span style="font-family:'Fraunces',serif;font-weight:700;font-size:20px" class="hide-mobile">SWIPEUP<span style="color:var(--red)">CAR</span></span></a>
      <nav class="hide-mobile" style="display:flex;gap:20px;margin-left:10px">
        <a class="nav-link" href="location.html">Louer une voiture</a>
        <a class="nav-link" href="services.html?s=entretien">Entretien</a>
        <a class="nav-link" href="services.html?s=pneus">Pneus</a>
        <a class="nav-link" href="services.html?s=pieces">Pièces auto</a>
        <a class="nav-link" href="services.html?s=lavage">Lavage</a>
      </nav>
      <div style="margin-left:auto;display:flex;align-items:center;gap:12px">${right}</div>
    </div></div>`;
}
function renderFooter(){
  const el=document.getElementById('footer'); if(!el) return;
  el.innerHTML=`<footer style="background:var(--carbon);color:#EDE6DA;margin-top:60px">
   <div class="container" style="padding:50px 20px;display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:30px">
    <div style="max-width:260px"><img src="assets/logo.png" alt="SWIPEUPCAR" style="height:72px;width:72px;border-radius:50%"><p style="color:#b8ae9f;font-size:14px;margin-top:10px">La plateforme automobile nouvelle génération. Trouvez, réservez et profitez partout en France.</p></div>
    <div><h4 class="fh">Plateforme</h4><a href="location.html" class="foot">Louer une voiture</a><a href="services.html?s=entretien" class="foot">Entretien</a><a href="services.html?s=pneus" class="foot">Pneus</a><a href="services.html?s=pieces" class="foot">Pièces auto</a><a href="services.html?s=lavage" class="foot">Lavage</a></div>
    <div><h4 class="fh">Informations</h4><a href="infos.html#how" class="foot">Comment ça marche</a><a href="infos.html#security" class="foot">Sécurité</a><a href="infos.html#faq" class="foot">FAQ</a><a href="infos.html#cgu" class="foot">Conditions</a><a href="infos.html#privacy" class="foot">Confidentialité</a></div>
    <div><h4 class="fh">Professionnels</h4><a href="devenir-loueur.html" class="foot">Devenir loueur</a><a href="loueur.html" class="foot">Espace professionnel</a></div>
    <div><h4 class="fh">Support</h4><a href="infos.html#faq" class="foot">Centre d'aide</a><a href="infos.html#contact" class="foot">Contact</a><button onclick="resetDemo()" class="foot" style="background:none;border:none;cursor:pointer;text-align:left;padding:0">↻ Réinitialiser le cache</button></div>
   </div>
   <div style="border-top:1px solid #33302b"><div class="container" style="padding:18px 20px;display:flex;flex-wrap:wrap;gap:10px;justify-content:space-between;color:#8a8175;font-size:13px"><span>© 2026 SWIPEUPCAR — Plateforme de mise en relation.</span><a href="infos.html#legal" style="color:#8a8175">Mentions légales</a></div></div>
  </footer>
  <style>.foot{display:block;color:#d7cfc0;font-size:14px;padding:5px 0}.foot:hover{color:#fff}.fh{font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:#b8ae9f}</style>`;
}
function renderMobileNav(){
  const u=Session.get(); const space=u?(u.role==='LOUEUR'?'loueur.html':u.role==='ADMIN'?'admin.html':u.role==='PRO'?'pro.html':'compte.html'):'connexion.html';
  const el=document.getElementById('mnav'); if(!el) return;
  el.innerHTML=`<div class="mobile-nav">
    <a href="index.html" class="mn"><i class="fa-solid fa-house"></i><span>Accueil</span></a>
    <a href="location.html" class="mn"><i class="fa-solid fa-magnifying-glass"></i><span>Chercher</span></a>
    <a href="compte.html#fav" class="mn"><i class="fa-regular fa-heart"></i><span>Favoris</span></a>
    <a href="messages.html" class="mn"><i class="fa-regular fa-comment"></i><span>Messages</span></a>
    <a href="${space}" class="mn"><i class="fa-regular fa-user"></i><span>Compte</span></a>
  </div><style>.mn{display:flex;flex-direction:column;align-items:center;gap:3px;font-size:11px;font-weight:600;color:var(--carbon)}.mn i{font-size:17px}</style>`;
}
function toast(msg){ const t=document.createElement('div'); t.className='toast'; t.textContent=msg; document.body.appendChild(t); setTimeout(()=>t.remove(),2600); }
function requireAuth(role){ const u=Session.get(); if(!u){ location.href='connexion.html?next='+encodeURIComponent(location.pathname.split('/').pop()+location.search); return null;} if(role&&u.role!==role&&u.role!=='ADMIN'){ toast('Accès réservé'); setTimeout(()=>location.href='index.html',800); return null;} return u; }

function vehicleCard(v){
  return `<a href="vehicule.html?id=${v.id}" class="card fade-up" style="overflow:hidden;display:block" data-testid="vehicle-card-${v.id}">
    <div style="position:relative"><img class="veh-img" src="${(v.images&&v.images[0])||IMG.sedan}" alt="${v.brand} ${v.model}" loading="lazy">
      <span class="chip" style="position:absolute;top:12px;left:12px">${v.cat}</span>
      <button class="fav-btn" onclick="event.preventDefault();event.stopPropagation();const a=toggleFav('${v.id}');this.innerHTML=a?'<i class=\\'fa-solid fa-heart\\' style=color:var(--red)></i>':'<i class=\\'fa-regular fa-heart\\'></i>'" style="position:absolute;top:10px;right:10px;background:#fff;border:none;width:36px;height:36px;border-radius:50%;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.12)">${isFav(v.id)?'<i class="fa-solid fa-heart" style="color:var(--red)"></i>':'<i class="fa-regular fa-heart"></i>'}</button>
    </div>
    <div style="padding:16px">
      <div style="display:flex;justify-content:space-between;align-items:start"><div><div style="font-family:'Fraunces',serif;font-weight:600;font-size:18px">${v.brand} ${v.model}</div><div style="color:var(--muted);font-size:13px">${v.year} • ${v.city} (${v.dept})</div></div><div style="text-align:right"><div style="font-weight:800;font-size:19px">${v.price} €</div><div style="color:var(--muted);font-size:12px">/ jour</div></div></div>
      <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:12px;color:var(--muted);font-size:13px">
        <span><i class="fa-solid fa-gear"></i> ${v.gear.slice(0,4)}.</span><span><i class="fa-solid fa-gas-pump"></i> ${v.fuel}</span><span><i class="fa-solid fa-user-group"></i> ${v.seats}</span><span><i class="fa-solid fa-road"></i> ${(v.km/1000).toFixed(0)}k km</span>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:14px;padding-top:12px;border-top:1px solid var(--line)">
        <span style="font-weight:700;font-size:14px"><i class="fa-solid fa-star" style="color:var(--amber)"></i> ${(v.rating||0).toFixed(1)} <span style="color:var(--muted);font-weight:500">(${v.reviews||0})</span></span>
        <span class="btn btn-red" style="padding:8px 16px;font-size:14px">Voir</span>
      </div>
    </div></a>`;
}

loadState();
function apiUpload(file){const x=new XMLHttpRequest();const fd=new FormData();fd.append('file',file);try{x.open('POST',API_ROOT+'/upload',false);const t=localStorage.getItem('suc_token');if(t)x.setRequestHeader('Authorization','Bearer '+t);x.send(fd);}catch(e){return{error:'upload'}}let j={};try{j=JSON.parse(x.responseText||'{}')}catch(e){}if(x.status<200||x.status>=300)return{error:j.detail||'upload'};return j;}
document.addEventListener('DOMContentLoaded',()=>{ renderNav(); renderFooter(); renderMobileNav(); });
