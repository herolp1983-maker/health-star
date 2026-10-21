import {useState} from 'react';
import config from '../public/config/summary-prompt.json';
import {useApp} from './app-context';
import {KeyboardTextarea,useKeyboard} from './mobile';
import {Button} from './ui';
export default function SummaryPromptSettings(){
 const {data,commit,notify}=useApp(),keyboard=useKeyboard();
 const [draft,setDraft]=useState(data.settings.summaryPrompt||config.defaultPrompt),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const save=async()=>{keyboard.hide();if(!draft.trim()||draft.length>12000){setError('提示词请填写1至12000个字符');return;}setBusy(true);setError('');try{const prompt=draft.trim()===config.defaultPrompt?'':draft.trim();await commit(s=>({...s,revision:s.revision+1,settings:{...s.settings,summaryPrompt:prompt}}));notify('综合分析提示词已保存，下次生成生效');}catch{setError('保存失败，请重试');}finally{setBusy(false);}};
 return <div className="hh-form"><p className="intro-copy">设置综合分析的关注重点、解释方式和建议风格。只影响此后的综合报告；旧报告保留。</p><label className="form-field"><span>AI 综合分析提示词</span><KeyboardTextarea rows={16} maxLength={12000} value={draft} disabled={busy} onChange={e=>setDraft(e.target.value)} aria-label="AI 综合分析提示词"/></label><p className="small muted">{draft.length} / 12000 · 输出格式、来源约束与用药安全规则由应用固定保留。提示词及病情背景随加密备份导出，API Key 不包含在内。</p><Button disabled={busy} onClick={()=>void save()}>{busy?'保存中…':'保存提示词'}</Button><Button secondary disabled={busy} onClick={()=>{keyboard.hide();setDraft(config.defaultPrompt);setError('');}}>恢复默认（保存后生效）</Button>{error&&<p className="form-error" role="alert">{error}</p>}</div>;
}
