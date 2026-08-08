/* SWIPEUPCAR - moteur client (localStorage). Démo fonctionnelle de bout en bout. */
const DB_KEY='suc_db_v1';
const money=n=>Number(n).toLocaleString('fr-FR')+' €';
const uid=p=>p+Math.random().toString(36).slice(2,8).toUpperCase();
const todayISO=()=>new Date().toISOString().slice(0,10);
const addDays=(d,n)=>{const x=new Date(d);x.setDate(x.getDate()+n);return x.toISOString().slice(0,10)};
const daysBetween=(a,b)=>Math.max(1,Math.round((new Date(b)-new Date(a))/864e5));
const COMMISSION=0.05;

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

const SEED_VEHICLES=[
  {id:'V001',owner:'L001',brand:'BMW',model:'Série 5',year:2022,cat:'Berline',km:28000,power:190,fuel:'Diesel',gear:'Automatique',seats:5,doors:5,color:'Noir',price:120,priceWe:220,priceWeek:700,city:'Paris',dept:'75',rating:4.9,reviews:42,status:'approved',deposit:1500,minAge:23,mileageInc:200,features:['GPS','CarPlay','Caméra','Climatisation'],images:[IMG.sedan,IMG.aston],desc:"Berline premium idéale pour vos déplacements pro et week-ends."},
  {id:'V002',owner:'L001',brand:'Renault',model:'Clio',year:2023,cat:'Citadine',km:12000,power:90,fuel:'Essence',gear:'Manuelle',seats:5,doors:5,color:'Gris',price:39,priceWe:70,priceWeek:230,city:'Lyon',dept:'69',rating:4.7,reviews:63,status:'approved',deposit:600,minAge:19,mileageInc:250,features:['CarPlay','Android Auto','Climatisation'],images:[IMG.crv],desc:"Citadine économique, parfaite pour la ville."},
  {id:'V003',owner:'L002',brand:'Tesla',model:'Model 3',year:2023,cat:'Premium',km:15000,power:283,fuel:'Électrique',gear:'Automatique',seats:5,doors:5,color:'Blanc',price:99,priceWe:180,priceWeek:600,city:'Bordeaux',dept:'33',rating:4.95,reviews:31,status:'approved',deposit:2000,minAge:23,mileageInc:300,features:['GPS','Caméra','Toit panoramique','CarPlay'],images:[IMG.sedan],desc:"100% électrique, technologie de pointe, silence absolu."},
  {id:'V004',owner:'L002',brand:'Peugeot',model:'3008',year:2021,cat:'SUV',km:41000,power:130,fuel:'Diesel',gear:'Automatique',seats:5,doors:5,color:'Bleu',price:75,priceWe:135,priceWeek:450,city:'Marseille',dept:'13',rating:4.6,reviews:28,status:'approved',deposit:1000,minAge:21,mileageInc:250,features:['GPS','Caméra','Climatisation','Siège bébé'],images:[IMG.rav4,IMG.hyundai],desc:"SUV familial confortable et spacieux."},
  {id:'V005',owner:'L001',brand:'Porsche',model:'911',year:2022,cat:'Sportive',km:9000,power:450,fuel:'Essence',gear:'Automatique',seats:2,doors:2,color:'Rouge',price:390,priceWe:720,priceWeek:2400,city:'Nice',dept:'06',rating:5.0,reviews:12,status:'approved',deposit:5000,minAge:28,mileageInc:150,features:['GPS','CarPlay','Caméra'],images:[IMG.ferrari,IMG.orange],desc:"L'expérience sportive ultime pour un week-end d'exception."},
  {id:'V006',owner:'L002',brand:'Volkswagen',model:'Transporter',year:2020,cat:'Utilitaire',km:88000,power:150,fuel:'Diesel',gear:'Manuelle',seats:3,doors:4,color:'Blanc',price:69,priceWe:120,priceWeek:400,city:'Lille',dept:'59',rating:4.4,reviews:19,status:'approved',deposit:900,minAge:23,mileageInc:300,features:['Climatisation','GPS'],images:[IMG.crv],desc:"Utilitaire pour vos déménagements et livraisons."},
  {id:'V007',owner:'L001',brand:'Audi',model:'Q5',year:2023,cat:'SUV',km:18000,power:204,fuel:'Hybride',gear:'Automatique',seats:5,doors:5,color:'Gris',price:110,priceWe:200,priceWeek:650,city:'Toulouse',dept:'31',rating:4.8,reviews:24,status:'approved',deposit:1500,minAge:23,mileageInc:250,features:['GPS','CarPlay','Android Auto','Caméra','Toit panoramique'],images:[IMG.bmwx,IMG.rav4],desc:"SUV hybride élégant, faible consommation."},
  {id:'V008',owner:'L002',brand:'Fiat',model:'500',year:2022,cat:'Citadine',km:22000,power:70,fuel:'Essence',gear:'Manuelle',seats:4,doors:3,color:'Rouge',price:34,priceWe:60,priceWeek:200,city:'Nantes',dept:'44',rating:4.6,reviews:37,status:'approved',deposit:500,minAge:19,mileageInc:250,features:['Climatisation','CarPlay'],images:[IMG.orange],desc:"Petite citadine iconique et fun."},
];
const SEED_USERS=[
  {id:'A001',role:'ADMIN',firstName:'Admin',lastName:'SUC',email:'admin@swipeupcar.fr',password:'admin123',verified:true},
  {id:'L001',role:'LOUEUR',proType:'LOUEUR',firstName:'Thomas',lastName:'Martin',email:'loueur@swipeupcar.fr',password:'loueur123',verified:true,proStatus:'Validé',siret:'81234567800012',company:'Martin Auto Location',rating:4.9,rentals:118,since:'2023',satisfaction:98},
  {id:'L002',role:'LOUEUR',proType:'LOUEUR',firstName:'Sophie',lastName:'Durand',email:'sophie@swipeupcar.fr',password:'loueur123',verified:true,proStatus:'Validé',siret:'75234567800045',company:'Durand Mobilité',rating:4.7,rentals:64,since:'2024',satisfaction:95},
  {id:'U001',role:'PARTICULIER',firstName:'Julie',lastName:'Bernard',email:'client@swipeupcar.fr',password:'client123',verified:true},
];

