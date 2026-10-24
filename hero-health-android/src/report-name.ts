/** Rename the display label only. The encrypted attachment and original filename stay intact. */
export function acceptedReportName(examName:string|undefined,date:string,originalName:string,mime?:string):string{
 const found=originalName.match(/\.(jpg|jpeg|png|webp|pdf)$/i);
 const ext=found?.[0]||({'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp','application/pdf':'.pdf'}[mime||'']??'');
 const time=date.replaceAll('-','');
 const label=(examName||'健康').replace(/[\s\u0000-\u001f<>:"/\\|?*]/g,'').replace(/检查.*$/,'').trim()||'健康';
 const room=20-Array.from(ext+'检查'+time).length;
 return Array.from(label).slice(0,Math.max(1,room)).join('')+'检查'+time+ext;
}
