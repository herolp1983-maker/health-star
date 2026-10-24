import {validateAiArchive,type ReportAnalysis,type SummaryAnalysis} from './ai-results';
import type {BatchPlan} from './ai-batch';
import {validateHealthFeatures} from './health-features';
export type MetricDef = { id: string; name: string; unit: string; kind: 'number' | 'pressure'; icon: string };
export type Reading = { id: string; metricId: string; value: number; second?: number; date: string; source: string; reportId?: string; note?: string; flag?: boolean; sourcePage?:number; sourceQuote?:string; sourcePrintedPage?:string };
export type Medication={id:string;name:string;dose:string;frequency:string;startDate:string;endDate?:string;status:'在用'|'已停用';note:string};
export type ChatImage={name:string;mime:string;dataUrl:string};
export type ChatTurn={id:string;user:string;assistant?:string;createdAt:number;completedAt?:number;status:'pending'|'done'|'failed';image?:ChatImage;cardNames?:string[];contextRevision?:number;model?:string;host?:string};
export type ChatTopic={id:string;createdAt:number;lastActivityAt:number;turns:ChatTurn[]};
export type HealthCard = { id: string; name: string; description: string; patientBackground?: string; metricIds: string[]; archived?: boolean;medications?:Medication[] };
export type HealthReport = { id: string; name: string; date: string; dateSource?:'检验日期'|'审核日期'|'人工核对'|'待确认';uploadedAt?:string; institution: string; analysisError?:string; status: '未分析' | '分析中' | '已分析' | '待确认' | '失败'; cardIds: string[]; demo?: boolean; file?: { name: string; mime: string; dataUrl: string; id?: string; sha256?: string }; summary?: string; analyzedAt?: string; analyses?:ReportAnalysis[] };
export type BatchProgress={id:string;plan:BatchPlan;nextIndex:number;sourceDigest:string};
export type HealthState = { schema: 1; revision: number; metrics: MetricDef[]; readings: Reading[]; cards: HealthCard[]; reports: HealthReport[]; batchProgress?:BatchProgress; homeMetricIds?: string[]; summary?: { revision: number; date: string }; aiSummaries?:SummaryAnalysis[]; chatTopics?:ChatTopic[];activeChatTopicId?:string; settings: { endpoint: string; model: string; summaryPrompt?:string }; lastBackup?: string };
export const today=()=>{const date=new Date();return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;};
export function validDate(s:string){if(!/^\d{4}-\d{2}-\d{2}$/.test(s))return false;const date=new Date(`${s}T12:00:00Z`);return Number.isFinite(date.getTime())&&date.toISOString().slice(0,10)===s;}
export const uid = () => crypto.randomUUID();
export const shortDate = (date: string) => date.slice(5).replace('-', '/');
export const initialState = ():HealthState => ({schema:1,revision:0,metrics:[{id:'height',name:'身高',unit:'cm',kind:'number',icon:'chart'},{id:'weight',name:'体重',unit:'kg',kind:'number',icon:'scale'},{id:'pressure',name:'血压',unit:'mmHg',kind:'pressure',icon:'heart'},{id:'glucose',name:'空腹血糖',unit:'mmol/L',kind:'number',icon:'drop'},{id:'ldl',name:'LDL-C',unit:'mmol/L',kind:'number',icon:'drop'},{id:'pulse',name:'静息心率',unit:'次/分',kind:'number',icon:'heart'}],cards:[basicCard()],readings:[],reports:[],homeMetricIds:['weight','pressure'],settings:{endpoint:'',model:''}});
export const readingsFor = (state: HealthState,id:string) => state.readings.filter(r=>r.metricId===id).sort((a,b)=>a.date.localeCompare(b.date));
export const latest = (state:HealthState,id:string) => readingsFor(state,id).at(-1);
export const BASIC_CARD_ID='basic';
/** Called only while opening an archive; it never resends an interrupted request. */
export function recoverInterruptedAnalyses(state:HealthState):HealthState {
  if(!state.reports.some(r=>r.status==='分析中'))return state;
  return {...state,reports:state.reports.map(r=>r.status==='分析中'?{...r,status:r.analyses?.at(-1)?.batchComplete!==false&&r.analyses?.at(-1)&&!r.analyses.at(-1)!.accepted?'待确认':'失败',analysisError:'上次分析已中断，已保存的结果保留；请确认后手动重试。'}:r)};
}
export function basicCard():HealthCard {return {id:BASIC_CARD_ID,name:'基本信息',description:'身高、体重与血压，记录身体的基础变化。',metricIds:['height','weight','pressure'],archived:false};}
/** Upgrade old local archives and enforce the fixed card without changing historical readings. */
export function normalizeState(state:HealthState):HealthState {
  const defaults:MetricDef[]=[{id:'height',name:'身高',unit:'cm',kind:'number',icon:'chart'},{id:'weight',name:'体重',unit:'kg',kind:'number',icon:'scale'},{id:'pressure',name:'血压',unit:'mmHg',kind:'pressure',icon:'heart'}];
  return {...state,metrics:[...state.metrics,...defaults.filter(m=>!state.metrics.some(x=>x.id===m.id))],cards:[{...basicCard(),...(state.cards.find(c=>c.id===BASIC_CARD_ID)?.patientBackground!==undefined?{patientBackground:state.cards.find(c=>c.id===BASIC_CARD_ID)!.patientBackground}:{})},...state.cards.filter(c=>c.id!==BASIC_CARD_ID)]};
}
export const trackedIds = (state:HealthState) => [...new Set(state.cards.filter(c=>!c.archived).flatMap(c=>c.metricIds))].filter(id=>state.metrics.some(m=>m.id===id));
export const homeIds = (state:HealthState) => trackedIds(state).filter(id=>state.homeMetricIds===undefined||state.homeMetricIds.includes(id));
export function setCardArchived(state:HealthState,id:string,archived:boolean):HealthState {
  if(id===BASIC_CARD_ID)throw new Error('基本信息不能归档');
  const card=state.cards.find(c=>c.id===id);if(!card)throw new Error('健康卡片不存在');
  if(!!card.archived===archived)return state;
  return {...state,revision:state.revision+1,cards:state.cards.map(c=>c.id===id?{...c,archived}:c)};
}

