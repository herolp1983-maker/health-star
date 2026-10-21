/** Nested flow navigation takes priority over the root tab fallback. */
export function backAction(critical:boolean,hasSheet:boolean,flowDepth:number,tab:string):'block'|'sheet'|'nested'|'home'|'system'{
 if(critical)return 'block';
 if(hasSheet)return 'sheet';
 if(flowDepth>1)return 'nested';
 return tab==='home'?'system':'home';
}
