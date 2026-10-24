import {shiftMatchedDates,type MatchedDraft} from './extraction-review';
import {MatchedMetrics} from './MatchedMetrics';
import {ExtractionReview,ExtractionCoverage,issueDrafts,issueDecisions,type IssueDraft} from './ExtractionReview';
import {useEffect,useState,useRef} from 'react';
import {ReloadIcon,BarChartIcon,LockClosedIcon,GearIcon} from '@radix-ui/react-icons';
import {nativeCall,openReport} from './native';
import {observeAiConfig,type AiConfig} from './ai-config';
import {parseReportReply,saveReportAnalysis,acceptReportAnalysis,parseSummaryReply,type AiReply,type AiMetric} from './ai-results';
import {analyzeOneReport} from './report-workflow';
import {useApp} from './app-context';
import {Field,Button} from './ui';

export function useAiConfig(){const {sheet}=useApp();const editing=sheet?.kind==='ai-settings';const [config,setConfig]=useState<AiConfig>(),[error,setError]=useState('');useEffect(()=>{if(editing)return;return observeAiConfig((value,message)=>{setConfig(value);setError(message);});},[editing]);return {config,error};}
function Consent({config,report=false}:{config?:AiConfig;report?:boolean}){
 const {open}=useApp();return <>
  <div className="inline-notice"><LockClosedIcon/><span>{report?'将发送此报告的图片（PDF逐页转图片）、关联卡片指标定义及相关指标每项最近30条记录（最多300条）、相关报告历史摘要以及病情背景、在用/停用药记录。':'将发送活动卡片及每项最近30条指标记录（最多600条）、最近20份已核对报告摘要，以及卡片病情背景与用药记录；不发送原件图片。'}发送至你配置的 AI 服务，可能产生服务商费用；数据保留规则由服务商决定。</span></div>
  {config?<section className="ai-destination"><strong>{config.endpoint?new URL(config.endpoint).host:'尚未填写服务地址'}</strong><span>{config.model||'尚未填写模型'}</span><small>{config.hasKey?'已保存密钥 · 仅点击下方按钮才发送':'尚未配置密钥'}</small></section>:<p className="small muted">正在读取服务配置…</p>}
  {(!config?.hasKey)&&<Button secondary onClick={()=>open({kind:'ai-settings'})}><GearIcon/>配置 AI 服务</Button>}
 </>;
}
const safeError=(e:unknown)=>e instanceof Error?e.message:'操作未完成，请重试';
export function ReportAIForm({id}:{id:string}){
 const {data,commit,open,notify,setCritical}=useApp();const {config,error:configError}=useAiConfig();
 const report=data.reports.find(r=>r.id===id),analysis=report?.analyses?.at(-1);
 const running=useRef(false);const [busy,setBusy]=useState(false),[error,setError]=useState(''),[progress,setProgress]=useState(''),[recordDate,setRecordDate]=useState(analysis?.reportDateConflict?'':analysis?.reportDate?.date||report?.date||'');
 const [issues,setIssues]=useState<IssueDraft[]>([]);
 useEffect(()=>setIssues(issueDrafts(analysis?.reviewItems)),[analysis?.id,analysis?.batchComplete,analysis?.reviewItems?.length]);
 const [draft,setDraft]=useState<MatchedDraft[]>([]);
 useEffect(()=>{setDraft((analysis?.metrics||[]).map(m=>({selected:true,metric:m,value:String(m.value),second:m.second===undefined?'':String(m.second),date:m.date||(analysis?.reportDateConflict?'':analysis?.reportDate?.date||report?.date||'')})));},[analysis?.id,analysis?.batchComplete,analysis?.metrics.length]);

 const run=async()=>{if(!config?.hasKey||running.current)return;running.current=true;setBusy(true);setCritical(true);setError('');try{
  await analyzeOneReport(data,id,config,commit,(done,total)=>setProgress(`${done} / ${total} 段`));notify('此报告已分析并自动命名，请核对结论后更新卡片');
 }catch(e){setError(safeError(e));}finally{running.current=false;setBusy(false);setCritical(false);}};
 useEffect(()=>{setRecordDate(analysis?.reportDateConflict?'':analysis?.reportDate?.date||report?.date||'');},[analysis?.id,analysis?.batchComplete]);
 const accept=async()=>{setError('');try{
  const metrics=draft.filter(d=>d.selected).map(d=>{if(!d.value.trim()||(d.metric.second!==undefined&&!d.second.trim()))throw new Error('请填写选中指标的完整数值');return {...d.metric,value:Number(d.value),...(d.metric.second!==undefined?{second:Number(d.second)}:{}),date:d.date||recordDate};});
  setBusy(true);setCritical(true);await commit(s=>acceptReportAnalysis(s,id,analysis!.id,metrics,recordDate,issueDecisions(analysis!.reviewItems||[],issues,s,recordDate)));notify('已核对并更新卡片、首页和趋势');open(null);
 }catch(e){setError(safeError(e));}finally{setBusy(false);setCritical(false);}};
 const edit=(i:number,patch:Partial<(typeof draft)[number]>)=>setDraft(rows=>rows.map((d,j)=>i===j?{...d,...patch,...(patch.date!==undefined?{dateEdited:true}:{})}:d));
 if(!report)return <p>报告不存在。</p>;
 return <>
  <h3>{report?.name}</h3>{report.status==='失败'&&!report.analysisError&&<p className="form-error">此历史失败未记录具体原因。可重新分析；新版会保留失败阶段和原因。</p>}{analysis&&<ExtractionCoverage analysis={analysis}/>}
  {analysis&&!analysis.accepted&&analysis.batchComplete!==false?<>
   <section className="surface ai-result"><span className="badge warning">待核对 · 尚未更新指标</span><p>{analysis.summary}</p>{analysis.cards.map(c=><div key={c.cardId}><h4>{data.cards.find(x=>x.id===c.cardId)?.name}</h4><p className="small">近况：{c.recent}<br/>趋势：{c.trend}<br/>关注：{c.attention}</p></div>)}{analysis.notes.map((note,i)=><p className="small muted" key={i}>{note}</p>)}</section>
   {report.file?.mime.startsWith('image/')?<details className="ai-original"><summary>对照报告原件</summary><img src={report.file.dataUrl} alt="报告原件"/></details>:report.file&&<Button secondary onClick={()=>void openReport(report.file!).catch(()=>setError('无法打开原件，请在报告详情查看'))}>打开 PDF 原件</Button>}
   <Field type="date" label="报告检验／审核日期（必核对）" value={recordDate} onChange={date=>{setDraft(rows=>shiftMatchedDates(rows,recordDate,date));setRecordDate(date);}} disabled={busy}/><p className="small muted">核对本报告结论与日期后统一确认。已明确匹配的指标无需逐项勾选；只有模糊匹配需要选择归属。若手动修正或排除指标，原 AI 摘要仅保留作历史对照。</p>
   <MatchedMetrics rows={draft} edit={edit} disabled={busy}/>
   <ExtractionReview items={analysis.reviewItems||[]} drafts={issues} onChange={setIssues} allowedIds={[...new Set(data.cards.filter(c=>report.cardIds.includes(c.id)).flatMap(c=>c.metricIds))]} disabled={busy} reportId={id}/>
   <Button disabled={busy} onClick={()=>void accept()}>{busy?'正在保存…':'确认并更新健康卡片'}</Button>
   <details><summary>重新分析</summary><Consent config={config} report/><Button secondary disabled={busy||!config?.hasKey} onClick={()=>void run()}>发送报告，重新分析</Button></details>
  </>:<>{analysis?.batchComplete===false&&<p className="form-error">上次分段分析未完成，尚不能确认。请重新分析此报告；原件保留。</p>}<Consent config={config} report/>{analysis?.accepted&&<p className="small muted">上次结果已保存，重新分析会新增版本；已核对的记录会保留。</p>}<Button disabled={busy||!config?.hasKey||!report.file} onClick={()=>void run()}>{busy?<><ReloadIcon className="spinning"/>正在分析 {progress}</>:<><BarChartIcon/>{analysis?'重新分析此报告':'分析此报告'}</>}</Button>{!report.file&&<p className="form-error">此报告缺少原件，请先导入图片或 PDF。</p>}</>}
  {(error||configError||report.analysisError)&&<p className="form-error" role="alert">{error||configError||report.analysisError}</p>}
  {busy&&<p className="small muted" role="status">正在处理，请保持应用打开。不会自动重试；手动重试可能再次产生服务商费用。</p>}
 </>;
}
export function SummaryAIForm({onGenerated}:{onGenerated?:()=>void}={}){
 const {data,commit,notify,setCritical}=useApp();const {config,error:configError}=useAiConfig();const [busy,setBusy]=useState(false),[error,setError]=useState('');const running=useRef(false);
 const run=async()=>{if(!config?.hasKey||running.current)return;running.current=true;setBusy(true);setCritical(true);setError('');try{
  const reply=await nativeCall<AiReply>('analyzeSummary',{endpoint:config.endpoint,model:config.model,summaryPrompt:data.settings.summaryPrompt||''});
  await commit(s=>({...s,aiSummaries:[...(s.aiSummaries||[]),parseSummaryReply(reply,s)]}));notify('AI 综合分析报告已保存');onGenerated?.();
 }catch(e){setError(safeError(e));}finally{running.current=false;setBusy(false);setCritical(false);}};
 return <section className="summary-generate"><details><summary>本次发送范围与服务</summary><Consent config={config}/></details><p className="small muted">{config?.endpoint?new URL(config.endpoint).host:'请先配置 AI 服务'} · {config?.model||'模型未设置'}。发送活动卡片的病情背景、用药、每项最近30条指标（总计最多600条）及最近20份已核对报告摘要；不发送原件。{data.settings.summaryPrompt?'自定义分析提示词':'专家综合分析提示词'}。点击生成即向该服务发送上述资料，可能产生服务商费用。</p>{!config?.hasKey&&<Consent config={config}/>}<Button disabled={busy||!config?.hasKey} onClick={()=>void run()}>{busy?<><ReloadIcon className="spinning"/>正在生成…</>:<><BarChartIcon/>{data.aiSummaries?.length?'重新生成 AI 综合分析':'生成 AI 综合分析'}</>}</Button>{(error||configError)&&<p className="form-error" role="alert">{error||configError}</p>}{busy&&<p className="small muted" role="status">生成后会保存在本机，请保持应用打开。</p>}</section>;
}
export function ReportAIHistory({id}:{id:string}){
 const {data}=useApp();const versions=data.reports.find(r=>r.id===id)?.analyses||[];
 if(!versions.length)return null;
 return <details className="ai-analysis-history"><summary>AI 分析历史 · {versions.length} 个版本</summary>{[...versions].reverse().map(a=><section className="surface" key={a.id}><span className={`badge ${a.accepted?'success':'warning'}`}>{a.accepted?'已核对':'原始提取 · 未确认'}</span><p className="small muted">{new Date(a.date).toLocaleString('zh-CN')} · {a.model}</p><p>{a.summary}</p>{a.batchSegments?.map((segment,i)=><p className="small muted" key={"segment-"+i}>{data.cards.find(c=>c.id===segment.cardId)?.name} · 第{segment.startPage}至{segment.endPage}页：{segment.summary}</p>)}{a.metrics.map((m,i)=><p className="small muted" key={i}>输入第 {m.page} 页{m.printedPage?` · 印刷页码 ${m.printedPage}`:''} · {data.metrics.find(x=>x.id===m.metricId)?.name}：{m.value}{m.second!==undefined?`/${m.second}`:''} {m.unit} · {m.date}</p>)}{a.reviewedMetrics&&a.useCardNotes===false&&<><p className="small muted">核对后的保存值：</p>{a.reviewedMetrics.map((m,i)=><p className="small" key={i}>{data.metrics.find(x=>x.id===m.metricId)?.name} {m.value}{m.second!==undefined?`/${m.second}`:''} {m.unit} · {m.date}</p>)}</>}{a.reviewItems?.map(item=><p className="small muted" key={item.id}>{item.category==='review'?'待确认':'未匹配'} · {item.name} {item.value} {item.unit} · 输入第{item.page}页{item.printedPage?` · 印刷页码 ${item.printedPage}`:''} · {a.reviewedIssues?.find(d=>d.issueId===item.id)?.action==='mapped'?'已人工归属':a.accepted?'已明确跳过':'尚待处理'}：{item.reason}</p>)}{a.notes.map((note,i)=><p className="small muted" key={i}>{note}</p>)}</section>)}</details>;
}
