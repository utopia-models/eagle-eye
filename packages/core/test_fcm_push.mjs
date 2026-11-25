// knowledge#14268: offline test of the FCM transport in handler-dev.js (mock fetch + KV). Run: node test_fcm_push.mjs
import fs from "node:fs";import {generateKeyPairSync} from "node:crypto";
let src=fs.readFileSync(new URL("./handler-dev.js",import.meta.url),"utf8").replace("export default{","const __h={")+"\nglobalThis.__t={pushTo,notifyAll,personEvents};globalThis.__h=__h;";
fs.writeFileSync("/tmp/h14268-t.mjs","const A={},T={};\n"+src);
const calls=[],kvs={"people":JSON.stringify({emails:{"a@x.example":"tyler","c@x.example":"claire"}}),
"push/app/claire":JSON.stringify([{token:"AND",platform:"android",kind:"fcm"},{token:"DEAD",platform:"android",kind:"fcm"},{token:"APNS",platform:"ios",kind:"apns"}])};
globalThis.fetch=async(u,o)=>{u=String(u);calls.push([u,o&&o.body]);
if(u.includes("oauth2"))return new Response(JSON.stringify({access_token:"AT",expires_in:3600}));
if(u.includes("iid"))return new Response(JSON.stringify({results:[{status:"OK",registration_token:"CONV"}]}));
const m=JSON.parse(o.body).message;return new Response("{}",{status:m.token==="DEAD"?404:200});};
const {privateKey}=generateKeyPairSync("rsa",{modulusLength:2048});
const env={DATA:{get:async k=>kvs[k]??null,put:async(k,v)=>{kvs[k]=v;}},FCM_SA:JSON.stringify({client_email:"sa@p.example",private_key:privateKey.export({type:"pkcs8",format:"pem"})})};
await import("/tmp/h14268-t.mjs");
const out=await __t.pushTo(env,"claire",{title:"Reply · Acme",body:"hi",url:"/p/sam",tag:"reply|Acme"});
const sends=calls.filter(c=>c[0].includes("messages:send")).map(c=>JSON.parse(c[1]).message);
const ok=(c,m)=>{if(!c){console.log("FAIL "+m);process.exit(1);}};
ok(JSON.stringify(out)==='["app:200","app:404","app:200"]',"statuses "+JSON.stringify(out));
ok(sends.map(s=>s.token).join()==="AND,DEAD,CONV","tokens "+sends.map(s=>s.token));
ok(sends[0].data.url==="/p/sam"&&sends[0].notification.title==="Reply · Acme","payload");
ok(JSON.parse(kvs["push/app/claire"]).map(d=>d.token).join()==="AND,APNS","dead token dropped");
ok(calls.filter(c=>c[0].includes("oauth2")).length===1,"one token mint");
console.log("PASS");
