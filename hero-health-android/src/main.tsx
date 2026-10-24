import React,{Component,type ReactNode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import './native.css';
class ErrorBoundary extends Component<{children:ReactNode},{failed:boolean}>{state={failed:false};static getDerivedStateFromError(){return {failed:true};}render(){return this.state.failed?<div className="fatal-screen"><h1>暂时无法显示页面</h1><p>你的本地档案仍保存在手机中。请关闭后重新打开应用；不要清除应用数据。</p><button onClick={()=>location.reload()}>重新打开</button></div>:this.props.children;}}
createRoot(document.getElementById('root')!).render(<ErrorBoundary><App/></ErrorBoundary>);
