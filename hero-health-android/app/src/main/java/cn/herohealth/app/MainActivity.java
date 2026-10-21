package cn.herohealth.app;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Build;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.TextView;
import org.json.JSONObject;
import java.io.ByteArrayInputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.HashMap;
import java.util.Collections;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private WebView web;
    private HealthVault vault;
    private final ExecutorService io=Executors.newSingleThreadExecutor();
    private final ExecutorService ai=Executors.newSingleThreadExecutor();
    private final java.util.concurrent.atomic.AtomicBoolean aiRunning=new java.util.concurrent.atomic.AtomicBoolean(false);
    private ValueCallback<Uri[]> chooser;
    private String exportRequest,exportText;
    private static final int PICK_FILE=100,EXPORT_FILE=101;
    @SuppressLint({"SetJavaScriptEnabled","AddJavascriptInterface"})
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.rgb(246,247,251));getWindow().setNavigationBarColor(Color.rgb(246,247,251));
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        FrameLayout frame=new FrameLayout(this);frame.setBackgroundColor(Color.rgb(246,247,251));
        frame.setOnApplyWindowInsetsListener((view,insets)->{if(Build.VERSION.SDK_INT>=30){android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout()),ime=insets.getInsets(WindowInsets.Type.ime());view.setPadding(bars.left,bars.top,bars.right,Math.max(bars.bottom,ime.bottom));}else{view.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());}return insets.consumeSystemWindowInsets();});
        setContentView(frame);
        java.io.File[] cached=getCacheDir().listFiles((dir,name)->name.startsWith("report-")&&name.endsWith(".pdf"));
        if(cached!=null)for(java.io.File cachedReport:cached){try{java.nio.file.Files.deleteIfExists(cachedReport.toPath());}catch(Exception ignored){}}
        try{vault=HealthVault.open(this);}catch(Exception error){TextView failure=new TextView(this);failure.setText("本地档案暂时无法读取。\n资料未被覆盖，请重新打开应用。\n不要清除应用数据或卸载应用。");failure.setPadding(40,60,40,40);frame.addView(failure);return;}
        web=new WebView(this);web.setBackgroundColor(Color.rgb(246,247,251));frame.addView(web,new FrameLayout.LayoutParams(-1,-1));
        WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);settings.setAllowFileAccess(false);settings.setAllowContentAccess(true);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);settings.setJavaScriptCanOpenWindowsAutomatically(false);settings.setSupportMultipleWindows(false);settings.setSaveFormData(false);settings.setMediaPlaybackRequiresUserGesture(true);
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        web.addJavascriptInterface(new LocalBridge(),"HeroNative");
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return !trusted(request.getUrl())||!request.isForMainFrame();}
            @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){
                Uri uri=request.getUrl();if(!trusted(uri))return blocked();
                try{String path=uri.getPath();if(path==null||path.contains(".."))return blocked();
                    if(path.startsWith("/reports/")){String id=path.substring(9);String mime=vault.fileMetadata(id).getString("mime");return response(mime,vault.attachment(id));}
                    String asset=path.equals("/")?"index.html":path.substring(1);String mime=asset.endsWith(".js")?"application/javascript":asset.endsWith(".css")?"text/css":asset.endsWith(".png")?"image/png":asset.endsWith(".woff2")?"font/woff2":"text/html";
                    return new WebResourceResponse(mime,"UTF-8",200,"OK",responseHeaders(),getAssets().open("www/"+asset));
                }catch(Exception error){return blocked();}
            }
        });
        web.setWebChromeClient(new WebChromeClient(){@Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
            if(chooser!=null)chooser.onReceiveValue(null);chooser=callback;
            Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);intent.addCategory(Intent.CATEGORY_OPENABLE);intent.setType("*/*");intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,false);
            String[] types=params.getAcceptTypes();if(types.length>0&&!types[0].startsWith("."))intent.putExtra(Intent.EXTRA_MIME_TYPES,types);
            try{startActivityForResult(intent,PICK_FILE);}catch(Exception error){chooser.onReceiveValue(null);chooser=null;}return true;
        }});
        web.loadUrl("https://app.hero.local/");
        if(Build.VERSION.SDK_INT>=33)getOnBackInvokedDispatcher().registerOnBackInvokedCallback(android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT,this::handleBack);
    }
    private boolean trusted(Uri uri){return "https".equals(uri.getScheme())&&"app.hero.local".equals(uri.getHost())&&(uri.getPort()==-1||uri.getPort()==443);}
    private Map<String,String> responseHeaders(){Map<String,String> headers=new HashMap<>();headers.put("Cache-Control","no-store");headers.put("X-Content-Type-Options","nosniff");return headers;}
    private WebResourceResponse blocked(){return new WebResourceResponse("text/plain","UTF-8",403,"Blocked",Collections.emptyMap(),new ByteArrayInputStream(new byte[0]));}
    private WebResourceResponse response(String mime,byte[] bytes){return new WebResourceResponse(mime,null,200,"OK",responseHeaders(),new ByteArrayInputStream(bytes));}
    public final class LocalBridge {
        @JavascriptInterface public void postMessage(String message){io.execute(()->{
            String id="";try{
                JSONObject request=new JSONObject(message);id=request.getString("id");String action=request.getString("action");JSONObject payload=request.optJSONObject("payload");Object result;
                switch(action){
                    case "readState":result=vault.readState();break;
                    case "saveState":result=vault.saveState(payload);break;
                    case "readAiConfig":result=vault.readAiConfig();break;
                    case "saveAiConfig":result=vault.saveAiConfig(payload);break;
                    case "clearAiKey":result=vault.clearAiKey();break;
                    case "testAiConnection":case "analyzeReport":case "analyzeSummary":case "analyzeCardBatch":case "reportPageCounts":case "healthChat":{
                        if(!aiRunning.compareAndSet(false,true)){reply(id,null,"已有 AI 任务正在进行，请稍后再试");return;}
                        String job=id;JSONObject input=payload;
                        ai.execute(()->{Object answer=null;String failure=null;
                            try{answer=new AiService(MainActivity.this,vault).analyze(action,input);}
                            catch(AiHttp.Failure error){failure=error.getMessage();}
                            catch(Exception error){failure="AI 分析未完成，请检查文件、网络或服务配置后重试。已有资料保持完整。";}
                            finally{aiRunning.set(false);}
                            // Release before publishing the result: the next batch may start immediately.
                            reply(job,answer,failure);});return;
                    }
                    case "readAttachment":result=vault.attachmentDataUrl(payload.getString("id"));break;
                    case "openReport":{String reportId=payload.getString("id");vault.fileMetadata(reportId);runOnUiThread(()->startActivity(new Intent(MainActivity.this,PdfActivity.class).putExtra("reportId",reportId)));result=true;break;}
                    case "exportFile":{String job=id,text=payload.getString("text"),name=payload.getString("name");runOnUiThread(()->beginExport(job,text,name));return;}
                    default:throw new Exception("Unsupported action");
                }
                reply(id,result,null);
            }catch(AiConfigPolicy.Invalid error){reply(id,null,error.getMessage());}
            catch(Exception error){reply(id,null,"本地操作未完成，请检查文件、存储空间后重试。原档案未被覆盖。");}
        });}
    }
    private void beginExport(String id,String text,String name){
        if(exportRequest!=null){reply(id,null,"已有导出任务，请先完成或取消");return;}
        exportRequest=id;exportText=text;
        Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/octet-stream").addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,name.replaceAll("[\\\\/:*?\"<>|]","-"));
        try{startActivityForResult(intent,EXPORT_FILE);}catch(Exception error){exportRequest=null;exportText=null;reply(id,null,"无法打开系统保存位置");}
    }
    private void reply(String id,Object result,String error){
        String encoded=result==null?"null":result instanceof JSONObject?result.toString():result instanceof String?JSONObject.quote((String)result):String.valueOf(result);
        String script="window.heroNativeResult&&window.heroNativeResult("+JSONObject.quote(id)+","+encoded+","+(error==null?"null":JSONObject.quote(error))+")";
        runOnUiThread(()->{if(web!=null&&!isFinishing())web.evaluateJavascript(script,null);});
    }
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);
        if(request==PICK_FILE&&chooser!=null){chooser.onReceiveValue(result==RESULT_OK&&data!=null&&data.getData()!=null?new Uri[]{data.getData()}:null);chooser=null;}
        if(request==EXPORT_FILE&&exportRequest!=null){String id=exportRequest,text=exportText;exportRequest=null;exportText=null;
            if(result!=RESULT_OK||data==null||data.getData()==null){reply(id,null,"导出已取消，当前资料保持不变");return;}
            Uri uri=data.getData();io.execute(()->{try{OutputStream out=getContentResolver().openOutputStream(uri,"wt");if(out==null)throw new Exception();ExportSafety.writeAndClose(out,text);}catch(Exception error){reply(id,null,"保存失败，请检查文件位置和剩余空间");return;}reply(id,true,null);});
        }
    }
    private void handleBack(){if(web==null){finish();return;}web.evaluateJavascript("window.heroBack?window.heroBack():false",handled->{if(!"true".equals(handled))finish();});}
    @Override public void onBackPressed(){handleBack();}
    @Override protected void onPause(){super.onPause();if(web!=null)web.onPause();}
    @Override protected void onResume(){super.onResume();if(web!=null)web.onResume();}
    @Override protected void onDestroy(){if(chooser!=null)chooser.onReceiveValue(null);io.shutdown();ai.shutdownNow();if(web!=null){web.removeJavascriptInterface("HeroNative");web.destroy();web=null;}super.onDestroy();}
}
