import {useEffect,useState} from 'react';
import {EyeOpenIcon,EyeClosedIcon,LockClosedIcon,CheckCircledIcon,ReloadIcon} from '@radix-ui/react-icons';
import {readAiConfig,saveAiConfig,clearAiKey,type AiConfig} from './ai-config';
import {Button,Field} from './ui';
import {KeyboardInput} from './mobile';
import {useApp} from './app-context';
import {nativeCall} from './native';

export default function AISettings(){
 const {notify}=useApp();
 const [saved,setSaved]=useState<AiConfig>(),[endpoint,setEndpoint]=useState(''),[model,setModel]=useState(''),[newKey,setNewKey]=useState('');
 const [visible,setVisible]=useState(false),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState(''),[confirmClear,setConfirmClear]=useState(false);
 const [testing,setTesting]=useState(false),[testResult,setTestResult]=useState('');
 const apply=(config:AiConfig)=>{setSaved(config);setEndpoint(config.endpoint);setModel(config.model);setNewKey('');setVisible(false);setConfirmClear(false);};
 const load=async()=>{setLoading(true);setError('');try{apply(await readAiConfig());}catch{setError('无法读取安全配置，请重试。现有配置未被覆盖。');}finally{setLoading(false);}};
 useEffect(()=>{void load();},[]);
 // The transient input is never persisted in React app state, history, URLs or browser storage.
 useEffect(()=>{const hide=()=>{setVisible(false);setNewKey('');};document.addEventListener('visibilitychange',hide);return()=>document.removeEventListener('visibilitychange',hide);},[]);
 const changedAddress=!!saved?.hasKey&&endpoint.trim().replace(/\/+$/,'')!==saved.endpoint;
 const dirty=!!saved&&(endpoint.trim()!==saved.endpoint||model.trim()!==saved.model||newKey.length>0);
 const save=async()=>{setBusy(true);setError('');try{const config=await saveAiConfig(endpoint,model,newKey);apply(config);notify(config.hasKey?'AI 配置已安全保存':'服务配置已保存，尚未设置密钥');}catch(e){setError(e instanceof Error?e.message:'配置保存失败，请重试');}finally{setBusy(false);}};
 const clear=async()=>{setBusy(true);setError('');try{apply(await clearAiKey());notify('已清除 API Key');}catch{setError('清除失败，请重试。现有配置未被覆盖。');}finally{setBusy(false);}};
 const test=async()=>{if(!saved?.hasKey)return;setBusy(true);setTesting(true);setError('');setTestResult('');try{await nativeCall('testAiConnection',{endpoint:saved.endpoint,model:saved.model});setTestResult('对话连接成功。报告识别还需模型支持图片输入，并按提示返回结构化结果。');notify('AI 服务连接成功');}catch(e){setError(e instanceof Error?e.message:'连接测试失败，请检查配置');}finally{setBusy(false);setTesting(false);}};
 return <>
  <section className="ai-config-hero"><span className="large-symbol"><LockClosedIcon/></span><div><h2>AI 服务配置</h2><p>服务地址、模型和密钥，由你维护</p></div></section>
  {loading?<p className="empty-inline" role="status">正在读取安全配置…</p>:<>
   {saved&&<section className="surface ai-config-surface">
    <div className="ai-config-status"><span className={`badge ${saved.hasKey?'success':''}`}><CheckCircledIcon/>{saved.hasKey?'密钥已安全保存':'尚未设置密钥'}</span><small>{dirty?'有未保存的修改':'本机配置'}</small></div>
    <form className="hh-form" onSubmit={e=>{e.preventDefault();if(!busy)void save();}} autoComplete="off">
     <Field label="服务地址（HTTPS）" value={endpoint} onChange={setEndpoint} placeholder="https://你的服务地址/v1" type="url" disabled={busy}/>
     <p className="field-help">支持 OpenAI 兼容 Chat Completions 接口。填写 API 基础地址，不含密钥或查询参数。</p>
     <Field label="模型名称" value={model} onChange={setModel} placeholder="填写服务商提供的模型 ID" disabled={busy}/>
     <label className="form-field"><span>API Key{saved.hasKey?' · 留空保留已保存的密钥':''}</span><div className="secret-input"><KeyboardInput type={visible?'text':'password'} value={newKey} onChange={e=>setNewKey(e.target.value)} placeholder={saved.hasKey?'如需替换，请填写新密钥':'在手机中填写 API Key'} autoComplete="off" autoCapitalize="none" autoCorrect="off" spellCheck={false} maxLength={8192} disabled={busy}/><button type="button" aria-label={visible?'隐藏新密钥':'显示新密钥'} aria-pressed={visible} onClick={()=>setVisible(!visible)}>{visible?<EyeClosedIcon/>:<EyeOpenIcon/>}</button></div></label>
     {changedAddress&&<p className="inline-notice warning" role="status">服务地址已修改，请同时填写新密钥；留空保存会清除原密钥。</p>}
     <p className="field-help"><LockClosedIcon/>密钥加密保存在本机，不回显、不进入健康档案备份。</p>
     <Button disabled={busy||!dirty||!endpoint.trim()||!model.trim()} onClick={()=>void save()}>{busy&&!testing?<><ReloadIcon className="spinning"/>正在保存…</>:'保存配置'}</Button>
     <Button secondary disabled={busy||dirty||!saved.hasKey} onClick={()=>void test()}>{testing?<><ReloadIcon className="spinning"/>正在测试连接…</>:'测试连接（仅发送测试文本）'}</Button>
     {testResult&&<p className="inline-notice" role="status">{testResult}</p>}
    </form>
    {saved.hasKey&&!confirmClear&&<button className="text-button ai-clear-button" disabled={busy} onClick={()=>setConfirmClear(true)}>清除已保存的密钥</button>}
    {confirmClear&&<div className="ai-clear-confirm"><p>确认清除本机 API Key？已保存的服务地址、模型和健康资料会保留。{dirty?'页面上的未保存修改会被放弃。':''}</p><div><Button secondary disabled={busy} onClick={()=>setConfirmClear(false)}>取消</Button><Button disabled={busy} onClick={()=>void clear()}>确认清除</Button></div></div>}
   </section>}
   {!saved&&<Button secondary onClick={()=>void load()}>重新读取配置</Button>}
  </>}
  {error&&<p className="form-error" role="alert">{error}</p>}
  <section className="surface ai-config-info"><h3>配置与分析</h3><p>保存配置不会联网。连接测试仅发送测试文本；报告分析需要支持图片输入及 JSON 输出的模型。主页综合分析使用已保存的记录和已核对报告摘要。</p><p>主动分析前会显示发送范围及目标服务。服务商可能收取费用，数据保留规则以该服务商为准。</p><p>换手机后需重新填写 AI 配置。备份恢复不会更改本机已保存的服务地址和密钥。</p></section>
 </>;
}
