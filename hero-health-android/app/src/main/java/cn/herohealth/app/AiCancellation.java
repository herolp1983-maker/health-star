package cn.herohealth.app;

import javax.net.ssl.HttpsURLConnection;

/** One explicit AI operation owns its active connection and cancellation. */
final class AiCancellation {
    private boolean cancelled;
    private HttpsURLConnection active;
    synchronized void check() throws AiHttp.Failure {
        if(cancelled||Thread.currentThread().isInterrupted())throw new AiHttp.Failure("AI 请求已中断，已保存的结果保留；请确认后手动重试");
    }
    synchronized void attach(HttpsURLConnection connection) throws AiHttp.Failure {
        check();active=connection;
    }
    synchronized void detach(HttpsURLConnection connection){if(active==connection)active=null;}
    void cancel(){
        HttpsURLConnection connection;
        synchronized(this){cancelled=true;connection=active;active=null;}
        if(connection!=null)connection.disconnect();
    }
}
