try{self["workbox:core:6.0.2"]&&_()}catch(t){}const t=(t,...e)=>{let s=t;return e.length>0&&(s+=` :: ${JSON.stringify(e)}`),s};class e extends Error{constructor(e,s){super(t(e,s)),this.name=e,this.details=s}}try{self["workbox:routing:6.0.2"]&&_()}catch(t){}const s=t=>t&&"object"==typeof t?t:{handle:t};class i{constructor(t,e,i="GET"){this.handler=s(e),this.match=t,this.method=i}}class n extends i{constructor(t,e,s){super((({url:e})=>{const s=t.exec(e.href);if(s&&(e.origin===location.origin||0===s.index))return s.slice(1)}),e,s)}}class r{constructor(){this.t=new Map,this.i=new Map}get routes(){return this.t}addFetchListener(){self.addEventListener("fetch",(t=>{const{request:e}=t,s=this.handleRequest({request:e,event:t});s&&t.respondWith(s)}))}addCacheListener(){self.addEventListener("message",(t=>{if(t.data&&"CACHE_URLS"===t.data.type){const{payload:e}=t.data,s=Promise.all(e.urlsToCache.map((e=>{"string"==typeof e&&(e=[e]);const s=new Request(...e);return this.handleRequest({request:s,event:t})})));t.waitUntil(s),t.ports&&t.ports[0]&&s.then((()=>t.ports[0].postMessage(!0)))}}))}handleRequest({request:t,event:e}){const s=new URL(t.url,location.href);if(!s.protocol.startsWith("http"))return;const i=s.origin===location.origin,{params:n,route:r}=this.findMatchingRoute({event:e,request:t,sameOrigin:i,url:s});let a=r&&r.handler;const o=t.method;if(!a&&this.i.has(o)&&(a=this.i.get(o)),!a)return;let c;try{c=a.handle({url:s,request:t,event:e,params:n})}catch(t){c=Promise.reject(t)}return c instanceof Promise&&this.o&&(c=c.catch((i=>this.o.handle({url:s,request:t,event:e})))),c}findMatchingRoute({url:t,sameOrigin:e,request:s,event:i}){const n=this.t.get(s.method)||[];for(const r of n){let n;const a=r.match({url:t,sameOrigin:e,request:s,event:i});if(a)return n=a,(Array.isArray(a)&&0===a.length||a.constructor===Object&&0===Object.keys(a).length||"boolean"==typeof a)&&(n=void 0),{route:r,params:n}}return{}}setDefaultHandler(t,e="GET"){this.i.set(e,s(t))}setCatchHandler(t){this.o=s(t)}registerRoute(t){this.t.has(t.method)||this.t.set(t.method,[]),this.t.get(t.method).push(t)}unregisterRoute(t){if(!this.t.has(t.method))throw new e("unregister-route-but-not-found-with-method",{method:t.method});const s=this.t.get(t.method).indexOf(t);if(!(s>-1))throw new e("unregister-route-route-not-registered");this.t.get(t.method).splice(s,1)}}let a;const o=()=>(a||(a=new r,a.addFetchListener(),a.addCacheListener()),a);const c={googleAnalytics:"googleAnalytics",precache:"precache-v2",prefix:"workbox",runtime:"runtime",suffix:"undefined"!=typeof registration?registration.scope:""},h=t=>[c.prefix,t,c.suffix].filter((t=>t&&t.length>0)).join("-"),u=t=>t||h(c.runtime);function l(t){t.then((()=>{}))}const f=new Set;class w{constructor(t,e,{onupgradeneeded:s,onversionchange:i}={}){this.h=null,this.u=t,this.l=e,this.p=s,this.m=i||(()=>this.close())}get db(){return this.h}async open(){if(!this.h)return this.h=await new Promise(((t,e)=>{let s=!1;setTimeout((()=>{s=!0,e(new Error("The open request was blocked and timed out"))}),this.OPEN_TIMEOUT);const i=indexedDB.open(this.u,this.l);i.onerror=()=>e(i.error),i.onupgradeneeded=t=>{s?(i.transaction.abort(),i.result.close()):"function"==typeof this.p&&this.p(t)},i.onsuccess=()=>{const e=i.result;s?e.close():(e.onversionchange=this.m.bind(this),t(e))}})),this}async getKey(t,e){return(await this.getAllKeys(t,e,1))[0]}async getAll(t,e,s){return await this.getAllMatching(t,{query:e,count:s})}async getAllKeys(t,e,s){return(await this.getAllMatching(t,{query:e,count:s,includeKeys:!0})).map((t=>t.key))}async getAllMatching(t,{index:e,query:s=null,direction:i="next",count:n,includeKeys:r=!1}={}){return await this.transaction([t],"readonly",((a,o)=>{const c=a.objectStore(t),h=e?c.index(e):c,u=[],l=h.openCursor(s,i);l.onsuccess=()=>{const t=l.result;t?(u.push(r?t:t.value),n&&u.length>=n?o(u):t.continue()):o(u)}}))}async transaction(t,e,s){return await this.open(),await new Promise(((i,n)=>{const r=this.h.transaction(t,e);r.onabort=()=>n(r.error),r.oncomplete=()=>i(),s(r,(t=>i(t)))}))}async g(t,e,s,...i){return await this.transaction([e],s,((s,n)=>{const r=s.objectStore(e),a=r[t].apply(r,i);a.onsuccess=()=>n(a.result)}))}close(){this.h&&(this.h.close(),this.h=null)}}w.prototype.OPEN_TIMEOUT=2e3;const d={readonly:["get","count","getKey","getAll","getAllKeys"],readwrite:["add","put","clear","delete"]};for(const[t,e]of Object.entries(d))for(const s of e)s in IDBObjectStore.prototype&&(w.prototype[s]=async function(e,...i){return await this.g(s,e,t,...i)});try{self["workbox:expiration:6.0.2"]&&_()}catch(t){}const p=t=>{const e=new URL(t,location.href);return e.hash="",e.href};class y{constructor(t){this.v=t,this.h=new w("workbox-expiration",1,{onupgradeneeded:t=>this.q(t)})}q(t){const e=t.target.result.createObjectStore("cache-entries",{keyPath:"id"});e.createIndex("cacheName","cacheName",{unique:!1}),e.createIndex("timestamp","timestamp",{unique:!1}),(async t=>{await new Promise(((e,s)=>{const i=indexedDB.deleteDatabase(t);i.onerror=()=>{s(i.error)},i.onblocked=()=>{s(new Error("Delete blocked"))},i.onsuccess=()=>{e()}}))})(this.v)}async setTimestamp(t,e){const s={url:t=p(t),timestamp:e,cacheName:this.v,id:this.R(t)};await this.h.put("cache-entries",s)}async getTimestamp(t){return(await this.h.get("cache-entries",this.R(t))).timestamp}async expireEntries(t,e){const s=await this.h.transaction("cache-entries","readwrite",((s,i)=>{const n=s.objectStore("cache-entries").index("timestamp").openCursor(null,"prev"),r=[];let a=0;n.onsuccess=()=>{const s=n.result;if(s){const i=s.value;i.cacheName===this.v&&(t&&i.timestamp<t||e&&a>=e?r.push(s.value):a++),s.continue()}else i(r)}})),i=[];for(const t of s)await this.h.delete("cache-entries",t.id),i.push(t.url);return i}R(t){return this.v+"|"+p(t)}}class m{constructor(t,e={}){this.D=!1,this._=!1,this.N=e.maxEntries,this.O=e.maxAgeSeconds,this.C=e.matchOptions,this.v=t,this.U=new y(t)}async expireEntries(){if(this.D)return void(this._=!0);this.D=!0;const t=this.O?Date.now()-1e3*this.O:0,e=await this.U.expireEntries(t,this.N),s=await self.caches.open(this.v);for(const t of e)await s.delete(t,this.C);this.D=!1,this._&&(this._=!1,l(this.expireEntries()))}async updateTimestamp(t){await this.U.setTimestamp(t,Date.now())}async isURLExpired(t){if(this.O){return await this.U.getTimestamp(t)<Date.now()-1e3*this.O}return!1}async delete(){this._=!1,await this.U.expireEntries(1/0)}}function g(){return(g=Object.assign||function(t){for(var e=1;e<arguments.length;e++){var s=arguments[e];for(var i in s)Object.prototype.hasOwnProperty.call(s,i)&&(t[i]=s[i])}return t}).apply(this,arguments)}function v(t,e){const s=new URL(t);for(const t of e)s.searchParams.delete(t);return s.href}class q{constructor(){this.promise=new Promise(((t,e)=>{this.resolve=t,this.reject=e}))}}try{self["workbox:strategies:6.0.2"]&&_()}catch(t){}function R(t){return"string"==typeof t?new Request(t):t}class x{constructor(t,e){this.A={},Object.assign(this,e),this.event=e.event,this.k=t,this.P=new q,this.S=[],this.T=[...t.plugins],this.L=new Map;for(const t of this.T)this.L.set(t,{});this.event.waitUntil(this.P.promise)}fetch(t){return this.waitUntil((async()=>{const{event:s}=this;let i=R(t);if("navigate"===i.mode&&s instanceof FetchEvent&&s.preloadResponse){const t=await s.preloadResponse;if(t)return t}const n=this.hasCallback("fetchDidFail")?i.clone():null;try{for(const t of this.iterateCallbacks("requestWillFetch"))i=await t({request:i.clone(),event:s})}catch(t){throw new e("plugin-error-request-will-fetch",{thrownError:t})}const r=i.clone();try{let t;t=await fetch(i,"navigate"===i.mode?void 0:this.k.fetchOptions);for(const e of this.iterateCallbacks("fetchDidSucceed"))t=await e({event:s,request:r,response:t});return t}catch(t){throw n&&await this.runCallbacks("fetchDidFail",{error:t,event:s,originalRequest:n.clone(),request:r.clone()}),t}})())}async fetchAndCachePut(t){const e=await this.fetch(t),s=e.clone();return this.waitUntil(this.cachePut(t,s)),e}cacheMatch(t){return this.waitUntil((async()=>{const e=R(t);let s;const{cacheName:i,matchOptions:n}=this.k,r=await this.getCacheKey(e,"read"),a=g({},n,{cacheName:i});s=await caches.match(r,a);for(const t of this.iterateCallbacks("cachedResponseWillBeUsed"))s=await t({cacheName:i,matchOptions:n,cachedResponse:s,request:r,event:this.event})||void 0;return s})())}async cachePut(t,s){const i=R(t);var n;await(n=0,new Promise((t=>setTimeout(t,n))));const r=await this.getCacheKey(i,"write");if(!s)throw new e("cache-put-with-no-response",{url:(a=r.url,new URL(String(a),location.href).href.replace(new RegExp(`^${location.origin}`),""))});var a;const o=await this.M(s);if(!o)return;const{cacheName:c,matchOptions:h}=this.k,u=await self.caches.open(c),l=this.hasCallback("cacheDidUpdate"),w=l?await async function(t,e,s,i){const n=v(e.url,s);if(e.url===n)return t.match(e,i);const r=g({},i,{ignoreSearch:!0}),a=await t.keys(e,r);for(const e of a)if(n===v(e.url,s))return t.match(e,i)}(u,r.clone(),["__WB_REVISION__"],h):null;try{await u.put(r,l?o.clone():o)}catch(t){throw"QuotaExceededError"===t.name&&await async function(){for(const t of f)await t()}(),t}for(const t of this.iterateCallbacks("cacheDidUpdate"))await t({cacheName:c,oldResponse:w,newResponse:o.clone(),request:r,event:this.event})}async getCacheKey(t,e){if(!this.A[e]){let s=t;for(const t of this.iterateCallbacks("cacheKeyWillBeUsed"))s=R(await t({mode:e,request:s,event:this.event,params:this.params}));this.A[e]=s}return this.A[e]}hasCallback(t){for(const e of this.k.plugins)if(t in e)return!0;return!1}async runCallbacks(t,e){for(const s of this.iterateCallbacks(t))await s(e)}*iterateCallbacks(t){for(const e of this.k.plugins)if("function"==typeof e[t]){const s=this.L.get(e),i=i=>{const n=g({},i,{state:s});return e[t](n)};yield i}}waitUntil(t){return this.S.push(t),t}async doneWaiting(){let t;for(;t=this.S.shift();)await t}destroy(){this.P.resolve()}async M(t){let e=t,s=!1;for(const t of this.iterateCallbacks("cacheWillUpdate"))if(e=await t({request:this.request,response:e,event:this.event})||void 0,s=!0,!e)break;return s||e&&200!==e.status&&(e=void 0),e}}self.skipWaiting(),self.addEventListener("activate",(()=>self.clients.claim())),function(t,s,r){let a;if("string"==typeof t){const e=new URL(t,location.href);a=new i((({url:t})=>t.href===e.href),s,r)}else if(t instanceof RegExp)a=new n(t,s,r);else if("function"==typeof t)a=new i(t,s,r);else{if(!(t instanceof i))throw new e("unsupported-route-type",{moduleName:"workbox-routing",funcName:"registerRoute",paramName:"capture"});a=t}o().registerRoute(a)}(/^.*\/core\/preview\?fileId=.*/,new class extends class{constructor(t={}){this.cacheName=u(t.cacheName),this.plugins=t.plugins||[],this.fetchOptions=t.fetchOptions,this.matchOptions=t.matchOptions}handle(t){const[e]=this.handleAll(t);return e}handleAll(t){t instanceof FetchEvent&&(t={event:t,request:t.request});const e=t.event,s="string"==typeof t.request?new Request(t.request):t.request,i="params"in t?t.params:void 0,n=new x(this,{event:e,request:s,params:i}),r=this.j(n,s,e);return[r,this.K(r,n,s,e)]}async j(t,s,i){let n;await t.runCallbacks("handlerWillStart",{event:i,request:s});try{if(n=await this.W(s,t),!n||"error"===n.type)throw new e("no-response",{url:s.url})}catch(e){for(const r of t.iterateCallbacks("handlerDidError"))if(n=await r({error:e,event:i,request:s}),n)break;if(!n)throw e}for(const e of t.iterateCallbacks("handlerWillRespond"))n=await e({event:i,request:s,response:n});return n}async K(t,e,s,i){let n,r;try{n=await t}catch(r){}try{await e.runCallbacks("handlerDidRespond",{event:i,request:s,response:n}),await e.doneWaiting()}catch(t){r=t}if(await e.runCallbacks("handlerDidComplete",{event:i,request:s,response:n,error:r}),e.destroy(),r)throw r}}{async W(t,s){let i,n=await s.cacheMatch(t);if(!n)try{n=await s.fetchAndCachePut(t)}catch(t){i=t}if(!n)throw new e("no-response",{url:t.url,error:i});return n}}({cacheName:"images",plugins:[new class{constructor(t={}){var e;this.cachedResponseWillBeUsed=async({event:t,request:e,cacheName:s,cachedResponse:i})=>{if(!i)return null;const n=this.F(i),r=this.B(s);l(r.expireEntries());const a=r.updateTimestamp(e.url);if(t)try{t.waitUntil(a)}catch(t){}return n?i:null},this.cacheDidUpdate=async({cacheName:t,request:e})=>{const s=this.B(t);await s.updateTimestamp(e.url),await s.expireEntries()},this.I=t,this.O=t.maxAgeSeconds,this.H=new Map,t.purgeOnQuotaError&&(e=()=>this.deleteCacheAndMetadata(),f.add(e))}B(t){if(t===u())throw new e("expire-custom-caches-only");let s=this.H.get(t);return s||(s=new m(t,this.I),this.H.set(t,s)),s}F(t){if(!this.O)return!0;const e=this.G(t);if(null===e)return!0;return e>=Date.now()-1e3*this.O}G(t){if(!t.headers.has("date"))return null;const e=t.headers.get("date"),s=new Date(e).getTime();return isNaN(s)?null:s}async deleteCacheAndMetadata(){for(const[t,e]of this.H)await self.caches.delete(t),await e.delete();this.H=new Map}}({maxAgeSeconds:604800,maxEntries:1e4,purgeOnQuotaError:!0})]}),"GET");