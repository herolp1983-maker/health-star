import {createContext,useContext,useEffect,useRef,useState,forwardRef,type ReactNode,type InputHTMLAttributes,type TextareaHTMLAttributes,type HTMLAttributes} from 'react';
import * as Dialog from '@radix-ui/react-dialog';
export type FlowScreen={id:string;title?:string;header?:()=>ReactNode;headerHeight?:number;footer?:()=>ReactNode;footerHeight?:number;render:()=>ReactNode};
export type FlowControls={push:(screen:FlowScreen)=>void;pop:()=>void;replace:(screen:FlowScreen)=>void};
const FlowContext=createContext<FlowControls>(null!);
export const useFlow=()=>useContext(FlowContext);
const dismiss=()=>{if(document.activeElement instanceof HTMLElement)document.activeElement.blur();};
const keyboard={hide:dismiss};export const useKeyboard=()=>keyboard;
export const KeyboardInput=forwardRef<HTMLInputElement,InputHTMLAttributes<HTMLInputElement>>((props,ref)=><input {...props} ref={ref}/>);
export const KeyboardTextarea=forwardRef<HTMLTextAreaElement,TextareaHTMLAttributes<HTMLTextAreaElement>>((props,ref)=><textarea {...props} ref={ref}/>);
export const MobileScroll=forwardRef<HTMLDivElement,HTMLAttributes<HTMLDivElement>>(({className='',...props},ref)=><div {...props} ref={ref} className={`native-scroll ${className}`}/>);
export function FlowStack({initial}:{initial:FlowScreen}){
 const [stack,setStack]=useState([initial]);
 const controls:FlowControls={push:s=>{dismiss();setStack(a=>[...a,s]);},pop:()=>{dismiss();setStack(a=>a.length>1?a.slice(0,-1):a);},replace:s=>{dismiss();setStack(a=>[...a.slice(0,-1),s]);}};
 useEffect(()=>{const back=(event:Event)=>{if(!event.defaultPrevented&&!document.querySelector('[role="dialog"]')&&stack.length>1){event.preventDefault();controls.pop();}};window.addEventListener('hero-back',back);return()=>window.removeEventListener('hero-back',back);},[stack.length]);
 return <FlowContext.Provider value={controls}><div className="flow-stack" data-flow-depth={stack.length}>{stack.map((screen,index)=><div key={`${index}-${screen.id}`} hidden={index!==stack.length-1} className="flow-screen" style={{'--flow-footer-height':`${screen.footerHeight||0}px`} as React.CSSProperties}><header className="native-header">{screen.header?.()}</header><div className="native-route-body">{screen.render()}</div>{screen.footer&&<footer className="native-footer">{screen.footer()}</footer>}</div>)}</div></FlowContext.Provider>;
}
export function BottomSheet({open,onOpenChange,title,description,children,locked=false}:{open:boolean;onOpenChange:(open:boolean)=>void;title:string;description?:string;snap?:number;children:ReactNode;locked?:boolean}){const ref=useRef<HTMLDivElement>(null);return <Dialog.Root open={open} onOpenChange={next=>{if(!locked)onOpenChange(next);}}><Dialog.Portal><Dialog.Overlay className="native-sheet-overlay"/><Dialog.Content ref={ref} className="bottom-sheet native-sheet" aria-describedby={description?'sheet-description':undefined} onEscapeKeyDown={e=>{if(locked)e.preventDefault();}} onPointerDownOutside={e=>{if(locked)e.preventDefault();}} onOpenAutoFocus={e=>{e.preventDefault();dismiss();ref.current?.focus();}} tabIndex={-1}><div className="sheet-grip"/><div className="native-sheet-heading"><Dialog.Title>{title}</Dialog.Title><Dialog.Close aria-label="关闭" disabled={locked}>关闭</Dialog.Close></div>{description&&<Dialog.Description id="sheet-description">{description}</Dialog.Description>}<div className="native-sheet-scroll">{children}</div></Dialog.Content></Dialog.Portal></Dialog.Root>;}
