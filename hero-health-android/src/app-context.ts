import { createContext, useContext } from 'react';
import type { HealthState } from './model';
export type Tab='home'|'reports'|'cards'|'chat';
export type Sheet={kind:'report-delete'|'record'|'card'|'import'|'analyze'|'card-actions'|'home-metrics'|'export'|'restore'|'confirm-restore'|'ai-report'|'ai-settings'|'ai-batch'|'report-edit'|'metric-edit'|'medication'|'chat-context'|'chat-history';id?:string;medId?:string;returnTo?:'import'}|null;
export type AppContextValue={critical:boolean;setCritical:(value:boolean)=>void;data:HealthState;commit:(fn:(s:HealthState)=>HealthState)=>Promise<HealthState>;tab:Tab;setTab:(t:Tab)=>void;sheet:Sheet;open:(s:Sheet)=>void;notify:(s:string)=>void;pending:HealthState|null;setPending:(s:HealthState|null)=>void;password:string;setPassword:(s:string)=>void};
export const AppContext=createContext<AppContextValue>(null!);
export const useApp=()=>useContext(AppContext);
