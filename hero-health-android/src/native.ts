export const nativeAvailable=()=>typeof window.HeroNative?.postMessage==='function';
export function assertNativeStorage(){if(typeof location!=='undefined'&&location.hostname==='app.hero.local'&&!nativeAvailable())throw new Error('本地安全存储连接不可用，请重新打开应用');}
declare global {interface Window {HeroNative?:{postMessage:(message:string)=>void};heroNativeResult?:(id:string,result:unknown,error?:string)=>void;heroBack?:()=>boolean;}}
const pending=new Map<string,{resolve:(value:any)=>void;reject:(reason:Error)=>void}>();
window.heroNativeResult=(id,result,error)=>{const request=pending.get(id);if(!request)return;pending.delete(id);if(error)request.reject(new Error(error));else request.resolve(result);};
export function nativeCall<T>(action:string,payload:unknown={}):Promise<T>{if(!nativeAvailable())return Promise.reject(new Error('此操作需要在安卓应用中使用'));const id=crypto.randomUUID();return new Promise((resolve,reject)=>{pending.set(id,{resolve,reject});try{window.HeroNative!.postMessage(JSON.stringify({id,action,payload}));}catch{pending.delete(id);reject(new Error('无法连接本地存储'));}});}
window.heroBack=()=>{const event=new Event('hero-back',{cancelable:true});window.dispatchEvent(event);return event.defaultPrevented;};
export async function openReport(file:{id?:string;name:string;dataUrl:string}){if(nativeAvailable()&&file.id){await nativeCall('openReport',{id:file.id});return;}if(file.dataUrl.startsWith('data:')){const a=document.createElement('a');a.href=file.dataUrl;a.download=file.name;a.click();}}
