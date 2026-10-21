import {uid,validDate,today,associateImport,type HealthState,type HealthReport} from './model';
import {nativeCall} from './native';
import type {AiConfig} from './ai-config';
import {planCardJobs,saveCardBatchChunk,type PageInventory,type CardBatchReply} from './ai-batch';
import {acceptedReportName} from './report-name';

export function renamePendingReport(s:HealthState,id:string):HealthState{
 const report=s.reports.find(r=>r.id===id),a=report?.analyses?.at(-1);
 if(!report||!a||a.accepted||a.batchComplete===false)return s;
 const date=a.reportDateConflict?'':a.reportDate?.date||(['人工核对','检验日期','审核日期'].includes(report.dateSource||'')?report.date:'');
 const time=validDate(date)&&date<=today()?date:'待核对';
 return {...s,reports:s.reports.map(r=>r.id===id?{...r,name:acceptedReportName(a.examName,time,r.file?.name||r.name,r.file?.mime)}:r)};
}
export function reportDeletionImpact(s:HealthState,id:string){
 const readingIds=new Set(s.readings.filter(r=>r.reportId===id).map(r=>r.id));
 const summaries=(s.aiSummaries||[]).filter(a=>a.reportIds.includes(id)||a.readingIds.some(v=>readingIds.has(v))||a.sourceReadings.some(r=>r.reportId===id)||a.reportSources.some(r=>r.id===id));
 return {readings:readingIds.size,summaryIds:new Set(summaries.map(a=>a.id))};
}
export function deleteReport(s:HealthState,id:string):HealthState{
 if(!s.reports.some(r=>r.id===id))return s;
 const impact=reportDeletionImpact(s,id);
 return {...s,revision:s.revision+1,reports:s.reports.filter(r=>r.id!==id),readings:s.readings.filter(r=>r.reportId!==id),...(s.aiSummaries?{aiSummaries:s.aiSummaries.filter(a=>!impact.summaryIds.has(a.id))}:{})};
}
export function analysisFailureMessage(stage:string,error:unknown){return `${stage}未完成：${error instanceof Error?error.message:'操作失败，请重试'}`.slice(0,600);}
export function recordAnalysisFailure(s:HealthState,reportIds:string[],stage:string,error:unknown):HealthState{
 const failed=new Set(reportIds);return {...s,reports:s.reports.map(r=>failed.has(r.id)?{...r,status:r.analyses?.at(-1)&&!r.analyses.at(-1)!.accepted?'待确认':'失败',analysisError:analysisFailureMessage(stage,error)}:r)};
}
type Commit=(update:(state:HealthState)=>HealthState)=>Promise<unknown>;
type Invoke=<T>(action:string,payload?:unknown)=>Promise<T>;
/** Import must use the canonical archive returned AFTER durable attachment persistence. */
export async function importAndAnalyzeReport(report:HealthReport,cardId:string,config:AiConfig,commit:(update:(state:HealthState)=>HealthState)=>Promise<HealthState>,onSaved:()=>void,progress:(done:number,total:number)=>void=()=>{},invoke:Invoke=nativeCall){
 const saved=await commit(s=>{if(s.reports.some(r=>(report.file?.sha256&&r.file?.sha256===report.file.sha256)||r.file?.dataUrl===report.file?.dataUrl))throw new Error('该文件已导入，请打开原报告核对或重试分析');return associateImport(s,report,cardId);});
 onSaved();
 await analyzeOneReport(saved,report.id,config,commit,progress,invoke);
}
/** Called only from the explicit single-file picker action or a per-report retry. No mount/resume effects. */
export async function analyzeOneReport(snapshot:HealthState,id:string,config:AiConfig,commit:Commit,progress:(done:number,total:number)=>void=()=>{},invoke:Invoke=nativeCall){
 const report=snapshot.reports.find(r=>r.id===id);
 if(!report?.file)throw new Error('报告原件不存在，请重新导入');
 if(!config.hasKey)throw new Error('原件已保存；请先配置 AI 服务，再到此报告重试分析');
 let stage='准备本地原件';
 try{
  const inventory=await invoke<PageInventory>('reportPageCounts',{reportId:id});
  const plan=planCardJobs({...snapshot,reports:[report]},inventory);
  if(plan.problems.length||!plan.jobs.length)throw new Error(plan.problems[0]?.message||'此报告尚未关联有效卡片');
  const batchId=uid();
  await commit(s=>{if(!s.reports.some(r=>r.id===id))throw new Error('报告已删除');return {...s,reports:s.reports.map(r=>r.id===id?{...r,status:'分析中'}:r)};});
  progress(0,plan.jobs.length);
  for(const [index,job] of plan.jobs.entries()){
   stage=`第 ${index+1} / ${plan.jobs.length} 批 AI 请求`;
   const reply=await invoke<CardBatchReply>('analyzeCardBatch',{endpoint:config.endpoint,model:config.model,batchId,cardId:job.cardId,parts:job.parts});
   stage=`第 ${index+1} / ${plan.jobs.length} 批结果校验与保存`;
   await commit(s=>renamePendingReport(saveCardBatchChunk(s,plan,index,batchId,reply),id));
   progress(index+1,plan.jobs.length);
  }
 }catch(e){
  await commit(s=>recordAnalysisFailure(s,[id],stage,e)).catch(()=>{});
  throw new Error(analysisFailureMessage(stage,e));
 }
}