export type MetricChange={label:string;direction:'up'|'down'|'flat'|'none';delta?:number};
export function metricChanges(state:HealthState,id:string):MetricChange[]{
  const rows=readingsFor(state,id),r=rows.at(-1),p=rows.at(-2),m=state.metrics.find(m=>m.id===id);
  const change=(label:string,a?:number,b?:number):MetricChange=>a===undefined||b===undefined?{label,direction:'none'}:{label,direction:a>b?'up':a<b?'down':'flat',delta:Number(Math.abs(a-b).toFixed(2))};
  return m?.kind==='pressure'?[change('收',r?.value,p?.value),change('舒',r?.second,p?.second)]:[change('',r?.value,p?.value)];
}
export function cardDigest(state:HealthState,card:HealthCard){
  const measured=card.metricIds.map(id=>({m:state.metrics.find(m=>m.id===id)!,r:latest(state,id)})).filter(x=>x.m);
  const present=measured.filter(x=>x.r),flagged=present.find(x=>x.r?.flag),date=present.map(x=>x.r!.date).sort().at(-1);
  const pending=state.reports.some(r=>r.cardIds.includes(card.id)&&r.status==='待确认');
  const analyzed=[...state.reports].filter(r=>r.cardIds.includes(card.id)).sort((a,b)=>b.date.localeCompare(a.date)).flatMap(r=>[...(r.analyses||[])].reverse().filter(a=>a.accepted&&a.useCardNotes!==false));
  const aiNote=analyzed.flatMap(a=>a.cards).find(c=>c.cardId===card.id);
  if(aiNote)return {recent:aiNote.recent,trend:aiNote.trend,attention:pending?'先校对待确认报告。':aiNote.attention};
  const trends=present.filter(x=>readingsFor(state,x.m.id).length>1).slice(0,2).map(x=>{
    const changes=metricChanges(state,x.m.id),directions=new Set(changes.map(t=>t.direction));
    return `${x.m.name.slice(0,8)}${directions.size>1?'有升有降':changes[0].direction==='up'?'上升':changes[0].direction==='down'?'下降':'持平'}`;
  });
  return {recent:flagged?`${flagged.m.name.slice(0,10)}有报告异常标记。`:date?`最近记录于${shortDate(date)}，已记录${present.length}项。`:'暂无记录，等待首次测量。',trend:trends.length?`${trends.join('，')}。`:'记录不足，暂不判断趋势。',attention:pending?'先校对待确认报告。':flagged?'复查时对照原报告，向医生咨询。':present.length<measured.length?'补充未记录指标，保持测量条件一致。':'持续记录，复查时对照历史数据。'};
}
export function associateImport(state:HealthState,report:HealthReport,cardId:string):HealthState {
  if(!state.cards.some(c=>c.id===cardId&&!c.archived))throw new Error('请先选择一张正在关注的健康卡片');
  return {...state,reports:[...state.reports,{...report,cardIds:[cardId]}]};
}
export function validateState(value:unknown,allowLocalFiles=false): asserts value is HealthState {
  if(!value||typeof value!=='object')throw new Error('备份内容无效');
  const s=value as HealthState;
  if(s.schema!==1)throw new Error('不支持此备份版本');
  if(!Array.isArray(s.metrics)||!Array.isArray(s.cards)||!Array.isArray(s.readings)||!Array.isArray(s.reports)||!s.settings||!Number.isInteger(s.revision))throw new Error('备份结构不完整');
  const ids=new Set<string>();
  for(const m of s.metrics){if(!m||typeof m.id!=='string'||ids.has(m.id)||typeof m.name!=='string'||!m.name.trim()||typeof m.unit!=='string'||!['number','pressure'].includes(m.kind))throw new Error('指标定义损坏');ids.add(m.id);}
  const cardIds=new Set<string>();for(const c of s.cards){if(!c||typeof c.id!=='string'||cardIds.has(c.id)||typeof c.name!=='string'||!Array.isArray(c.metricIds)||!c.metricIds.every(id=>ids.has(id)))throw new Error('卡片数据损坏');cardIds.add(c.id);}
  if(s.homeMetricIds!==undefined&&(!Array.isArray(s.homeMetricIds)||!s.homeMetricIds.every(id=>typeof id==='string'&&ids.has(id))))throw new Error('首页显示配置损坏');
  const reportIds=new Set<string>();for(const r of s.reports){if(!r||typeof r.id!=='string'||reportIds.has(r.id)||typeof r.name!=='string'||!(r.date===''||validDate(r.date))||!Array.isArray(r.cardIds)||!r.cardIds.every(id=>cardIds.has(id))||!['未分析','分析中','已分析','待确认','失败'].includes(r.status))throw new Error('报告数据损坏');reportIds.add(r.id);if(r.file&&(!['image/png','image/jpeg','image/webp','application/pdf'].includes(r.file.mime)||!(typeof r.file.dataUrl==='string'&&(r.file.dataUrl.startsWith(`data:${r.file.mime};base64,`)||(allowLocalFiles&&r.file.id&&r.file.dataUrl===`https://app.hero.local/reports/${r.file.id}`)))))throw new Error('报告附件无效');}
  if(s.batchProgress!==undefined){const p=s.batchProgress,plan=p?.plan;
    if(!p||typeof p.id!=='string'||!p.id||typeof p.sourceDigest!=='string'||!/^[0-9a-f]{64}$/.test(p.sourceDigest)||!plan||!Array.isArray(plan.jobs)||!plan.jobs.length||plan.jobs.length>10000||!Array.isArray(plan.reportIds)||!Array.isArray(plan.cardIds)||!Array.isArray(plan.problems)||!Number.isInteger(p.nextIndex)||p.nextIndex<0||p.nextIndex>=plan.jobs.length)throw new Error('批量分析进度损坏');
     for(const job of plan.jobs){if(!job||!cardIds.has(job.cardId)||!Array.isArray(job.parts)||!job.parts.length||job.parts.length>3||job.parts.some(part=>!part)||job.parts.reduce((n,part)=>n+(part.endPage-part.startPage+1),0)>8)throw new Error('批量分析任务损坏');
      for(const part of job.parts)if(!part||!reportIds.has(part.reportId)||!s.reports.find(r=>r.id===part.reportId)?.cardIds.includes(job.cardId)||!Number.isInteger(part.startPage)||!Number.isInteger(part.endPage)||!Number.isInteger(part.pageCount)||part.startPage<1||part.endPage<part.startPage||part.endPage>part.pageCount||part.pageCount>500)throw new Error('批量分析页码损坏');
    }
  }
  for(const r of s.reports)if(r.analysisError!==undefined&&(typeof r.analysisError!=='string'||r.analysisError.length>600))throw new Error('报告分析错误提示损坏');
  const readingIds=new Set<string>();for(const r of s.readings){if(!r||!ids.has(r.metricId)||typeof r.id!=='string'||readingIds.has(r.id)||!Number.isFinite(r.value)||(r.second!==undefined&&!Number.isFinite(r.second))||!validDate(r.date)||(r.reportId&&!reportIds.has(r.reportId)))throw new Error('指标记录损坏');readingIds.add(r.id);}
  if(s.settings.summaryPrompt!==undefined&&(typeof s.settings.summaryPrompt!=='string'||s.settings.summaryPrompt.length>12000))throw new Error('综合分析提示词损坏');
  for(const r of s.readings)if(r.sourcePrintedPage!==undefined&&(typeof r.sourcePrintedPage!=='string'||!r.sourcePrintedPage.trim()||r.sourcePrintedPage.length>40))throw new Error('指标印刷页码损坏');
  validateAiArchive(s);
  validateHealthFeatures(s);
  // Secrets are never restored, including from packages created outside this app.
  s.settings={endpoint:typeof s.settings.endpoint==='string'?s.settings.endpoint:'',model:typeof s.settings.model==='string'?s.settings.model:'',...(s.settings.summaryPrompt!==undefined?{summaryPrompt:s.settings.summaryPrompt}:{})};
}
