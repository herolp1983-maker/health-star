import {useRef,useState} from 'react';
import {PlusIcon,UploadIcon,GearIcon,ReloadIcon} from '@radix-ui/react-icons';
import {useApp} from './app-context';
import {useAiConfig} from './AIFlows';
import {Field,Button} from './ui';
import {useKeyboard} from './mobile';
import {uid,validDate,today,type HealthReport} from './model';
import {importAndAnalyzeReport} from './report-workflow';

export default function ReportImportForm({id}:{id?:string}){
 const {data,commit,open,notify,setCritical,critical}=useApp();const {config,error:configError}=useAiConfig();
 const [date,setDate]=useState(''),[institution,setInstitution]=useState(''),[cardId,setCardId]=useState(id||''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[progress,setProgress]=useState('');
 const input=useRef<HTMLInputElement>(null),running=useRef(false),keyboard=useKeyboard();
 const add=async(file:File)=>{
  if(running.current||critical)return;
  if(!cardId||!config){setError('请先选择健康卡片，并等候 AI 配置读取完成');return;}
  if(date&&(!validDate(date)||date>today())){setError('请填写有效检查日期');return;}
  if(!['image/png','image/jpeg','image/webp','application/pdf'].includes(file.type)||file.size>15*1024*1024){setError('请选择不超过15 MB的一份 PNG、JPG、WebP 或 PDF');return;}
  running.current=true;setBusy(true);setCritical(true);setError('');setProgress('正在加密保存原件…');let saved=false;const reportId=uid();
  try{
   const bytes=await file.arrayBuffer(),hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
   const dataUrl=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(new Error('无法读取原件'));reader.readAsDataURL(file);});
   const report:HealthReport={id:reportId,name:file.name,date,dateSource:date?'人工核对':'待确认',uploadedAt:new Date().toISOString(),institution:institution.trim()||'未填写机构',status:'未分析',cardIds:[],file:{name:file.name,mime:file.type,dataUrl,sha256:hash}};
   await importAndAnalyzeReport(report,cardId,config,commit,()=>{saved=true;setProgress('原件已保存，正在准备 AI 分析…');},(done,total)=>setProgress(`正在分析此报告 · ${done} / ${total} 段`));
   notify('此报告已分析并自动命名，请核对结论和指标');
  }catch(e){const message=e instanceof Error?e.message:'操作未完成';if(saved)notify(message);else setError(message);}
  finally{running.current=false;setBusy(false);setCritical(false);if(saved)open({kind:'ai-report',id:reportId});}
 };
 return <><div className="import-step"><span className="badge">单份导入</span><strong>选择报告，保存后自动分析</strong></div><label className="form-field"><span>健康卡片（必选）</span><select aria-label="关联健康卡片" value={cardId} disabled={busy} onChange={e=>{keyboard.hide();setCardId(e.target.value);setError('');}}><option value="">请选择相关疾病或健康主题</option>{data.cards.filter(c=>!c.archived).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label><button className="text-button" disabled={busy} onClick={()=>open({kind:'card',returnTo:'import'})}><PlusIcon/>新建健康卡片</button><Field type="date" label="报告检验／审核日期（可留空）" value={date} onChange={setDate} disabled={busy}/><Field label="检查机构（选填）" value={institution} onChange={setInstitution} disabled={busy}/><p className="small muted">优先识别原件检验日期，其次审核日期；不取上传日期。每次只选择一份，PDF可包含多页。</p><section className="ai-destination"><strong>{config?.endpoint?new URL(config.endpoint).host:'未配置 AI 服务'}</strong><span>{config?.model||'未设置模型'}</span></section><p className="small muted">点击选择并选定文件后，会先加密保存，再自动将此报告图片（PDF逐页转图）、所选卡片的病情背景、指标历史、报告摘要及用药发送给上述服务。可能产生服务商费用，数据保留由服务商决定。无需再次确认发送；分析结论和指标需你核对后才生效。</p>{!config?.hasKey&&<><p className="form-error">尚未配置密钥时仅保存原件，稍后可在此报告中重试分析。</p><Button secondary disabled={busy} onClick={()=>open({kind:'ai-settings'})}><GearIcon/>配置 AI 服务</Button></>}<Button disabled={busy||critical||!cardId||!config} onClick={()=>{keyboard.hide();input.current?.click();}}>{busy?<><ReloadIcon className="spinning"/>{progress}</>:<><UploadIcon/>{config?.hasKey?'选择一份报告并自动分析':'选择一份报告并保存本机'}</>}</Button><input ref={input} type="file" accept="image/png,image/jpeg,image/webp,application/pdf" multiple={false} hidden onChange={e=>{const files=Array.from(e.currentTarget.files||[]);e.currentTarget.value='';if(!files?.length)return;if(files.length!==1){setError('每次只允许上传一份报告');return;}void add(files[0]);}}/><p className="small muted">单份不超过15 MB · 原件始终先保存本机 · 关闭应用后不会自行重发</p>{(error||configError)&&<p className="form-error" role="alert">{error||configError}</p>}</>;
}
