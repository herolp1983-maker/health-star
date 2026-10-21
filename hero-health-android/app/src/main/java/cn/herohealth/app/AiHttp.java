package cn.herohealth.app;

import javax.net.ssl.HttpsURLConnection;
import java.net.URL;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;

/** HTTPS only; credentials never follow a redirect or appear in error messages. */
final class AiHttp {
    static final class Failure extends Exception { Failure(String message){super(message);} }
    static String completionUrl(String base) throws Failure {
        try {
            URL url=new URL(base);
            if(!url.getProtocol().equals("https")||url.getHost().isEmpty()||url.getUserInfo()!=null||url.getQuery()!=null||url.getRef()!=null)throw new Exception();
            String clean=base.replaceAll("/+$","");
            if(AiProtocol.miniMax(base)&&(url.getPath().isEmpty()||url.getPath().equals("/")))clean+="/v1";
            return clean.endsWith("/chat/completions")?clean:clean+"/chat/completions";
        }catch(Exception error){throw new Failure("请在设置中填写有效的 HTTPS API 基础地址");}
    }
    static String errorForStatus(int status){
        if(status==401)return "密钥验证失败，请到设置检查 API Key";
        if(status==403)return "服务拒绝访问，请检查模型权限、服务地区或网络";
        if(status==404)return "接口或模型不存在，请核对 API 基础地址和模型名称";
        if(status==429)return "服务请求受限或额度不足，请检查账户后稍后重试";
        if(status==413)return "报告超出服务商请求大小限制，请拆分后重试";
        if(status>=300&&status<400)return "服务地址返回跳转，已停止发送，请填写最终 HTTPS API 地址";
        if(status==400||status==422)return "服务不接受此请求，请确认模型支持 Chat Completions、JSON 输出及报告图片输入";
        return "AI 服务暂时不可用（HTTP "+status+"），请稍后重试";
    }
    static String post(String base,String key,String body) throws Exception {
        HttpsURLConnection connection=(HttpsURLConnection)new URL(completionUrl(base)).openConnection();
        return exchange(connection,key,body);
    }
    static String exchange(HttpsURLConnection connection,String key,String body) throws Exception {
        try {
            connection.setInstanceFollowRedirects(false);connection.setConnectTimeout(20000);connection.setReadTimeout(90000);
            connection.setRequestMethod("POST");connection.setDoOutput(true);connection.setUseCaches(false);
            connection.setRequestProperty("Content-Type","application/json; charset=utf-8");connection.setRequestProperty("Accept","application/json");
            connection.setRequestProperty("Authorization","Bearer "+key);
            byte[] bytes=body.getBytes(StandardCharsets.UTF_8);
            if(bytes.length>18*1024*1024)throw new Failure("分析请求超过18 MB，请拆分报告后重试");
            connection.setFixedLengthStreamingMode(bytes.length);
            try(OutputStream output=connection.getOutputStream()){output.write(bytes);}
            int status=connection.getResponseCode();
            if(status<200||status>=300)throw new Failure(errorForStatus(status));
            try(InputStream input=connection.getInputStream();ByteArrayOutputStream output=new ByteArrayOutputStream()){
                byte[] buffer=new byte[8192];int count;
                while((count=input.read(buffer))!=-1){if(output.size()+count>512*1024)throw new Failure("AI 返回内容过大，请减少资料后重试");output.write(buffer,0,count);}
                return output.toString(StandardCharsets.UTF_8.name());
            }
        }catch(java.net.SocketTimeoutException error){throw new Failure("AI 请求超时，请检查网络后重试；已有资料保持完整");}
        catch(javax.net.ssl.SSLException error){throw new Failure("服务的安全连接验证失败，请检查 HTTPS 地址与证书");}
        catch(java.io.IOException error){throw new Failure("无法连接 AI 服务，请检查网络与服务地址后重试");}
        finally{connection.disconnect();}
    }
}