function seed(){
  if(!localStorage.getItem(DB_KEY)){
    const db={users:SEED_USERS,vehicles:SEED_VEHICLES,bookings:[],favorites:{},reviews:[],conversations:[],notifications:{},settings:{commission:COMMISSION},reports:[]};
    localStorage.setItem(DB_KEY,JSON.stringify(db));
  }
}
const DB={
  get(){seed();return JSON.parse(localStorage.getItem(DB_KEY))},
  set(db){localStorage.setItem(DB_KEY,JSON.stringify(db))},
};
function resetDemo(){localStorage.removeItem(DB_KEY);localStorage.removeItem('suc_session');seed();toast('Données de démo réinitialisées');setTimeout(()=>location.href='index.html',700)}

/* Auth */
const Session={
  get(){const id=localStorage.getItem('suc_session');if(!id)return null;return DB.get().users.find(u=>u.id===id)||null},
  set(id){localStorage.setItem('suc_session',id)},
  clear(){localStorage.removeItem('suc_session')},
};
function login(email,pw){const u=DB.get().users.find(u=>u.email===email&&u.password===pw);if(u){Session.set(u.id);return u}return null}
function register(data){const db=DB.get();if(db.users.find(u=>u.email===data.email))return{err:'Cet email est déjà utilisé.'};const u={id:uid(data.role==='LOUEUR'?'L':'U'),verified:false,...data};db.users.push(u);DB.set(db);Session.set(u.id);return{user:u}}
function logout(){Session.clear();location.href='index.html'}

/* Favorites */
function toggleFav(vid){const u=Session.get();if(!u){toast('Connectez-vous pour ajouter aux favoris');return false}const db=DB.get();db.favorites[u.id]=db.favorites[u.id]||[];const i=db.favorites[u.id].indexOf(vid);let added;if(i>-1){db.favorites[u.id].splice(i,1);added=false}else{db.favorites[u.id].push(vid);added=true}DB.set(db);toast(added?'Ajouté aux favoris ♥':'Retiré des favoris');return added}
function isFav(vid){const u=Session.get();if(!u)return false;const f=DB.get().favorites[u.id]||[];return f.includes(vid)}

/* Notifications */
function notify(userId,text){const db=DB.get();db.notifications[userId]=db.notifications[userId]||[];db.notifications[userId].unshift({id:uid('N'),text,date:new Date().toISOString(),read:false});DB.set(db)}

/* Message filter anti-contournement */
const CONTACT_RE=/(\b0[1-9]([ .-]?\d{2}){4}\b)|(\+33)|([a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,})|(wa\.me|whatsapp|instagram|snap(chat)?|telegram|t\.me|facebook|https?:\/\/|www\.)/i;
function containsContact(t){return CONTACT_RE.test(t)}

