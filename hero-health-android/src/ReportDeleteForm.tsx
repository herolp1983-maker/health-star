import {useRef,useState} from 'react';
import {useApp} from './app-context';
import {deleteReport,reportDeletionImpact} from './report-workflow';
import {Button} from './ui';
export default function ReportDeleteForm({id}:{id:string}){
 const {data,commit,open,notify,setCritical}=useApp();
 const [busy,setBusy]=useState(false),[error,setError]=useState('');const running=useRef(false);
 const report=data.reports.find(r=>r.id===id);if(!report)return <p>此报告已删除。</p>;
 const impact=reportDeletionImpact(data,id);
 const remove=async()=>{if(running.current)return;running.current=true;setBusy(true);setCritical(true);setError('');try{await commit(s=>deleteReport(s,id));open(null);notify('报告及关联指标已删除，首页和趋势已更新');}catch{setError('删除失败，原档案未被覆盖，请重试');}finally{running.current=false;setBusy(false);setCritical(false);}};
 return <><h3>{report.name}</h3><div className="inline-notice warning"><span>将删除这份报告原件及分析历史、{impact.readings} 条关联指标记录、{impact.summaryIds.size} 份引用这些资料的综合分析。其他报告、独立记录和健康卡片保留。删除不可撤销。</span></div><Button disabled={busy} onClick={()=>void remove()}>{busy?'正在删除…':'确认删除报告及关联记录'}</Button><Button secondary disabled={busy} onClick={()=>open(null)}>取消</Button>{error&&<p className="form-error" role="alert">{error}</p>}</>;
}
