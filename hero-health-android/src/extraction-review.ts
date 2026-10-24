import {uid,validDate,today,type HealthState} from './model';
import type {AiMetric} from './ai-results';
export type ReviewItem={id:string;category:'review'|'unmatched';name:string;value:string;unit:string;date:string;page:number;printedPage?:string;quote:string;reason:string;candidateIds:string[]};
export type IssueDecision={issueId:string;action:'skip'}|{issueId:string;action:'mapped';metric:AiMetric};
const str=(v:unknown,max:number,empty=false)=>{if(typeof v!=='string'||v.length>max||(!empty&&!v.trim()))throw new Error('待核对项目文本损坏');return v.trim();};
export function parseReviewItems(value:unknown,s:HealthState,allowed:Set<string>,pages:number,preserveIds=false):ReviewItem[]{
 if(value===undefined)return [];if(!Array.isArray(value)||value.length>3000)throw new Error('待核对项目格式无效');const ids=new Set<string>();
 return value.map(v=>{if(!v||typeof v!=='object'||!['review','unmatched'].includes(v.category)||!Number.isInteger(v.page)||v.page<1||v.page>pages)throw new Error('待核对项目类型或输入页码无效');
  const id=preserveIds?str(v.id,100):uid();if(ids.has(id))throw new Error('待核对项目ID重复');ids.add(id);
  const candidates=v.candidateIds??[];if(!Array.isArray(candidates)||candidates.length>100||!candidates.every((id:unknown)=>typeof id==='string'&&allowed.has(id)&&s.metrics.some(m=>m.id===id)))throw new Error('待核对项目引用未知指标');
  const date=v.date??'';if(typeof date!=='string'||(date!==''&&(!validDate(date)||date>today())))throw new Error('待核对项目日期无效');
  return {id,category:v.category,name:str(v.name,150),value:str(typeof v.value==='number'&&Number.isFinite(v.value)?String(v.value):v.value,100),unit:str(v.unit??'',100,true),date,page:v.page,...(v.printedPage!==undefined?{printedPage:str(v.printedPage,40)}:{}),quote:str(v.quote,200),reason:str(v.reason,240),candidateIds:[...new Set(candidates)] as string[]};
 });
}
export function mergeReviewItems(old:ReviewItem[],fresh:ReviewItem[]):ReviewItem[]{
 const result=structuredClone(old);
 for(const item of fresh){const same=result.find(v=>v.name===item.name&&v.value===item.value&&v.unit===item.unit&&v.date===item.date&&v.page===item.page&&v.printedPage===item.printedPage&&v.quote===item.quote);if(same){same.candidateIds=[...new Set([...same.candidateIds,...item.candidateIds])];if(item.category==='review')same.category='review';}else result.push(item);}
 return result;
}
export function resolveReviewItems(items:ReviewItem[],decisions:IssueDecision[]|undefined,check:(metric:unknown)=>AiMetric):{decisions:IssueDecision[];metrics:AiMetric[]}{
 const input=decisions??[];if(!Array.isArray(input)||input.length!==items.length)throw new Error('请逐项处理待确认和未匹配项目，选择归属或明确跳过');
 const seen=new Set<string>(),metrics:AiMetric[]=[],clean:IssueDecision[]=[];
 for(const d of input){const item=items.find(v=>v.id===d?.issueId);if(!item||seen.has(d.issueId))throw new Error('待核对处理结果已变化，请重新核对');seen.add(d.issueId);
  if(d.action==='skip'){clean.push({issueId:d.issueId,action:'skip'});continue;}
  if(d.action!=='mapped'||!d.metric)throw new Error('请选择待核对项目的处理方式');
  const metric=check({...d.metric,page:item.page,quote:item.quote,printedPage:item.printedPage});metrics.push(metric);clean.push({issueId:d.issueId,action:'mapped',metric});
 }
 return {decisions:clean,metrics};
}

export type IssueDraft={id:string;action:''|'map'|'skip';metricId:string;value:string;second:string;date:string};
export const makeIssueDrafts=(items:ReviewItem[]=[]):IssueDraft[]=>items.map(v=>({id:v.id,action:v.category==='unmatched'?'skip':'',metricId:'',value:'',second:'',date:v.date}));
export function decisionsFromDrafts(items:ReviewItem[],drafts:IssueDraft[],s:HealthState,reportDate:string):IssueDecision[]{
 return items.map(item=>{const d=drafts.find(v=>v.id===item.id);if(!d?.action)throw new Error('请逐项处理待确认和未匹配项目，选择归属或明确跳过');if(d.action==='skip')return {issueId:item.id,action:'skip'};
  const m=s.metrics.find(v=>v.id===d.metricId);if(!m||!d.value.trim()||(m.kind==='pressure'&&!d.second.trim()))throw new Error('请为待核对项目选择指标并填写完整数值');
  return {issueId:item.id,action:'mapped',metric:{metricId:m.id,value:Number(d.value),...(m.kind==='pressure'?{second:Number(d.second)}:{}),unit:m.unit,date:d.date||reportDate,page:item.page,quote:item.quote,...(item.printedPage?{printedPage:item.printedPage}:{})}};
 });
}

export type MatchedDraft={metric:AiMetric;selected:boolean;value:string;second:string;date:string;dateEdited?:boolean};
/** Only inherited dates follow a report-date correction; distinct/manual dates remain intact. */
export function shiftMatchedDates(rows:MatchedDraft[],previous:string,next:string):MatchedDraft[]{
 return rows.map(d=>!d.dateEdited&&(!d.date||d.date===previous)?{...d,date:next}:d);
}