/* Booking */
function overlaps(v,from,to){const db=DB.get();return db.bookings.some(b=>b.vehicleId===v&&['confirmed','pending'].includes(b.status)&&!(to<=b.from||from>=b.to))}
function createBooking({vehicleId,from,to}){const db=DB.get();const u=Session.get();const v=db.vehicles.find(x=>x.id===vehicleId);if(!u)return{err:'auth'};if(overlaps(vehicleId,from,to))return{err:'Ces dates ne sont plus disponibles.'};const days=daysBetween(from,to);const total=days*v.price;const commission=Math.round(total*db.settings.commission);const b={id:uid('BK'),ref:'SUC-'+uid(''),userId:u.id,ownerId:v.owner,vehicleId,from,to,days,total,commission,ownerAmount:total-commission,status:'confirmed',createdAt:new Date().toISOString(),paid:true};db.bookings.push(b);DB.set(db);notify(u.id,`Réservation confirmée : ${v.brand} ${v.model} (${b.ref})`);notify(v.owner,`Nouvelle réservation reçue : ${v.brand} ${v.model} — ${money(b.ownerAmount)}`);return{booking:b}}

/* ---------- UI: NAV + FOOTER injection ---------- */
function initials(u){return((u.firstName||'?')[0]+(u.lastName||'')[0]).toUpperCase()}
function renderNav(){
  const u=Session.get();
  let right;
  if(!u){
    right=`<a href="connexion.html" class="nav-link hide-mobile">Se connecter</a><a href="inscription.html" class="btn btn-red" style="padding:9px 18px" data-testid="nav-signup">S'inscrire</a>`;
  }else{
    const space=u.role==='ADMIN'?'admin.html':u.role==='LOUEUR'?'loueur.html':'compte.html';
    const nnotif=(DB.get().notifications[u.id]||[]).filter(n=>!n.read).length;
    right=`<a href="messages.html" class="nav-link hide-mobile" data-testid="nav-messages"><i class="fa-regular fa-comment"></i></a>
    <a href="${space}" class="nav-link hide-mobile" style="position:relative"><i class="fa-regular fa-bell"></i>${nnotif?`<span style="position:absolute;top:-2px;right:-8px;background:var(--red);color:#fff;font-size:10px;border-radius:999px;padding:1px 5px">${nnotif}</span>`:''}</a>
    <a href="${space}" class="chip" data-testid="nav-account"><span style="width:26px;height:26px;border-radius:50%;background:var(--carbon);color:#fff;display:grid;place-items:center;font-size:12px;font-weight:700">${initials(u)}</span>${u.firstName}</a>
    <button class="btn btn-ghost" style="padding:8px 14px" onclick="logout()" data-testid="nav-logout">Quitter</button>`;
  }
  const el=document.getElementById('nav');if(!el)return;
  el.innerHTML=`<div style="position:sticky;top:0;z-index:100;background:rgba(244,237,226,.85);backdrop-filter:blur(12px);border-bottom:1px solid var(--line)">
    <div class="container" style="display:flex;align-items:center;gap:22px;height:66px">
      <a href="index.html" style="display:flex;align-items:center;gap:8px;font-family:'Fraunces',serif;font-weight:700;font-size:22px"><span style="background:var(--red);color:#fff;width:30px;height:30px;border-radius:8px;display:grid;place-items:center;font-size:16px"><i class="fa-solid fa-bolt"></i></span>SWIPEUP<span style="color:var(--red)">CAR</span></a>
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
  const el=document.getElementById('footer');if(!el)return;
  el.innerHTML=`<footer style="background:var(--carbon);color:#EDE6DA;margin-top:60px">
   <div class="container" style="padding:50px 20px;display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:30px">
    <div style="max-width:260px">
      <div style="font-family:'Fraunces',serif;font-size:22px;font-weight:700">SWIPEUP<span style="color:#ff6b6b">CAR</span></div>
      <p style="color:#b8ae9f;font-size:14px;margin-top:10px">La plateforme automobile nouvelle génération. Trouvez, réservez et profitez partout en France.</p>
    </div>
    <div><h4 style="font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:#b8ae9f">Plateforme</h4>
      <a href="location.html" class="foot">Louer une voiture</a><a href="services.html?s=entretien" class="foot">Entretien</a><a href="services.html?s=pneus" class="foot">Pneus</a><a href="services.html?s=pieces" class="foot">Pièces auto</a><a href="services.html?s=lavage" class="foot">Lavage</a></div>
    <div><h4 style="font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:#b8ae9f">Informations</h4>
      <a href="infos.html#how" class="foot">Comment ça marche</a><a href="infos.html#security" class="foot">Sécurité</a><a href="infos.html#faq" class="foot">FAQ</a><a href="infos.html#cgu" class="foot">Conditions</a><a href="infos.html#privacy" class="foot">Confidentialité</a></div>
    <div><h4 style="font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:#b8ae9f">Professionnels</h4>
      <a href="devenir-loueur.html" class="foot">Devenir loueur</a><a href="loueur.html" class="foot">Espace professionnel</a></div>
    <div><h4 style="font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:#b8ae9f">Support</h4>
      <a href="infos.html#faq" class="foot">Centre d'aide</a><a href="infos.html#contact" class="foot">Contact</a><button onclick="resetDemo()" class="foot" style="background:none;border:none;cursor:pointer;text-align:left;padding:0">↻ Réinitialiser la démo</button></div>
   </div>
   <div style="border-top:1px solid #33302b"><div class="container" style="padding:18px 20px;display:flex;flex-wrap:wrap;gap:10px;justify-content:space-between;color:#8a8175;font-size:13px"><span>© 2026 SWIPEUPCAR — Plateforme de mise en relation.</span><a href="infos.html#legal" style="color:#8a8175">Mentions légales</a></div></div>
  </footer>
  <style>.foot{display:block;color:#d7cfc0;font-size:14px;padding:5px 0}.foot:hover{color:#fff}</style>`;
}
function renderMobileNav(){
  const u=Session.get();const space=u?(u.role==='LOUEUR'?'loueur.html':u.role==='ADMIN'?'admin.html':'compte.html'):'connexion.html';
  const el=document.getElementById('mnav');if(!el)return;
  el.innerHTML=`<div class="mobile-nav">
    <a href="index.html" class="mn"><i class="fa-solid fa-house"></i><span>Accueil</span></a>
    <a href="location.html" class="mn"><i class="fa-solid fa-magnifying-glass"></i><span>Chercher</span></a>
    <a href="compte.html#fav" class="mn"><i class="fa-regular fa-heart"></i><span>Favoris</span></a>
    <a href="messages.html" class="mn"><i class="fa-regular fa-comment"></i><span>Messages</span></a>
    <a href="${space}" class="mn"><i class="fa-regular fa-user"></i><span>Compte</span></a>
  </div><style>.mn{display:flex;flex-direction:column;align-items:center;gap:3px;font-size:11px;font-weight:600;color:var(--carbon)}.mn i{font-size:17px}</style>`;
}
function toast(msg){const t=document.createElement('div');t.className='toast';t.textContent=msg;document.body.appendChild(t);setTimeout(()=>t.remove(),2600)}
function requireAuth(role){const u=Session.get();if(!u){location.href='connexion.html?next='+encodeURIComponent(location.pathname.split('/').pop()+location.search);return null}if(role&&u.role!==role&&u.role!=='ADMIN'){toast('Accès réservé');setTimeout(()=>location.href='index.html',800);return null}return u}

/* Vehicle card */
function vehicleCard(v){
  return `<a href="vehicule.html?id=${v.id}" class="card fade-up" style="overflow:hidden;display:block" data-testid="vehicle-card-${v.id}">
    <div style="position:relative"><img class="veh-img" src="${v.images[0]}" alt="${v.brand} ${v.model}" loading="lazy">
      <span class="chip" style="position:absolute;top:12px;left:12px">${v.cat}</span>
      <button class="fav-btn" onclick="event.preventDefault();event.stopPropagation();const a=toggleFav('${v.id}');this.innerHTML=a?'<i class=\\'fa-solid fa-heart\\' style=color:var(--red)></i>':'<i class=\\'fa-regular fa-heart\\'></i>'" style="position:absolute;top:10px;right:10px;background:#fff;border:none;width:36px;height:36px;border-radius:50%;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.12)">${isFav(v.id)?'<i class="fa-solid fa-heart" style="color:var(--red)"></i>':'<i class="fa-regular fa-heart"></i>'}</button>
    </div>
    <div style="padding:16px">
      <div style="display:flex;justify-content:space-between;align-items:start"><div><div style="font-family:'Fraunces',serif;font-weight:600;font-size:18px">${v.brand} ${v.model}</div><div style="color:var(--muted);font-size:13px">${v.year} • ${v.city} (${v.dept})</div></div><div style="text-align:right"><div style="font-weight:800;font-size:19px">${v.price} €</div><div style="color:var(--muted);font-size:12px">/ jour</div></div></div>
      <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:12px;color:var(--muted);font-size:13px">
        <span><i class="fa-solid fa-gear"></i> ${v.gear.slice(0,4)}.</span><span><i class="fa-solid fa-gas-pump"></i> ${v.fuel}</span><span><i class="fa-solid fa-user-group"></i> ${v.seats}</span><span><i class="fa-solid fa-road"></i> ${(v.km/1000).toFixed(0)}k km</span>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:14px;padding-top:12px;border-top:1px solid var(--line)">
        <span style="font-weight:700;font-size:14px"><i class="fa-solid fa-star" style="color:var(--amber)"></i> ${v.rating.toFixed(1)} <span style="color:var(--muted);font-weight:500">(${v.reviews})</span></span>
        <span class="btn btn-red" style="padding:8px 16px;font-size:14px">Voir</span>
      </div>
    </div></a>`;
}
function boot(){seed();renderNav();renderFooter();renderMobileNav();}
document.addEventListener('DOMContentLoaded',boot);
