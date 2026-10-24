import { nativeCall } from './native';

export type AiConfig = { endpoint:string; model:string; hasKey:boolean };
// Explicitly whitelist metadata. Saved keys never become application state or backup content.
function metadata(value:unknown):AiConfig {
 if(!value || typeof value!=='object')throw new Error('AI 配置读取失败，请重新打开设置');
 const config=value as Record<string,unknown>;
 if(typeof config.endpoint!=='string'||typeof config.model!=='string'||typeof config.hasKey!=='boolean')throw new Error('AI 配置格式无效');
 return {endpoint:config.endpoint,model:config.model,hasKey:config.hasKey};
}
export async function readAiConfig(){return metadata(await nativeCall('readAiConfig'));}
/** Each settings-close refresh clears the old destination; canceled reads cannot overwrite it. */
export function observeAiConfig(update:(config:AiConfig|undefined,error:string)=>void){
 let active=true;update(undefined,'');
 readAiConfig().then(config=>{if(active)update(config,'');}).catch(()=>{if(active)update(undefined,'无法读取服务配置，请重新打开或前往设置');});
 return ()=>{active=false;};
}
export async function saveAiConfig(endpoint:string,model:string,newKey:string){return metadata(await nativeCall('saveAiConfig',{endpoint,model,newKey}));}
export async function clearAiKey(){return metadata(await nativeCall('clearAiKey'));}
