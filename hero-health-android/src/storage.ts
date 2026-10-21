import {validateState,normalizeState,type HealthState} from './model';
import {nativeAvailable,nativeCall,assertNativeStorage} from './native';
const enc=new TextEncoder(),dec=new TextDecoder('utf-8',{fatal:true});
const base64=(a:Uint8Array)=>{let s='';for(let i=0;i<a.length;i+=8192)s+=String.fromCharCode(...a.subarray(i,i+8192));return btoa(s);};
const unbase64=(s:string)=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
async function derive(password:string,salt:Uint8Array){const raw=await crypto.subtle.importKey('raw',enc.encode(password),'PBKDF2',false,['deriveKey']);return crypto.subtle.deriveKey({name:'PBKDF2',salt:salt as BufferSource,iterations:210000,hash:'SHA-256'},raw,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);}
export async function encryptBackup(state:HealthState,password:string){
 if(password.length<8)throw new Error('密码至少 8 位');
 const safe=structuredClone(state);safe.settings={endpoint:safe.settings.endpoint,model:safe.settings.model,...(safe.settings.summaryPrompt!==undefined?{summaryPrompt:safe.settings.summaryPrompt}:{})};
 for(const r of safe.reports){if(r.file?.id){if(!nativeAvailable())throw new Error('请在原手机中导出包含原件的备份');r.file.dataUrl=await nativeCall<string>('readAttachment',{id:r.file.id});delete r.file.id;}}
 validateState(safe);
 const plain=enc.encode(JSON.stringify(safe));if(plain.byteLength>90*1024*1024)throw new Error('档案超过当前版本90 MB的备份内容上限，请保留原手机资料');
 const salt=crypto.getRandomValues(new Uint8Array(16)),iv=crypto.getRandomValues(new Uint8Array(12)),key=await derive(password,salt);
 const data=await crypto.subtle.encrypt({name:'AES-GCM',iv},key,plain);
 return JSON.stringify({format:'hero-health-backup',version:1,kdf:'PBKDF2-SHA256',iterations:210000,cipher:'AES-256-GCM',salt:base64(salt),iv:base64(iv),data:base64(new Uint8Array(data))});
}
export async function decryptBackup(text:string,password:string):Promise<HealthState>{
 if(text.length>180*1024*1024)throw new Error('备份文件过大');let pack;try{pack=JSON.parse(text);}catch{throw new Error('备份文件无法读取');}
 if(pack.format!=='hero-health-backup'||pack.version!==1||pack.kdf!=='PBKDF2-SHA256'||pack.cipher!=='AES-256-GCM'||pack.iterations!==210000)throw new Error('不支持此备份文件或版本');
 let plain:ArrayBuffer;try{const salt=unbase64(pack.salt),iv=unbase64(pack.iv);if(salt.length!==16||iv.length!==12)throw new Error();const key=await derive(password,salt);plain=await crypto.subtle.decrypt({name:'AES-GCM',iv:iv as BufferSource},key,unbase64(pack.data) as BufferSource);}catch{throw new Error('密码不正确，或备份文件已损坏');}
 let state:unknown;try{state=JSON.parse(dec.decode(plain));}catch{throw new Error('备份内容已损坏');}validateState(state);return normalizeState(state);
}
let database:Promise<IDBDatabase>|undefined;
const db=()=>database??=new Promise((resolve,reject)=>{const r=indexedDB.open('hero-health-development',1);r.onupgradeneeded=()=>r.result.createObjectStore('state');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
export async function readState():Promise<HealthState|null>{
 assertNativeStorage();
 if(nativeAvailable()){const s=await nativeCall<unknown>('readState');if(s===null)return null;validateState(s,true);return normalizeState(s);}
 const d=await db();return new Promise((resolve,reject)=>{const r=d.transaction('state','readonly').objectStore('state').get('current');r.onsuccess=()=>{try{if(!r.result){resolve(null);return;}validateState(r.result);resolve(normalizeState(r.result));}catch(e){reject(e);}};r.onerror=()=>reject(r.error);});
}
export async function writeState(state:HealthState):Promise<HealthState>{
 assertNativeStorage();
 validateState(state,true);
 if(nativeAvailable()){const saved=await nativeCall<unknown>('saveState',state);validateState(saved,true);return normalizeState(saved);}
 const d=await db();await new Promise<void>((resolve,reject)=>{const t=d.transaction('state','readwrite');t.objectStore('state').put(state,'current');t.oncomplete=()=>resolve();t.onerror=()=>reject(t.error);});return state;
}
export async function downloadText(text:string,name:string){
 assertNativeStorage();
 if(nativeAvailable()){await nativeCall('exportFile',{text,name});return;}
 const url=URL.createObjectURL(new Blob([text],{type:'application/octet-stream'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),3000);
}
export async function restoreWithSafety(current:HealthState,replacement:HealthState,password:string,save:(state:HealthState)=>Promise<void>,exporter=downloadText){
 validateState(replacement);
 const backup=await encryptBackup(current,password);
 await exporter(backup,`健康星-恢复前安全备份-${Date.now()}.herobak`);
 await save(normalizeState(replacement));
}
