export default{async fetch(r,env){const u=new URL(r.url),p=u.pathname;
// knowledge#14243: the installable app's own files are public (Access bypass app "Eagle Eye · app files"), so Chrome's
// WebAPK minter can read them. They are static and carry no data. Every other request must carry Access's signed JWT
// (a Google sign-in or a service token): a bypassed path never reaches the identity logic below.
if(PUB(p))return serve(p);
if(!r.headers.get("cf-access-jwt-assertion"))return new Response("sign in through Cloudflare Access",{status:401});
// who is looking (Cloudflare Access sets the signed-in Google email; a request with none came through a service token)
// knowledge#14268: ONE people map, KV `people` ({"emails":{"<google email>":"<person>"},"admins":[...]}), shared with eagle-eye-api. No inline copy.
const pp=(await kv(env,"people"))||{},PEOPLE=pp.emails||{};
const ALL=peopleList(pp),em=(r.headers.get("cf-access-authenticated-user-email")||"").toLowerCase();
const as=!em&&ALL.includes(u.searchParams.get("as"))?u.searchParams.get("as"):null; // a service-token check may view as one person
const me=em?(PEOPLE[em]||null):(as||"tyler"),admin=me==="tyler",may=admin?ALL:(me?[me]:[]);
if(!may.length)return new Response("This Google account has no Eagle Eye yet.",{status:403});
// knowledge#14128: whose Eagle Eye this request shows. `?p=` (a link, or the switcher in /who.js) wins and is remembered
// in cookie ee_p; else the cookie; else the signed-in person. Never a person outside `may`: Osman and Claire only ever see their own.
const ck=((r.headers.get("cookie")||"").match(/(?:^|;\s*)ee_p=([a-z]+)/)||[])[1],qp=u.searchParams.get("p");
const who=may.includes(qp)?qp:may.includes(ck)?ck:me;
const res=await app(await route(r,env,u,p,em,me,admin,may,who));
if(!qp||!may.includes(qp)||qp===ck)return res;
const h=new Headers(res.headers);h.append("set-cookie","ee_p="+qp+"; Path=/; Max-Age=31536000; SameSite=Lax; Secure");
return new Response(res.body,{status:res.status,statusText:res.statusText,headers:h});},
// knowledge#14243: every minute, push each person's NEW replies and bookings to their own installed apps
async scheduled(ev,env,ctx){ctx.waitUntil(notifyAll(env));}}
const peopleList=pp=>[...new Set(Object.values((pp||{}).emails||{}))];
const NAMES={tyler:"Tyler",osman:"Osman",claire:"Claire",yusuf:"Yusuf"};
const J=(b,s)=>new Response(typeof b==="string"?b:JSON.stringify(b),{status:s||200,headers:{"content-type":"application/json","cache-control":"no-store"}});
const H=(b,extra)=>new Response(extra?b.replace("</body>",extra+"\n</body>"):b,{headers:{"content-type":"text/html; charset=utf-8","cache-control":"no-cache"}});
const kv=async(env,k)=>{try{return JSON.parse(await env.DATA.get(k)||"null");}catch(e){return null;}};
// knowledge#14128: a person other than Tyler gets the SAME page, fed only from their own stores: apps/<who> (their apply
// store, apps_feed.py) and p/<who> (their ledger, person_feed.py). A lane they have no store for is an honest empty state.
const HUNTS={upwork:"Upwork proposals",cold_apps:"applications",linkedin:"LinkedIn outreach",cold_email:"cold email",in_person:"in-person events"};
const ROOSTS={clients:"clients",network:"network",social:"social inbox",inbox:"inbox"};
async function personData(env,who){const N=NAMES[who]||who,[a,pp]=await Promise.all([kv(env,"apps/"+who),kv(env,"p/"+who)]);
const hunts={},roosts={};
for(const k in HUNTS)hunts[k]={sent:null,answered:null,status:"empty",reason:"no "+HUNTS[k]+" for "+N+" yet",candidate:who};
for(const k in ROOSTS)roosts[k]={rows:[],status:"empty",reason:"no "+ROOSTS[k]+" for "+N+" yet",candidate:who};
if(a&&Array.isArray(a.apps)){const t=a.totals||{},resp=((a.traction||{}).responded||[]).length;
const last=a.apps.reduce((m,x)=>x.at&&(!m||x.at>m.at)?x:m,null);
hunts.cold_apps={sent:t.applied_24h||0,answered:t.answers_24h||0,window:"last 24 h",sent_all:t.applied_all!=null?t.applied_all:a.apps.length,answered_all:resp,window_all:"all time",
what:"applications submitted in "+N+"'s name · companies that answered (any stage), last 24 h",source:N+"'s apply store (applications.db, apps_feed.py)",at:a.updated,status:"live",candidate:who};
if(last)hunts.cold_apps.latest={ts:last.at,co:last.co,kind:"application",what:last.role};}
if(pp){for(const k in pp.hunts||{})if(!(k in hunts)||k==="in_person")hunts[k]=Object.assign({candidate:who},pp.hunts[k]); // knowledge#14303: the In Person feed is the person's own
for(const k in pp.roosts||{}){const r=pp.roosts[k];if(r&&k in ROOSTS)roosts[k]=Object.assign({status:(r.rows||[]).length?"live":"empty",candidate:who},r);}}
let s=0,n=0;for(const k in hunts){const h=hunts[k];if(h.sent!=null&&k in HUNTS){s+=h.sent;n+=h.answered||0;}}
return {person:who,candidate:who,updated:(a&&a.updated)||(pp&&pp.updated)||null,proposals_sent:s,proposals_answered:n,contracts:0,paid_events:0,videos_sent:0,hunts,roosts};}
async function personLanes(env,who){const N=NAMES[who]||who,[a,pp]=await Promise.all([kv(env,"apps/"+who),kv(env,"p/"+who)]),lanes={},companies={};
for(const k of [...Object.keys(HUNTS),"clients","network","social"])lanes[k]={events:[],companies:[],source:"no "+(HUNTS[k]||ROOSTS[k])+" for "+N+" yet"};
if(a&&Array.isArray(a.apps)){const now=Date.now(),ev=a.apps.filter(x=>x.at).map(x=>({ts:x.at,kind:"application",what:x.role,co:x.co}));
for(const x of (a.traction||{}).interviews||[])if(x.start)ev.push({ts:x.start,kind:x.status==="cancelled"?"cancelled":"interview",what:[x.stage,x.role].filter(Boolean).join(" · "),co:x.co||x.company,up:Date.parse(x.start)>now?1:0});
for(const x of (a.traction||{}).responded||[])if(x.at&&x.stage!=="interview")ev.push({ts:x.at,kind:x.stage||"answer",what:x.via||"",co:x.co});
for(const x of (a.traction||{}).inbound||[])if(x.at&&x.action)ev.push({ts:x.at,kind:"reply",what:x.snippet||"",co:x.co});
ev.sort((x,y)=>x.ts<y.ts?1:-1);
for(const k in a.companies||{}){const c=a.companies[k];companies[k]={name:c.name,tier:c.tier,apps:c.apps||0,emails:(c.emails||[]).length,replies:(c.replies||[]).length,vsls:0,proposals:0,stage:c.stage,last:c.last,lanes:["cold_apps"]};}
lanes.cold_apps={events:ev.slice(0,600),source:N+"'s apply store (applications.db, apps_feed.py)",companies:Object.keys(companies)};}
const L=pp&&pp.lanes||{};for(const k in L)if(k in lanes&&(L[k].events||[]).length)lanes[k]=Object.assign({companies:[]},L[k]); // In Person events, knowledge#14303
return {person:who,updated:(a&&a.updated)||null,event_days:7,companies,lanes,facts:(pp&&pp.facts)||null,tiers:(a&&a.tiers)||[],tier_source:((a&&a.sources)||{}).tiers||"no tier list for "+N+" yet"};}
async function route(r,env,u,p,em,me,admin,may,who){
if(p.startsWith("/push/"))return pushRoute(r,env,p,me);
// knowledge#14599: Tyler approves (or edits, then approves) a campaign's referral copy on the applied job's panel. Only his
// own Google sign-in counts, never a service token (em is empty for those, and `me` would default to tyler). The
// approval goes to KV approve/<id>; horus's campaign-approvals-pull timer on novaserver writes it where every send path reads it.
if(p==="/campaign/approve")return approveRoute(r,env,em,me);
if(p==="/triage/pick")return triagePick(r,env,em,me); // knowledge#18050: the FULL / INTRO buttons of /hunt/upwork/jobs
if(admin&&p==="/triage-picks.json"){const o={},l=await env.DATA.list({prefix:"triage/"});for(const k of l.keys){const v=await kv(env,k.name);if(v&&v.key)o[v.key]=v;}return J(o);}
if(p==="/me.json")return J({me,view:who,people:may,names:NAMES,email:em||null});
if(p==="/apps.json"){const q=u.searchParams.get("p");if(q&&!may.includes(q))return J({reason:"not yours"},403);const w=q||who;
const d=await env.DATA.get(w==="tyler"?"apps":"apps/"+w);return d?J(d):J({reason:"no applications feed for "+w+" yet"});}
if(!admin){ // Osman or Claire: their own home, hunts, roosts and applications; Tyler's desks, feeds and pages stay his
const own=p==="/p/"+me||p.startsWith("/p/"+me+"/")||p==="/p/eagle-eye.js"; // their own person page (Claire's /p/claire)
const mine=own||p==="/"||p==="/home-v2.js"||p==="/who.js"||p==="/pwa.js"||p==="/data.json"||p==="/lanes.json"||p==="/applications"||p==="/lane/cold-applications"||/^\/(hunt|roost)\/[a-z_-]+\/?$/.test(p);
if(!mine)return /\.(json|js)$/.test(p)||/^\/(go|view|desk|p)\//.test(p)?new Response("not yours",{status:403}):Response.redirect(u.origin+"/",302);}
if(who!=="tyler"){ // Tyler looking through the switcher at someone else's Eagle Eye, or that person themselves
if(p==="/data.json")return J(await personData(env,who));
if(p==="/lanes.json")return J(await personLanes(env,who));
if(p==="/upwork.json"||p==="/cold-apps.json"||p==="/pipelines.json")return J({reason:"no such feed for "+(NAMES[who]||who)+" yet"},404);}
if(p==="/data.json"){let d={};try{d=JSON.parse(await env.DATA.get("data")||"{}");const a=JSON.parse(await env.DATA.get("apps")||"{}");const h24=a.hunts_24h||{};
for(const k in h24){const h=d.hunts&&d.hunts[k];if(!h)continue;h.sent_all=h.sent;h.answered_all=h.answered;h.window_all=h.window;Object.assign(h,h24[k]);if(h.sent!==null)h.status=h.status==="empty"?"live":h.status;delete h.reason;}
if(h24.upwork){d.proposals_sent=h24.upwork.sent;d.proposals_answered=h24.upwork.answered;}}catch(e){}
// knowledge#14038: the Upwork hunt reads the upwork agent's own stores (KV `upwork`, upwork_feed.py on Nova every 5 min)
try{const w=JSON.parse(await env.DATA.get("upwork")||"null"),h=d.hunts&&d.hunts.upwork;if(w&&w.h24&&h){h.sent=w.h24.sent;h.answered=w.h24.answered;h.window="last 24 h";h.at=w.computedAt;h.status="live";h.source="upwork ledger + proposals.db (upwork_feed.py)";
const ev=[...(w.proposals||[]).map(x=>({ts:x.sentAt,co:x.title,kind:"proposal sent",what:x.title})),...(w.replies||[]).filter(x=>!x.mail).map(x=>({ts:x.ts,co:x.client,kind:"client reply",what:x.what}))].filter(x=>x.ts).sort((a,b)=>a.ts<b.ts?1:-1);
if(ev[0])h.latest=ev[0];d.proposals_sent=h.sent;d.proposals_answered=h.answered;}}catch(e){}return J(d);}
if(p==="/pipelines.json"){const d=await env.DATA.get("pipelines");return d?J(d):J({reason:"no pipelines feed yet"},404);}
if(p==="/upwork.json"){const d=await env.DATA.get("upwork");return d?J(d):J({reason:"no upwork feed yet"},404);}
const WHO='<script src="/who.js" defer></script>';
if(p==="/"){const b=A["/"];if(b!==undefined)return H(b,(who==="tyler"?'<script src="/upwork-badge.js" defer></script>\n':"")+WHO);}
if(p==="/cold-apps.json"||p==="/lanes.json"){const d=await env.DATA.get(p==="/lanes.json"?"lanes":"cold-apps")||"{}";return J(d);}
if(/^\/(go|view|desk)\//.test(p)){const o=await fetch("https://desks.utopiamodels.ai"+p+u.search,{headers:{"CF-Access-Client-Id":env.DESK_ID,"CF-Access-Client-Secret":env.DESK_SECRET},redirect:"manual"});
const h=new Headers(o.headers);h.delete("set-cookie");h.set("cache-control","no-store");return new Response(o.body,{status:o.status,headers:h});}
if(p==="/campaigns"||p==="/campaigns/"){const b=A["/campaigns.html"];if(b===undefined)return new Response("not found",{status:404});return H(b,WHO);}
if(p==="/hunt/cold_apps"||p==="/hunt/cold_apps/"||p==="/lane/cold-applications"||p==="/applications")return H(A["/apps.html"]);
if(/^\/(hunt|roost)\/[a-z_-]+\/?$/.test(p)){const b=A["/lane.html"];if(b===undefined)return new Response("not found",{status:404});return H(b,WHO);}
const pm=p.match(/^\/p\/([a-z0-9-]+)(\/.*)?$/);
if(pm){const w=pm[1],rest=pm[2]||"";
// knowledge#14303: Claire's and Osman's Eagle Eye is the home page fed from their own apply stores (personData/personLanes);
// the old /p/claire and /p/osman pages read a ledger Sheet that never saw a submit (0 sent beside 4 and 33 applied). Their links land on the home.
if((w==="claire"||w==="osman")&&(rest===""||rest==="/"))return Response.redirect(u.origin+"/?p="+w,302);
if(rest==="/data.json"){const d=await env.DATA.get("p/"+w);if(!d)return new Response("no feed for this person yet",{status:404});return J(d);}
const k=rest==="/eagle-eye.js"?"/p/eagle-eye.js":(rest===""||rest==="/")?"/p/"+w:null;
const b=k&&A[k];if(!b)return new Response("not found",{status:404});
return new Response(b,{headers:{"content-type":T[k]+"; charset=utf-8","cache-control":"no-cache"}});}
return serve(p);}
// ── knowledge#14243: the installable Android app (PWA → Chrome WebAPK) and its push alerts ──
const PUB=p=>p==="/manifest.webmanifest"||p==="/sw.js"||p==="/favicon.ico"||p==="/favicon.svg"||/^\/logo-[a-z-]+\.svg$/.test(p)||/^\/icons\/[a-z0-9-]+\.png$/.test(p);
function serve(p){const b=A[p];if(b===undefined)return new Response("not found",{status:404});const t=T[p]||"text/plain";
if(t==="image/png"){const bin=Uint8Array.from(atob(b),c=>c.charCodeAt(0));return new Response(bin,{headers:{"content-type":t,"cache-control":"public, max-age=86400"}});}
return new Response(b,{headers:{"content-type":t+"; charset=utf-8","cache-control":"no-cache"}});}
// every HTML page gets the manifest, theme colour, icons and /pwa.js (service worker + the alerts button)
const HEAD='<link rel="manifest" href="/manifest.webmanifest" crossorigin="use-credentials"><meta name="theme-color" content="#0a0a09">'
+'<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="icon" href="/icons/icon-192.png" sizes="192x192" type="image/png">'
+'<link rel="apple-touch-icon" href="/icons/icon-192.png"><script src="/pwa.js" defer></script>';
async function app(res){const ct=res.headers.get("content-type")||"";if(!ct.startsWith("text/html")||res.status!==200)return res;
const b=await res.text();if(b.includes('rel="manifest"')||!b.includes("</head>"))return new Response(b,res);
return new Response(b.replace("</head>",HEAD+"</head>"),{status:res.status,statusText:res.statusText,headers:res.headers});}

// Web Push (RFC 8030 + 8291 aes128gcm + 8292 VAPID) on WebCrypto. Keys: Worker secrets VAPID_JWK / VAPID_PUBLIC
// (Infisical fleet-infra EAGLE_VAPID_PRIVATE_JWK / EAGLE_VAPID_PUBLIC_KEY). Subscriptions: KV push/subs/<person>.
const te=new TextEncoder();
const b64u=a=>{let s="";for(const c of new Uint8Array(a))s+=String.fromCharCode(c);return btoa(s).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");};
const ub64=s=>{s=s.replace(/-/g,"+").replace(/_/g,"/");while(s.length%4)s+="=";return Uint8Array.from(atob(s),c=>c.charCodeAt(0));};
const cat=(...a)=>{const o=new Uint8Array(a.reduce((n,x)=>n+x.length,0));let i=0;for(const x of a){o.set(x,i);i+=x.length;}return o;};
const hkdf=async(salt,ikm,info,len)=>new Uint8Array(await crypto.subtle.deriveBits({name:"HKDF",hash:"SHA-256",salt,info},
  await crypto.subtle.importKey("raw",ikm,"HKDF",false,["deriveBits"]),len*8));
async function webpush(env,sub,payload){
const ep=new URL(sub.endpoint),sk=await crypto.subtle.importKey("jwk",JSON.parse(env.VAPID_JWK),{name:"ECDSA",namedCurve:"P-256"},false,["sign"]);
const jh=b64u(te.encode(JSON.stringify({typ:"JWT",alg:"ES256"}))),jc=b64u(te.encode(JSON.stringify({aud:ep.origin,exp:Math.floor(Date.now()/1000)+43200,sub:"mailto:tyler@utopiamodels.ai"})));
const jwt=jh+"."+jc+"."+b64u(await crypto.subtle.sign({name:"ECDSA",hash:"SHA-256"},sk,te.encode(jh+"."+jc)));
const ua=ub64(sub.keys.p256dh),auth=ub64(sub.keys.auth);
const as=await crypto.subtle.generateKey({name:"ECDH",namedCurve:"P-256"},true,["deriveBits"]);
const asPub=new Uint8Array(await crypto.subtle.exportKey("raw",as.publicKey));
const secret=new Uint8Array(await crypto.subtle.deriveBits({name:"ECDH",public:await crypto.subtle.importKey("raw",ua,{name:"ECDH",namedCurve:"P-256"},false,[])},as.privateKey,256));
const ikm=await hkdf(auth,secret,cat(te.encode("WebPush: info\x00"),ua,asPub),32),salt=crypto.getRandomValues(new Uint8Array(16));
const cek=await hkdf(salt,ikm,te.encode("Content-Encoding: aes128gcm\x00"),16),nonce=await hkdf(salt,ikm,te.encode("Content-Encoding: nonce\x00"),12);
const ct=new Uint8Array(await crypto.subtle.encrypt({name:"AES-GCM",iv:nonce},await crypto.subtle.importKey("raw",cek,"AES-GCM",false,["encrypt"]),cat(te.encode(payload),new Uint8Array([2]))));
const hdr=new Uint8Array(21);hdr.set(salt,0);new DataView(hdr.buffer).setUint32(16,4096);hdr[20]=65;
return fetch(sub.endpoint,{method:"POST",body:cat(hdr,asPub,ct),headers:{Authorization:"vapid t="+jwt+", k="+env.VAPID_PUBLIC,
"Content-Encoding":"aes128gcm","Content-Type":"application/octet-stream",TTL:"86400",Urgency:"high"}});}
// send one alert to every app this person installed; a 404/410 subscription is gone and is dropped
// knowledge#14268: the store app's push. Devices register through eagle-eye-api (/v1/push/register) into KV push/app/<person>
// [{token,platform,kind}]. FCM HTTP v1 (project driven-rider-500720-i0) carries Android directly; an iPhone's raw APNs token is
// exchanged for an FCM token (iid batchImport) and sent through FCM's APNs bridge (needs the APNs auth key uploaded in Firebase).
// Worker secret FCM_SA = the fleet service account JSON (Infisical fleet-infra GOOGLE_SA_JSON_B64, decoded).
const FCM_PROJECT="driven-rider-500720-i0",APP_ID="sh.eagleeye.app";
let fcmTok=null;
async function fcmToken(env){if(fcmTok&&fcmTok.exp>Date.now()+60e3)return fcmTok.t;
const sa=JSON.parse(env.FCM_SA),now=Math.floor(Date.now()/1000);
const h=b64u(te.encode(JSON.stringify({alg:"RS256",typ:"JWT"}))),c=b64u(te.encode(JSON.stringify({iss:sa.client_email,scope:"https://www.googleapis.com/auth/firebase.messaging",aud:"https://oauth2.googleapis.com/token",iat:now,exp:now+3600})));
const der=ub64(sa.private_key.replace(/-----[A-Z ]+-----/g,"").replace(/\s+/g,"")),k=await crypto.subtle.importKey("pkcs8",der,{name:"RSASSA-PKCS1-v1_5",hash:"SHA-256"},false,["sign"]);
const jwt=h+"."+c+"."+b64u(await crypto.subtle.sign("RSASSA-PKCS1-v1_5",k,te.encode(h+"."+c)));
const r=await fetch("https://oauth2.googleapis.com/token",{method:"POST",headers:{"content-type":"application/x-www-form-urlencoded"},body:"grant_type="+encodeURIComponent("urn:ietf:params:oauth:grant-type:jwt-bearer")+"&assertion="+jwt});
const j=await r.json();if(!j.access_token)throw new Error("fcm token: "+JSON.stringify(j).slice(0,200));
fcmTok={t:j.access_token,exp:Date.now()+(j.expires_in||3600)*1e3};return fcmTok.t;}
// an iPhone registers its APNs token; FCM wants its own registration token for it. Returns "" when Firebase has no APNs key yet.
async function fcmFromApns(env,d){if(d.fcm)return d.fcm;
const r=await fetch("https://iid.googleapis.com/iid/v1:batchImport",{method:"POST",headers:{Authorization:"Bearer "+await fcmToken(env),"content-type":"application/json",access_token_auth:"true"},
body:JSON.stringify({application:APP_ID,sandbox:!!d.sandbox,apns_tokens:[d.token]})});
const x=(((await r.json()).results)||[])[0]||{};return x.status==="OK"?x.registration_token:"";}
async function fcmSend(env,d,msg){const tok=d.platform==="ios"&&d.kind!=="fcm"?await fcmFromApns(env,d):d.token;if(!tok)return {st:-2};if(d.platform==="ios"&&d.kind!=="fcm")d.fcm=tok;
const r=await fetch("https://fcm.googleapis.com/v1/projects/"+FCM_PROJECT+"/messages:send",{method:"POST",
headers:{Authorization:"Bearer "+await fcmToken(env),"content-type":"application/json"},
body:JSON.stringify({message:{token:tok,notification:{title:msg.title||"Eagle Eye",body:msg.body||""},data:{url:String(msg.app||msg.url||"/"),tag:String(msg.tag||"")},
android:{priority:"HIGH",collapse_key:msg.tag||undefined,notification:{tag:msg.tag||undefined,channel_id:"alerts"}},
apns:{headers:{"apns-priority":"10","apns-collapse-id":(msg.tag||"").slice(0,64)||undefined},payload:{aps:{sound:"default"}}}}})});
return {st:r.status};}
// send one alert to every app this person installed (browser PWA via Web Push, store app via FCM); a 404/410 target is gone and dropped
async function pushTo(env,who,msg){const subs=(await kv(env,"push/subs/"+who))||[],keep=[],out=[];
for(const s of subs){let st=0;try{st=(await webpush(env,s,JSON.stringify(msg))).status;}catch(e){st=-1;}out.push(st);if(st!==404&&st!==410)keep.push(s);}
if(keep.length!==subs.length)await env.DATA.put("push/subs/"+who,JSON.stringify(keep));
const devs=(await kv(env,"push/app/"+who))||[],dk=[];let dirty=false;
if(devs.length&&env.FCM_SA)for(const d of devs){let st=0;try{const r=await fcmSend(env,d,msg);st=r.st;if(d.fcm&&!d.fcmSaved){d.fcmSaved=1;dirty=true;}}catch(e){st=-1;console.log("fcm "+who+": "+e);}
out.push("app:"+st);if(st!==404)dk.push(d);else dirty=true;} // FCM answers 404 UNREGISTERED for a removed install
if(dirty)await env.DATA.put("push/app/"+who,JSON.stringify(dk));return out;}
async function pushRoute(r,env,p,me){
if(p==="/push/key")return new Response(env.VAPID_PUBLIC||"",{headers:{"content-type":"text/plain","cache-control":"no-store"}});
if(r.method!=="POST")return J({reason:"POST only"},405);
const k="push/subs/"+me,subs=(await kv(env,k))||[];
if(p==="/push/subscribe"){let s;try{s=await r.json();}catch(e){s=null;}
if(!s||!/^https:\/\//.test(s.endpoint||"")||!s.keys||!s.keys.p256dh||!s.keys.auth)return J({reason:"not a push subscription"},400);
const next=[{endpoint:s.endpoint,keys:{p256dh:s.keys.p256dh,auth:s.keys.auth},at:new Date().toISOString(),ua:(r.headers.get("user-agent")||"").slice(0,120)},...subs.filter(x=>x.endpoint!==s.endpoint)].slice(0,10);
await env.DATA.put(k,JSON.stringify(next));return J({ok:true,person:me,apps:next.length});}
if(p==="/push/unsubscribe"){let s={};try{s=await r.json();}catch(e){}await env.DATA.put(k,JSON.stringify(subs.filter(x=>x.endpoint!==s.endpoint)));return J({ok:true});}
if(p==="/push/test"){const st=await pushTo(env,me,{title:"Eagle Eye",body:"Alerts are on: replies and booked calls land here.",url:me==="tyler"?"/":"/p/"+me,tag:"test"});return J({person:me,apps:subs.length,status:st});}
return J({reason:"no such push route"},404);}

// What alerts (Tyler, card 2026-11-16): a company or client reply, and a booked interview or call. Applications,
// proposals, rejections and our own sends stay silent. Each person's events come only from their own stores.
const REPLY={client_reply:"Client reply",reply:"Reply",screen:"Screen",assessment:"Assessment",offer:"Offer",hired:"Hired",answer:"Reply"};
const BOOK={interview:"Interview booked",call_booked:"Call booked"};
async function personEvents(env,who){const out=[],L=(who==="tyler"?(await kv(env,"lanes"))||{}:await personLanes(env,who)).lanes||{};
for(const k in L)for(const e of L[k].events||[])if(e.ts&&(REPLY[e.kind]||BOOK[e.kind]))out.push({ts:e.ts,kind:e.kind,co:e.co||"",what:e.what||"",lane:k});
const a=await kv(env,who==="tyler"?"apps":"apps/"+who);
for(const x of ((a||{}).traction||{}).inbound||[])if(x.at&&x.action&&who!=="tyler")out.push({ts:x.at,kind:"reply",co:x.co||"",what:x.snippet||"",lane:"clients"}); // knowledge#14304: a reply to their own mailbox
for(const x of ((a||{}).traction||{}).interviews||[])if(x.start&&x.status==="scheduled")out.push({ts:x.start,kind:"interview",co:x.co||x.company||"",what:[x.stage,x.role].filter(Boolean).join(" · "),lane:"cold_apps"});
return out;}
async function notifyAll(env){const now=Date.now();
for(const who of peopleList(await kv(env,"people"))){try{
const evs=await personEvents(env,who),seenK="push/seen/"+who,prev=await kv(env,seenK),seen=new Set(prev||[]),fresh=[];
for(const e of evs){const id=e.kind+"|"+e.co+"|"+e.ts;if(seen.has(id))continue;seen.add(id);
const t=Date.parse(e.ts);if(prev&&(t>now-72*3600e3||(BOOK[e.kind]&&t>now)))fresh.push(e);} // first run seeds silently
if(!prev||fresh.length)await env.DATA.put(seenK,JSON.stringify([...seen].slice(-3000)));
for(const e of fresh.slice(0,5)){const lane=(e.lane in ROOSTS?"/roost/":"/hunt/")+e.lane;
await pushTo(env,who,{title:(REPLY[e.kind]||BOOK[e.kind])+(e.co?" · "+e.co:""),body:(e.what||"").slice(0,160),
url:who==="tyler"?lane:"/p/"+who,app:"/p/"+who+"/lane/"+e.lane,tag:e.kind+"|"+e.co});}}catch(e){console.log("notify "+who+": "+e);}}}
async function triagePick(r,env,em,me){if(r.method!=="POST")return J({reason:"POST only"},405);
if(!em||me!=="tyler")return J({reason:"only Tyler's own sign-in picks a take"},403);
let b={};try{b=await r.json();}catch(e){return J({reason:"bad JSON"},400);}
const key=String(b.key||""),take=String(b.take||"");if(!/^~0\d{17,}$/.test(key))return J({reason:"bad job key"},400);if(take!=="full"&&take!=="intro")return J({reason:"take is full or intro"},400);
const v={key,take,by:"button",at:new Date().toISOString().replace(/\.\d+Z$/,"Z")};await env.DATA.put("triage/"+key,JSON.stringify(v));return J({ok:true,...v});}
async function approveRoute(r,env,em,me){if(r.method!=="POST")return J({reason:"POST only"},405);
if(!em||me!=="tyler")return J({reason:"only Tyler's own sign-in approves campaign copy"},403);
let b={};try{b=await r.json();}catch(e){return J({reason:"bad JSON"},400);}
const id=String(b.id||"");if(!/^[a-z0-9][a-z0-9-]{0,120}$/.test(id))return J({reason:"bad campaign id"},400);
const items=(Array.isArray(b.items)?b.items:[]).slice(0,50).map(i=>({channel:String(i.channel||"").slice(0,20),to:String(i.to||"").slice(0,120),
name:String(i.name||"").slice(0,80),text:String(i.text||"").slice(0,2000),edited:!!i.edited})).filter(i=>i.text.trim()&&i.channel&&i.to);
if(!items.length)return J({reason:"no items"},400);
const k="approve/"+id,prev=await kv(env,k),keep={};for(const i of [...((prev&&prev.items)||[]),...items])keep[i.channel+"|"+i.to]=i;
await env.DATA.put(k,JSON.stringify({id,by:"tyler",via:"eagle-eye",at:new Date().toISOString(),items:Object.values(keep)}));
return J({ok:true,id,items:items.length});}
