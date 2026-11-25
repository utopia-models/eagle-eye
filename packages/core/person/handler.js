export default{async fetch(r,env){const p=new URL(r.url).pathname;
if(p==="/data.json"||p==="/cold-apps.json"||p==="/lanes.json"){const k=p==="/data.json"?"data":p==="/lanes.json"?"lanes":"cold-apps";const d=await env.DATA.get(k)||"{}";return new Response(d,{headers:{"content-type":"application/json","cache-control":"no-store"}});}
if(/^\/(hunt|roost)\/[a-z_-]+\/?$/.test(p)){const b=A["/lane.html"];if(b===undefined)return new Response("not found",{status:404});return new Response(b,{headers:{"content-type":"text/html; charset=utf-8","cache-control":"no-cache"}});}
const pm=p.match(/^\/p\/([a-z0-9-]+)(\/.*)?$/);
if(pm){const who=pm[1],rest=pm[2]||"";
if(rest==="/data.json"){const d=await env.DATA.get("p/"+who);if(!d)return new Response("no feed for this person yet",{status:404});return new Response(d,{headers:{"content-type":"application/json","cache-control":"no-store"}});}
const k=rest==="/eagle-eye.js"?"/p/eagle-eye.js":(rest===""||rest==="/")?"/p/"+who:null;
const b=k&&A[k];if(!b)return new Response("not found",{status:404});
return new Response(b,{headers:{"content-type":T[k]+"; charset=utf-8","cache-control":"no-cache"}});}
const b=A[p];if(b===undefined)return new Response("not found",{status:404});
return new Response(b,{headers:{"content-type":T[p]+"; charset=utf-8","cache-control":"no-cache"}});}}
