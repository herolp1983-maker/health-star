import {mergeReviewItems,type IssueDecision} from './extraction-review';
import {uid,type HealthState} from './model';
import {parseReportReply,acceptReportAnalysis,type AiReply,type AiMetric,type ReportAnalysis} from './ai-results';

export type ReportPart={reportId:string;startPage:number;endPage:number;pageCount:number};
export type CardJob={cardId:string;parts:ReportPart[]};
export type BatchPlan={jobs:CardJob[];problems:{reportId:string;message:string}[];reportIds:string[];cardIds:string[]};
export type PageInventory={pages:Record<string,number>;errors:Record<string,string>};
export type CardBatchReply=AiReply&{pageCounts:Record<string,number>};
/** Bind a paused batch to the inputs that the next native request will read. */
export async function batchInputDigest(s:HealthState,config:{endpoint:string;model:string}):Promise<string>{
 const input=JSON.stringify({cards:s.cards,metrics:s.metrics,readings:s.readings,
  reports:s.reports.map(r=>({id:r.id,date:r.date,cardIds:r.cardIds,file:r.file?{id:r.file.id,sha256:r.file.sha256,mime:r.file.mime,name:r.file.name,...(!r.file.sha256?{dataUrl:r.file.dataUrl}:{})}:null})),
  settings:s.settings,endpoint:config.endpoint,model:config.model});
 const bytes=new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(input)));
 return Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
}
export function planCardJobs(s:HealthState,inventory:PageInventory,onlyIncomplete=false):BatchPlan{
 const reports=s.reports.filter(r=>!onlyIncomplete||(!['已分析','待确认'].includes(r.status)||r.analyses?.at(-1)?.batchComplete===false)).sort((a,b)=>a.date.localeCompare(b.date));
 const problems:BatchPlan['problems']=[],eligible=new Map<string,number>();
 for(const report of reports){
  const pages=inventory.pages[report.id];
  let message=!report.file?'缺少报告原件':!report.cardIds.length||report.cardIds.some(id=>!s.cards.some(c=>c.id===id))?'尚未关联有效健康卡片':!Number.isInteger(pages)||pages<1||pages>500?inventory.errors[report.id]||'无法识别原件页数':'';
  if(message)problems.push({reportId:report.id,message});else eligible.set(report.id,pages);
 }
 const jobs:CardJob[]=[],cardIds:string[]=[];
 for(const card of s.cards){
  const linked=reports.filter(r=>eligible.has(r.id)&&r.cardIds.includes(card.id));if(!linked.length)continue;cardIds.push(card.id);
  let parts:ReportPart[]=[],pagesUsed=0;
  const flush=()=>{if(parts.length)jobs.push({cardId:card.id,parts});parts=[];pagesUsed=0;};
  for(const report of linked){let start=1;const count=eligible.get(report.id)!;while(start<=count){
   if(parts.length>=3||pagesUsed===8)flush();const take=Math.min(count-start+1,8-pagesUsed);
   parts.push({reportId:report.id,startPage:start,endPage:start+take-1,pageCount:count});pagesUsed+=take;start+=take;
   if(pagesUsed===8)flush();
  }}flush();
 }
 return {jobs,problems,reportIds:[...eligible.keys()],cardIds};
}
const array=(v:unknown):any[]=>{if(!Array.isArray(v))throw new Error('卡片批量结果格式无效，请重试');return v;};
export function saveCardBatchChunk(s:HealthState,plan:BatchPlan,index:number,batchId:string,reply:CardBatchReply):HealthState{
 const job=plan.jobs[index];if(!job)throw new Error('批量任务不存在');
 const target=s.cards.find(c=>c.id===job.cardId);if(!target)throw new Error('关联卡片已变化，请重新分析');
 const output=reply.output as {card?:any;reports?:unknown};
 if(!output||output.card?.cardId!==job.cardId)throw new Error('AI 返回了其他卡片的内容，尚未更新档案');
 const results=array(output.reports);const expected=job.parts.map(p=>p.reportId);
 if(results.length!==expected.length||new Set(results.map(r=>r?.reportId)).size!==expected.length||results.some(r=>!expected.includes(r?.reportId)))throw new Error('AI 批量结果未完整对应本批报告，尚未更新档案');
 const updates=new Map<string,ReportAnalysis>();
 for(const result of results){
  const part=job.parts.find(p=>p.reportId===result.reportId)!,report=s.reports.find(r=>r.id===part.reportId);
  if(!report||!report.cardIds.includes(job.cardId)||reply.pageCounts?.[part.reportId]!==part.pageCount)throw new Error('报告原件或关联已变化，请重新开始批量分析');
  const one=parseReportReply({...reply,sentPages:(reply.sentPages as Record<string,unknown>|undefined)?.[part.reportId],imageBlocks:(reply.imageBlocks as Record<string,unknown>|undefined)?.[part.reportId],pageCount:part.pageCount,output:{reviewItems:result.reviewItems,readabilityIssues:result.readabilityIssues,examName:result.examName,reportDate:result.reportDate,summary:result.summary,metrics:result.metrics,cards:[output.card],notes:result.notes||[]}},{...s,reports:s.reports.map(r=>r.id===report.id?{...r,cardIds:[job.cardId]}:r)},report.id);
  if((one.reportDate&&(one.reportDate.page<part.startPage||one.reportDate.page>part.endPage))||[...one.metrics,...(one.reviewItems||[]),...(one.readabilityIssues||[])].some(m=>m.page<part.startPage||m.page>part.endPage))throw new Error('AI 引用了本批未发送的页码，尚未更新档案');
  if(reply.inputPageProtocol===2&&(one.sentPages?.length!==part.endPage-part.startPage+1||one.sentPages?.some(p=>p<part.startPage||p>part.endPage)||(one.imageBlocks||0)>32))throw new Error('发送输入页记录不完整，尚未保存结果');
  const previous=report.analyses?.at(-1),old=previous?.batchId===batchId?previous:undefined;
  if(old?.accepted)throw new Error('该批结果已核对，请开始新的分析任务');
  const segments=[...(old?.batchSegments||[]),{cardId:job.cardId,startPage:part.startPage,endPage:part.endPage,summary:one.summary,notes:one.notes,...(one.sentPages?{sentPages:one.sentPages,imageBlocks:one.imageBlocks}:{}),...(one.reportDate?{reportDate:one.reportDate}:{})}];
  const metrics=[...(old?.metrics||[])];for(const metric of one.metrics)if(!metrics.some(m=>m.metricId===metric.metricId&&m.date===metric.date&&m.value===metric.value&&m.second===metric.second&&m.page===metric.page&&m.printedPage===metric.printedPage&&m.quote===metric.quote))metrics.push(metric);
  const cards=[...(old?.cards||[]).filter(c=>c.cardId!==job.cardId),...one.cards];
  const latestByCard=new Map<string,string>();for(const segment of segments)latestByCard.set(segment.cardId,segment.summary);
  const summary=Array.from([...latestByCard].map(([id,text])=>`【${s.cards.find(c=>c.id===id)?.name||'卡片'}】${text}`).join(' ')).slice(0,220).join('');
  const more=plan.jobs.slice(index+1).some(j=>j.parts.some(p=>p.reportId===report.id));
  const evidence=[...(old?.reportDate?[old.reportDate]:[]),...segments.flatMap(v=>v.reportDate?[v.reportDate]:[])];
  const inspections=evidence.filter(v=>v.source==='检验日期'),preferred=inspections.length?inspections:evidence;
  const conflict=new Set(preferred.map(v=>v.date)).size>1;
  const combined:ReportAnalysis={...one,...(one.examName||old?.examName?{examName:one.examName||old?.examName}:{}),id:old?.id||uid(),summary,metrics,cards,notes:[...new Set([...(old?.notes||[]),...one.notes])].slice(0,10),batchId,batchComplete:!more,batchSegments:segments};
  const reviewItems=mergeReviewItems(old?.reviewItems||[],one.reviewItems||[]);if(reviewItems.length)combined.reviewItems=reviewItems;else delete combined.reviewItems;
  const unread=[...(old?.readabilityIssues||[]),...(one.readabilityIssues||[])].filter((x,i,all)=>all.findIndex(v=>v.page===x.page&&v.reason===x.reason)===i);if(unread.length)combined.readabilityIssues=unread;else delete combined.readabilityIssues;
  if(segments.every(v=>v.sentPages&&v.imageBlocks)){combined.sentPages=[...new Set(segments.flatMap(v=>v.sentPages!))].sort((a,b)=>a-b);combined.imageBlocks=segments.reduce((sum,v)=>sum+v.imageBlocks!,0);}else{delete combined.sentPages;delete combined.imageBlocks;}
  if(conflict){delete combined.reportDate;combined.reportDateConflict=true;}else{delete combined.reportDateConflict;if(preferred.length)combined.reportDate=preferred[0];else delete combined.reportDate;}
  updates.set(report.id,combined);
 }
 return {...s,reports:s.reports.map(r=>{const analysis=updates.get(r.id);if(!analysis)return r;const previous=r.analyses?.at(-1);return {...r,status:'待确认',analysisError:undefined,analyses:previous?.batchId===batchId?[...r.analyses!.slice(0,-1),analysis]:[...(r.analyses||[]),analysis]};})};
}
export type BatchReview={reportId:string;analysisId:string;reportDate?:string;metrics:AiMetric[];issueDecisions?:IssueDecision[]};
export function acceptBatchReviews(s:HealthState,reviews:BatchReview[]):HealthState{
 if(!reviews.length)throw new Error('暂无可确认的完整结果');
 // The caller writes only after all reviews validate, so one invalid entry cannot cause a partial commit.
 return reviews.reduce((next,r)=>acceptReportAnalysis(next,r.reportId,r.analysisId,r.metrics,r.reportDate,r.issueDecisions),s);
}
