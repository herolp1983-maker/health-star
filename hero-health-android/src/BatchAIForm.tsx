import {shiftMatchedDates,type MatchedDraft} from './extraction-review';
import {MatchedMetrics} from './MatchedMetrics';
import {ExtractionReview,ExtractionCoverage,issueDrafts,issueDecisions,type IssueDraft} from './ExtractionReview';
import {useEffect,useRef,useState} from 'react';
import {BarChartIcon,ReloadIcon,GearIcon} from '@radix-ui/react-icons';
import {useApp} from './app-context';
import {readAiConfig,type AiConfig} from './ai-config';
import {nativeCall,openReport} from './native';
import {uid} from './model';
import {planCardJobs,saveCardBatchChunk,acceptBatchReviews,batchInputDigest,type BatchPlan,type PageInventory,type CardBatchReply} from './ai-batch';
import {renamePendingReport,recordAnalysisFailure,analysisFailureMessage} from './report-workflow';
import type {AiMetric} from './ai-results';
import {Field,Button} from './ui';

type Draft={reportId:string;analysisId:string;reportDate:string;issues:IssueDraft[];metrics:MatchedDraft[]};
export default function BatchAIForm(){
 const {data,commit,open,notify,setCritical}=useApp();
 const [config,setConfig]=useState<AiConfig>(),[inventory,setInventory]=useState<PageInventory>(),[loading,setLoading]=useState(true),[error,setError]=useState('');
 const [onlyIncomplete,setOnlyIncomplete]=useState(false),[busy,setBusy]=useState(false),[completed,setCompleted]=useState(0),[currentCard,setCurrentCard]=useState(''),[paused,setPaused]=useState(false),[draft,setDraft]=useState<Draft[]>([]);
 const planRef=useRef<BatchPlan|undefined>(undefined),batchRef=useRef(''),nextRef=useRef(0),pauseRef=useRef(false),starting=useRef(false);
 const load=async()=>{setLoading(true);setError('');try{const c=await readAiConfig();setConfig(c);setInventory(await nativeCall<PageInventory>('reportPageCounts'));}catch(e){setError(e instanceof Error?e.message:'无法整理报告，请重试');}finally{setLoading(false);}};
 useEffect(()=>{void load();},[]);
 useEffect(()=>{setDraft(previous=>data.reports.filter(r=>{const a=r.analyses?.at(-1);return a&&!a.accepted&&a.batchComplete!==false;}).map(r=>{const a=r.analyses!.at(-1)!;const existing=previous.find(d=>d.reportId===r.id&&d.analysisId===a.id);if(existing)return existing;return {reportId:r.id,analysisId:a.id,issues:issueDrafts(a.reviewItems),reportDate:a.reportDateConflict?'':a.reportDate?.date||r.date,metrics:a.metrics.map(m=>({metric:m,selected:true,value:String(m.value),second:m.second===undefined?'':String(m.second),date:m.date||(a.reportDateConflict?'':a.reportDate?.date||r.date)}))};}));},[data.reports]);
  const candidate=inventory?planCardJobs(data,inventory,onlyIncomplete):undefined,plan=data.batchProgress?.plan||planRef.current||candidate;
 const run=async()=>{
   if(starting.current||!config?.hasKey||!candidate||!inventory)return;starting.current=true;
   const saved=data.batchProgress,frozen=saved?.plan||candidate;
   if(!frozen.jobs.length){starting.current=false;return;}
  pauseRef.current=false;setPaused(false);setBusy(true);setCritical(true);setError('');let stage='准备批量分析';
  try{
    const sourceDigest=await batchInputDigest(data,config);
    if(saved){
     if(sourceDigest!==saved.sourceDigest||saved.plan.jobs.slice(saved.nextIndex).some(job=>job.parts.some(part=>inventory.pages[part.reportId]!==part.pageCount)))throw new Error('原件、健康资料或 AI 设置已变化。请放弃旧任务后重新分析');
     planRef.current=saved.plan;batchRef.current=saved.id;nextRef.current=saved.nextIndex;setCompleted(saved.nextIndex);
    }else{
     const id=uid();await commit(s=>({...s,batchProgress:{id,plan:frozen,nextIndex:0,sourceDigest}}));
     planRef.current=frozen;batchRef.current=id;nextRef.current=0;setCompleted(0);
    }
   while(nextRef.current<frozen.jobs.length&&!pauseRef.current){
    const index=nextRef.current,job=frozen.jobs[index];setCurrentCard(data.cards.find(c=>c.id===job.cardId)?.name||'健康卡片');
    stage=`第 ${index+1} / ${frozen.jobs.length} 批 AI 请求`;
    const reply=await nativeCall<CardBatchReply>('analyzeCardBatch',{endpoint:config.endpoint,model:config.model,batchId:batchRef.current,cardId:job.cardId,parts:job.parts});
    stage=`第 ${index+1} / ${frozen.jobs.length} 批结果校验与保存`;
     await commit(s=>{const progress=s.batchProgress;if(progress?.id!==batchRef.current||progress.nextIndex!==index)throw new Error('批量进度已变化，请重新打开任务');
      const next=job.parts.reduce((state,part)=>renamePendingReport(state,part.reportId),saveCardBatchChunk(s,frozen,index,batchRef.current,reply));
      return {...next,batchProgress:index+1<frozen.jobs.length?{...progress,nextIndex:index+1}:undefined};});nextRef.current=index+1;setCompleted(index+1);
   }
   if(nextRef.current>=frozen.jobs.length){setPaused(false);notify('全部可处理资料已分析，请集中核对后更新卡片');}else setPaused(true);
  }catch(e){setError(analysisFailureMessage(stage,e));setPaused(true);
    if(batchRef.current){const failed=frozen.jobs[nextRef.current]?.parts.map(p=>p.reportId)||[];
     await commit(s=>recordAnalysisFailure(s,failed,stage,e)).catch(()=>{});}
  }finally{setBusy(false);setCritical(false);starting.current=false;}
 };
 const confirm=async()=>{setError('');setBusy(true);setCritical(true);try{
  const reviews=draft.map(d=>({reportId:d.reportId,analysisId:d.analysisId,reportDate:d.reportDate,metrics:d.metrics.filter(m=>m.selected).map(m=>{if(!m.value.trim()||(m.metric.second!==undefined&&!m.second.trim()))throw new Error('请填写已勾选指标的完整数值');return {...m.metric,value:Number(m.value),date:m.date||d.reportDate,...(m.metric.second!==undefined?{second:Number(m.second)}:{})};})}));
  await commit(s=>acceptBatchReviews(s,reviews.map(review=>({...review,issueDecisions:issueDecisions(s.reports.find(r=>r.id===review.reportId)!.analyses!.at(-1)!.reviewItems||[],draft.find(d=>d.reportId===review.reportId)!.issues,s,review.reportDate)}))));notify('已更新所有已核对报告、关联卡片及首页趋势');open(null);
 }catch(e){setError(e instanceof Error?e.message:'保存失败，原资料保持不变');}finally{setBusy(false);setCritical(false);}};
 const edit=(id:string,index:number,patch:Partial<Draft['metrics'][number]>)=>setDraft(rows=>rows.map(d=>d.reportId===id?{...d,metrics:d.metrics.map((m,i)=>i===index?{...m,...patch,...(patch.date!==undefined?{dateEdited:true}:{})}:m)}:d));
 const partial=data.reports.filter(r=>r.analyses?.at(-1)?.batchComplete===false);
 return <>
  <p className="intro-copy">一键处理全部报告，按各自关联卡片合并分析，并带上该卡片历史记录、已核对摘要及用药。无需逐份提交。</p>
  {loading?<p role="status" className="small muted">正在检查本地原件与页数，不会联网…</p>:<>
   {plan&&<section className="batch-overview"><strong>{plan.reportIds.length} 份资料 · {plan.cardIds.length} 张卡片</strong><span>自动分为 {plan.jobs.length} 批，每批最多8页、3份文件；跨卡片报告会分别针对各卡片分析。</span></section>}
    {!planRef.current&&!data.batchProgress&&<label className="batch-option"><input type="checkbox" checked={onlyIncomplete} disabled={busy} onChange={e=>setOnlyIncomplete(e.target.checked)}/>仅处理未完成或失败的报告</label>}
   <div className="inline-notice"><span>将向下方服务发送上述原件图片（PDF逐页转图）、各自卡片的说明、追踪指标、最近指标、报告摘要及在用/停用药记录。同次任务较早批次结果会作为“未核对资料”继续交叉对照。可能产生服务商费用；具体数据保留规则由服务商决定。</span></div>
   {config&&<section className="ai-destination"><strong>{config.endpoint?new URL(config.endpoint).host:'尚未填写服务地址'}</strong><span>{config.model||'尚未填写模型'}</span><small>{config.hasKey?'已安全保存密钥':'尚未设置密钥'}</small></section>}
   {!config?.hasKey&&<Button secondary onClick={()=>open({kind:'ai-settings'})}><GearIcon/>配置 AI 服务</Button>}
    <Button disabled={busy||!config?.hasKey||!plan?.jobs.length} onClick={()=>void run()}>{busy?<><ReloadIcon className="spinning"/>正在处理 {currentCard}</>:data.batchProgress||paused?'继续未完成任务':completed&&completed===plan?.jobs.length?'重新分析全部资料':<><BarChartIcon/>一键分析全部资料</>}</Button>
    {(busy||completed>0||data.batchProgress)&&plan&&<div className="batch-progress" role="status"><progress value={data.batchProgress?.nextIndex??completed} max={plan.jobs.length}/><p>已保存 {data.batchProgress?.nextIndex??completed} / {plan.jobs.length} 批结果{busy?` · ${currentCard}`:''}</p>{busy&&<button type="button" className="text-button" disabled={pauseRef.current} onClick={()=>{pauseRef.current=true;setPaused(true);}}>本批完成后暂停</button>}</div>}
    {data.batchProgress&&!busy&&<Button secondary onClick={()=>void commit(s=>({...s,batchProgress:undefined})).then(()=>{planRef.current=undefined;batchRef.current='';nextRef.current=0;setCompleted(0);setPaused(false);setError('');}).catch(e=>setError(e instanceof Error?e.message:'无法放弃旧任务'))}>放弃旧任务并重新分析（可能再次产生费用）</Button>}
   {plan?.problems.length? <details className="batch-problems"><summary>{plan.problems.length} 份资料暂不能处理</summary>{plan.problems.map(p=><p className="small muted" key={p.reportId}>{data.reports.find(r=>r.id===p.reportId)?.name}：{p.message}</p>)}</details>:null}
   {!inventory&&<Button secondary onClick={()=>void load()}>重新检查原件</Button>}
  </>}
  {error&&<p className="form-error" role="alert">{error} 已完成结果会保留，剩余任务不会自动重试。</p>}
  {partial.length>0&&<p className="inline-notice warning">{partial.length} 份报告仍有未完成批次，完成全部相关卡片及页数后才能确认，不会将部分结果写入趋势。</p>}
  {draft.length>0&&<>
   <h3>集中核对 · {draft.length} 份完整结果</h3><p className="small muted">可一次确认所有完整结果。明确匹配项无需逐项勾选；核对结论与日期，并处理模糊匹配。修正或排除指标后，AI原摘要仅保留历史，不作为卡片结论。</p>
   {draft.map((d,ri)=>{const report=data.reports.find(r=>r.id===d.reportId)!,a=report.analyses!.at(-1)!;return <details className="batch-review-report" open={ri===0} key={d.reportId}><summary>{report.name} · {d.metrics.length} 项指标</summary><p className="small muted">{report.cardIds.map(id=>data.cards.find(c=>c.id===id)?.name).join(' / ')}</p><p>{a.summary}</p><ExtractionCoverage analysis={a}/>{a.reportDateConflict&&<p className="form-error">不同分段的同类日期存在冲突，请对照原件后手动填写，不会默认采信其中一条。</p>}<Field type="date" label="报告检验／审核日期（必核对）" value={d.reportDate} disabled={busy} onChange={date=>setDraft(rows=>rows.map(row=>row.reportId===d.reportId?{...row,reportDate:date,metrics:shiftMatchedDates(row.metrics,row.reportDate,date)}:row))}/>{a.reportDate&&<p className="small muted">{a.reportDate.source} · 输入第{a.reportDate.page}页{a.reportDate.printedPage?` · 印刷页码 ${a.reportDate.printedPage}`:''} · {a.reportDate.quote}</p>}{a.notes.map((n,i)=><p className="small muted" key={i}>{n}</p>)}{report.file?.mime==='application/pdf'?<Button secondary disabled={busy} onClick={()=>void openReport(report.file!).catch(()=>setError('无法打开PDF，请在报告详情查看'))}>对照 PDF 原件</Button>:report.file&&<details className="ai-original"><summary>对照原件图片</summary><img src={report.file.dataUrl} alt="报告原件"/></details>}
    {!d.metrics.length&&<p className="small muted">暂无已匹配指标，可核对下方待确认或未匹配项目。明确跳过的项目不写入趋势。</p>}
    <MatchedMetrics rows={d.metrics} edit={(index,patch)=>edit(d.reportId,index,patch)} disabled={busy}/><ExtractionReview items={a.reviewItems||[]} drafts={d.issues} onChange={issues=>setDraft(rows=>rows.map(row=>row.reportId===d.reportId?{...row,issues}:row))} allowedIds={[...new Set(data.cards.filter(c=>report.cardIds.includes(c.id)).flatMap(c=>c.metricIds))]} disabled={busy} reportId={d.reportId}/></details>;})}
   <Button disabled={busy} onClick={()=>void confirm()}>确认全部结果并更新健康卡片</Button>
  </>}
 </>;
}
