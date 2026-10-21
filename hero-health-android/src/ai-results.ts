import {parseReviewItems,resolveReviewItems,type ReviewItem,type IssueDecision} from './extraction-review';
import {acceptedReportName} from './report-name';
import {validateHealthFeatures} from './health-features';
import {today,validDate,uid,type HealthState,type Reading,type HealthCard} from './model';

export type AiMetric={metricId:string;value:number;second?:number;unit:string;date:string;page:number;quote:string;printedPage?:string;matchReason?:string;flag?:boolean};
export type AiCardNote={cardId:string;recent:string;trend:string;attention:string};
export type ReportDateEvidence={date:string;source:'检验日期'|'审核日期';page:number;quote:string;printedPage?:string};
export type ReadabilityIssue={page:number;reason:string};
export type ReportAnalysis={reviewItems?:ReviewItem[];reviewedIssues?:IssueDecision[];readabilityIssues?:ReadabilityIssue[];sentPages?:number[];imageBlocks?:number;examName?:string;reportDate?:ReportDateEvidence;reportDateConflict?:boolean;id:string;date:string;model:string;host:string;summary:string;metrics:AiMetric[];cards:AiCardNote[];notes:string[];pageCount:number;accepted?:boolean;reviewedMetrics?:AiMetric[];useCardNotes?:boolean;batchId?:string;batchComplete?:boolean;batchSegments?:{cardId:string;startPage:number;endPage:number;summary:string;notes:string[];reportDate?:ReportDateEvidence;sentPages?:number[];imageBlocks?:number}[]};
export type ReportSource={id:string;date:string;summary:string};
export type SummaryAnalysis={cardSources?:HealthCard[];id:string;date:string;model:string;host:string;revision:number;dataThrough:string;overview:string;assessment?:string;trends:{metricId:string;text:string}[];advice:string[];caveats:string[];readingIds:string[];reportIds:string[];sourceReadings:Reading[];reportSources:ReportSource[]};
export type AiReply={inputPageProtocol?:number;sentPages?:unknown;imageBlocks?:unknown;cardSources?:unknown;output:unknown;model:string;host:string;pageCount?:number;revision?:number;dataThrough?:string;readingIds?:string[];reportIds?:string[];sourceReadings?:unknown;reportSources?:unknown};
const object=(v:unknown):Record<string,any>=>{if(!v||typeof v!=='object'||Array.isArray(v))throw new Error('AI 结果不是有效对象，请重试');return v as Record<string,any>;};
const text=(v:unknown,max:number)=>{if(typeof v!=='string'||!v.trim()||v.length>max)throw new Error('AI 文本缺失或超长，请重试');return v.trim();};
const list=(v:unknown,max:number):any[]=>{if(!Array.isArray(v)||v.length>max)throw new Error('AI 列表格式无效，请重试');return v;};
const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v)&&Math.abs(v)<1e10;
function checkedMetric(value:unknown,s:HealthState,allowed:Set<string>,pages:number,allowUnknown=false):AiMetric{
 const v=object(value),m=s.metrics.find(x=>x.id===v.metricId);
 if(!m||!allowed.has(m.id)||m.unit!==v.unit)throw new Error('AI 返回未知指标或单位不一致，尚未写入指标，请核对卡片设置后重试');
 if(!finite(v.value)||!(validDate(v.date)||(allowUnknown&&v.date===''))||v.date>today()||!Number.isInteger(v.page)||v.page<1||v.page>pages)throw new Error('AI 数值、日期或来源页码无效，尚未写入指标');
 if(m.kind==='pressure'&&(!finite(v.second)||v.second<=0||v.value<=v.second))throw new Error('AI 血压双值无效，请重新分析或手工录入');
 return {metricId:m.id,value:v.value,...(m.kind==='pressure'?{second:v.second}:{}),unit:m.unit,date:v.date,page:v.page,quote:text(v.quote,200),...(v.printedPage!==undefined?{printedPage:text(v.printedPage,40)}:{}),...(v.matchReason!==undefined?{matchReason:text(v.matchReason,160)}:{}),...(typeof v.flag==='boolean'?{flag:v.flag}:{})};
}
function sourceSet(v:unknown,known:Set<string>){const values=list(v,1000);if(!values.every(x=>typeof x==='string'&&known.has(x)))throw new Error('AI 分析的来源记录已变化，请重新生成');return [...new Set(values)] as string[];}
export function checkedReportDate(value:unknown,pages:number):ReportDateEvidence{const d=object(value);if(!validDate(d.date)||d.date>today()||!['检验日期','审核日期'].includes(d.source)||!Number.isInteger(d.page)||d.page<1||d.page>pages)throw new Error('报告日期来源无效，请重新核对');return {date:d.date,source:d.source,page:d.page,quote:text(d.quote,200),...(d.printedPage!==undefined?{printedPage:text(d.printedPage,40)}:{})};}
export function checkedTransport(sent:unknown,blocks:unknown,pages:number){
 const values=list(sent,500);if(!values.length||new Set(values).size!==values.length||!values.every(v=>Number.isInteger(v)&&v>=1&&v<=pages)||!Number.isInteger(blocks)||(blocks as number)<values.length||(blocks as number)>320000)throw new Error('输入页发送记录无效，尚未保存结果');
 return {sentPages:[...values].sort((a,b)=>a-b) as number[],imageBlocks:blocks as number};
}
export function parseReportReply(reply:AiReply,s:HealthState,reportId:string,historical=false):ReportAnalysis{
 const output=object(reply.output),report=s.reports.find(x=>x.id===reportId);if(!report)throw new Error('报告不存在');
 const pageCount=reply.pageCount;if(!Number.isInteger(pageCount)||!pageCount||pageCount>500)throw new Error('报告页数无效');
 if(reply.inputPageProtocol===2&&!historical&&(!Array.isArray(output.reviewItems)||!Array.isArray(output.readabilityIssues)))throw new Error('AI 未完整返回待核对项目和可读性列表，请重新分析；尚未写入指标');
 const reportDate=output.reportDate?checkedReportDate(output.reportDate,pageCount):undefined;
 const linked=s.cards.filter(c=>report.cardIds.includes(c.id));const allowed=new Set(linked.flatMap(c=>c.metricIds));
 const metrics=list(output.metrics,3000).map(v=>checkedMetric(v,s,allowed,pageCount,true));
 const reviewItems=parseReviewItems(output.reviewItems,s,allowed,pageCount,historical);
 const readabilityIssues=list(output.readabilityIssues??[],500).map(v=>{const x=object(v);if(!Number.isInteger(x.page)||x.page<1||x.page>pageCount)throw new Error('可读性提示引用了无效输入页');return {page:x.page as number,reason:text(x.reason,240)};});
 const transport=reply.inputPageProtocol===2?checkedTransport(reply.sentPages,reply.imageBlocks,pageCount):undefined;
 if(transport&&[...metrics,...reviewItems,...readabilityIssues,...(reportDate?[reportDate]:[])].some(v=>!transport.sentPages.includes(v.page)))throw new Error('AI 引用了未发送的输入页，尚未写入档案');
 const cards=list(output.cards??[],100).map(v=>{const x=object(v);if(!linked.some(c=>c.id===x.cardId))throw new Error('AI 返回未关联的卡片');return {cardId:x.cardId as string,recent:text(x.recent,25),trend:text(x.trend,25),attention:text(x.attention,30)};});
 if(new Set(cards.map(c=>c.cardId)).size!==cards.length)throw new Error('AI 返回重复卡片摘要');
 return {...(transport||{}),...(reviewItems.length?{reviewItems}:{}),...(readabilityIssues.length?{readabilityIssues}:{}),...(output.examName!==undefined&&output.examName!==''?{examName:text(output.examName,80)}:{}),...(reportDate?{reportDate}:{}),id:uid(),date:new Date().toISOString(),model:text(reply.model,200),host:text(reply.host,255),summary:text(output.summary,220),metrics,cards,notes:list(output.notes??[],10).map(v=>text(v,180)),pageCount};
}
export function saveReportAnalysis(s:HealthState,id:string,analysis:ReportAnalysis):HealthState{
 if(!s.reports.some(r=>r.id===id))throw new Error('报告不存在');
 return {...s,reports:s.reports.map(r=>r.id===id?{...r,status:'待确认',analyses:[...(r.analyses||[]),analysis]}:r)};
}
export function acceptReportAnalysis(s:HealthState,id:string,analysisId:string,edited:AiMetric[],selectedReportDate?:string,issueDecisions?:IssueDecision[]):HealthState{
 const report=s.reports.find(r=>r.id===id),analysis=report?.analyses?.find(a=>a.id===analysisId);if(!report||!analysis)throw new Error('待核对结果不存在');if(analysis.accepted)return s;
 if(analysis.batchComplete===false)throw new Error('此报告的部分批次尚未完成，请继续分析后再确认');
 if(report.analyses?.at(-1)?.id!==analysisId)throw new Error('已有新的分析结果，请核对最新版本');
 if(analysis.reportDateConflict&&!selectedReportDate)throw new Error('日期证据冲突，请人工核对报告日期');const chosenDate=selectedReportDate||analysis.reportDate?.date||report.date;if(!validDate(chosenDate)||chosenDate>today())throw new Error('请先核对报告的检验或审核日期');
 const allowed=new Set(s.cards.filter(c=>report.cardIds.includes(c.id)).flatMap(c=>c.metricIds));
 const resolved=resolveReviewItems(analysis.reviewItems||[],issueDecisions,v=>checkedMetric(v,s,allowed,analysis.pageCount));
 const metrics=[...edited.map(v=>checkedMetric(v,s,allowed,analysis.pageCount)),...resolved.metrics];
 const unchanged=!(analysis.reviewItems?.some(v=>v.category==='review'))&&!analysis.reportDateConflict&&(!selectedReportDate||!analysis.reportDate||selectedReportDate===analysis.reportDate.date)&&metrics.length===analysis.metrics.length&&metrics.every((m,i)=>{const original=analysis.metrics[i];return m.metricId===original.metricId&&m.value===original.value&&m.second===original.second&&m.date===original.date&&m.unit===original.unit&&m.flag===original.flag;});
 const additions:Reading[]=[];
 for(const [index,m]of metrics.entries()){
  const duplicate=[...s.readings,...additions].some(r=>r.reportId===id&&r.metricId===m.metricId&&r.date===m.date&&r.value===m.value&&r.second===m.second);
  if(!duplicate)additions.push({id:`ai:${analysis.id}:${index}`,metricId:m.metricId,value:m.value,...(m.second!==undefined?{second:m.second}:{}),date:m.date,source:'AI 提取 · 已核对',reportId:id,sourcePage:m.page,sourceQuote:m.quote,...(m.printedPage?{sourcePrintedPage:m.printedPage}:{}),...(m.flag!==undefined?{flag:m.flag}:{})});
 }
 return {...s,revision:s.revision+1,readings:[...s.readings,...additions],reports:s.reports.map(r=>r.id===id?{...r,name:acceptedReportName(analysis.examName,chosenDate,r.file?.name||r.name,r.file?.mime),date:chosenDate,dateSource:selectedReportDate?'人工核对':analysis.reportDate?.source||r.dateSource,status:'已分析',summary:unchanged?analysis.summary:'报告指标已手工核对，部分数据经调整；AI 原摘要仅供对照，请以核对指标和原件为准。',analyzedAt:analysis.date,analyses:r.analyses!.map(a=>a.id===analysisId?{...a,...(analysis.reviewItems?.length?{reviewedIssues:resolved.decisions}:{}),reviewedMetrics:metrics,useCardNotes:unchanged,accepted:true}:a)}:r)};
}
export function parseSummaryReply(reply:AiReply,s:HealthState):SummaryAnalysis{
 const o=object(reply.output);let cardSources:HealthCard[]|undefined;if(reply.cardSources!==undefined){cardSources=list(reply.cardSources,1000).map(v=>{const c=object(v);if(!s.cards.some(x=>x.id===c.id)||typeof c.name!=='string'||typeof c.description!=='string'||!Array.isArray(c.metricIds)||!c.metricIds.every((id:unknown)=>s.metrics.some(m=>m.id===id)))throw new Error('卡片背景快照无效');return {id:c.id,name:c.name,description:c.description,...(c.patientBackground!==undefined?{patientBackground:c.patientBackground}:{}),metricIds:c.metricIds,...(c.medications?{medications:c.medications}:{})};});validateHealthFeatures({...s,reports:[],cards:cardSources,chatTopics:undefined,activeChatTopicId:undefined});}
 const readingIds=sourceSet(reply.readingIds,new Set(s.readings.map(r=>r.id))),reportIds=sourceSet(reply.reportIds,new Set(s.reports.map(r=>r.id)));
 if(!Number.isInteger(reply.revision)||(reply.revision??-1)<0||typeof reply.dataThrough!=='string'||!validDate(reply.dataThrough)||(!readingIds.length&&!reportIds.length))throw new Error('AI 分析缺少有效资料范围');
 const sourceReadings=list(reply.sourceReadings,600).map(v=>{const x=object(v);if(!readingIds.includes(x.id)||!s.metrics.some(m=>m.id===x.metricId)||!finite(x.value)||!validDate(x.date)||(x.second!==undefined&&!finite(x.second))||(x.reportId!==undefined&&!s.reports.some(r=>r.id===x.reportId))||(x.sourcePage!==undefined&&(!Number.isInteger(x.sourcePage)||x.sourcePage<1)))throw new Error('综合分析指标快照无效');return {id:x.id as string,metricId:x.metricId as string,value:x.value,date:x.date as string,source:typeof x.source==='string'?x.source:'生成时的指标记录',...(x.second!==undefined?{second:x.second as number}:{}),...(x.reportId?{reportId:x.reportId as string}:{}),...(x.sourcePage?{sourcePage:x.sourcePage as number}:{}),...(x.sourcePrintedPage!==undefined?{sourcePrintedPage:text(x.sourcePrintedPage,40)}:{}),...(typeof x.flag==='boolean'?{flag:x.flag}:{})};});
 const reportSources=list(reply.reportSources,20).map(v=>{const x=object(v);if(!reportIds.includes(x.id)||!validDate(x.date))throw new Error('综合分析报告快照无效');return {id:x.id as string,date:x.date as string,summary:text(x.summary,10000)};});
 if(sourceReadings.length!==readingIds.length||new Set(sourceReadings.map(r=>r.id)).size!==readingIds.length||reportSources.length!==reportIds.length||new Set(reportSources.map(r=>r.id)).size!==reportIds.length)throw new Error('综合分析快照来源不完整');
 const metricIds=new Set(sourceReadings.map(r=>r.metricId));
 const trends=list(o.trends,3).map(v=>{const x=object(v);if(!metricIds.has(x.metricId))throw new Error('AI 趋势缺少指标依据');return {metricId:x.metricId as string,text:text(x.text,120)};});
 return {...(cardSources?{cardSources:structuredClone(cardSources)}:{}),id:uid(),date:new Date().toISOString(),model:text(reply.model,200),host:text(reply.host,255),revision:reply.revision!,dataThrough:reply.dataThrough,readingIds,reportIds,sourceReadings,reportSources,overview:text(o.overview,100),...(o.assessment!==undefined?{assessment:text(o.assessment,400)}:{}),trends,advice:list(o.advice,3).map(v=>text(v,120)),caveats:list(o.caveats??[],3).map(v=>text(v,120))};
}
/** Validate optional versioned AI data when restoring archives, including older schema-1 archives. */
export function validateAiArchive(s:HealthState){
 for(const r of s.reports){if(r.analyses===undefined)continue;const ids=new Set<string>();for(const a of list(r.analyses,10000)){
  if(typeof a.id!=='string'||ids.has(a.id)||!Number.isFinite(Date.parse(a.date))||(a.accepted!==undefined&&typeof a.accepted!=='boolean')||(a.useCardNotes!==undefined&&typeof a.useCardNotes!=='boolean'))throw new Error('AI 报告历史损坏');ids.add(a.id);
  if(a.reviewedMetrics!==undefined)for(const m of list(a.reviewedMetrics,3000))checkedMetric(m,s,new Set(s.metrics.map(x=>x.id)),a.pageCount);
  if(a.reviewedIssues!==undefined){if(!a.accepted)throw new Error('未确认分析不能保存核对决定');resolveReviewItems(a.reviewItems||[],a.reviewedIssues,v=>checkedMetric(v,s,new Set(s.metrics.map(m=>m.id)),a.pageCount));}
  if(a.reportDateConflict!==undefined&&typeof a.reportDateConflict!=='boolean')throw new Error('报告日期核对状态损坏');
  if(a.batchId!==undefined&&typeof a.batchId!=='string'||a.batchComplete!==undefined&&typeof a.batchComplete!=='boolean')throw new Error('批量分析历史损坏');
  if(a.batchSegments!==undefined)for(const v of list(a.batchSegments,10000)){const segment=object(v);if(!s.cards.some(c=>c.id===segment.cardId)||!Number.isInteger(segment.startPage)||!Number.isInteger(segment.endPage)||segment.startPage<1||segment.endPage<segment.startPage||segment.endPage>a.pageCount)throw new Error('批量来源页码损坏');if(segment.reportDate){const evidence=checkedReportDate(segment.reportDate,a.pageCount);if(evidence.page<segment.startPage||evidence.page>segment.endPage)throw new Error('报告日期证据不属于保存分段');}if(segment.sentPages!==undefined){const t=checkedTransport(segment.sentPages,segment.imageBlocks,a.pageCount);if(t.sentPages.length!==segment.endPage-segment.startPage+1||t.sentPages.some(p=>p<segment.startPage||p>segment.endPage))throw new Error('发送页记录与来源分段不一致');}text(segment.summary,220);list(segment.notes,10).forEach(n=>text(n,180));}
  // Historical cards may have different associations now; validate against all existing cards.
  parseReportReply({inputPageProtocol:a.sentPages!==undefined?2:undefined,sentPages:a.sentPages,imageBlocks:a.imageBlocks,output:{reviewItems:a.reviewItems,readabilityIssues:a.readabilityIssues,examName:a.examName,summary:a.summary,metrics:a.metrics,cards:a.cards,notes:a.notes,reportDate:a.reportDate},model:a.model,host:a.host,pageCount:a.pageCount},{...s,cards:s.cards.map(c=>({...c,metricIds:s.metrics.map(m=>m.id)})),reports:s.reports.map(x=>x.id===r.id?{...x,cardIds:s.cards.map(c=>c.id)}:x)},r.id,true);
 }}
 if(s.aiSummaries!==undefined){const ids=new Set<string>();for(const a of list(s.aiSummaries,10000)){
  if(typeof a.id!=='string'||ids.has(a.id)||!Number.isFinite(Date.parse(a.date)))throw new Error('AI 综合分析历史损坏');ids.add(a.id);parseSummaryReply({output:a,model:a.model,host:a.host,revision:a.revision,dataThrough:a.dataThrough,readingIds:a.readingIds,reportIds:a.reportIds,sourceReadings:a.sourceReadings,reportSources:a.reportSources,cardSources:a.cardSources},s);
 }}
}
