package cn.herohealth.app;

import org.json.JSONArray;
import org.json.JSONObject;
import java.net.URI;

/** Provider envelopes are validated separately from clinical JSON. Never expose raw bodies. */
final class AiProtocol {
    static boolean miniMax(String endpoint){try{String host=new URI(endpoint).getHost();return "api.minimax.cn".equalsIgnoreCase(host)||"api.minimax.io".equalsIgnoreCase(host);}catch(Exception e){return false;}}
    static JSONObject request(String endpoint,String model,JSONArray messages,boolean test)throws Exception{
        JSONObject body=new JSONObject().put("model",model).put("messages",messages).put("stream",false);
        if(miniMax(endpoint)){
            body.put("reasoning_split",true).put("max_completion_tokens",test?4096:16384);
            if(model.equalsIgnoreCase("MiniMax-M3")&&test)body.put("thinking",new JSONObject().put("type","disabled"));
            if(model.toLowerCase(java.util.Locale.ROOT).startsWith("minimax-m3.1"))body.put("reasoning_effort",test?"low":"medium");
            // MiniMax does not document response_format. The prompt requests JSON; validate the answer ourselves.
        }else if(!test)body.put("response_format",new JSONObject().put("type","json_object"));
        if("api.openai.com".equalsIgnoreCase(new URI(endpoint).getHost()))body.put("store",false);
        return body;
    }
    static String businessError(int code){
        if(code==1004||code==2049)return "MiniMax 密钥验证失败（业务码"+code+"），请检查 API Key 与接口权限";
        if(code==1008)return "MiniMax 账户余额或额度不足（业务码1008），请检查服务账户";
        if(code==1002)return "MiniMax 请求频率受限（业务码1002），请稍后再试";
        if(code==1039)return "MiniMax Token 限制（业务码1039），请减少每批资料或检查模型长度设置";
        if(code==2013)return "MiniMax 参数或模型不匹配（业务码2013），请检查模型名称和 API 地址";
        return "MiniMax 服务拒绝请求（业务码"+code+"），请检查模型、密钥类型、权限和额度";
    }
    static JSONObject parse(String wire,boolean test)throws Exception{
        JSONObject envelope;
        try{envelope=new JSONObject(wire);}catch(Exception e){throw new AiHttp.Failure("AI 接口未返回有效响应，请确认填写的是 API 地址而非网页地址");}
        JSONObject business=envelope.optJSONObject("base_resp");
        if(business!=null&&business.optInt("status_code",0)!=0)throw new AiHttp.Failure(businessError(business.optInt("status_code",-1)));
        if(envelope.has("error")&&!envelope.isNull("error"))throw new AiHttp.Failure("AI 服务返回错误，请检查 API 地址、模型权限和密钥；已有资料未被修改");
        JSONArray choices=envelope.optJSONArray("choices");
        if(choices==null||choices.length()==0)throw new AiHttp.Failure("接口响应缺少对话结果，请使用 Chat Completions 兼容地址");
        JSONObject choice=choices.optJSONObject(0);
        if(choice==null)throw new AiHttp.Failure("AI 对话响应无效，请检查服务配置");
        if("length".equals(choice.optString("finish_reason")))throw new AiHttp.Failure("AI 输出被截断，请减少每批资料或换用更合适的模型后重试");
        if("content_filter".equals(choice.optString("finish_reason")))throw new AiHttp.Failure("服务未返回可用回答，请检查报告内容或服务限制");
        JSONObject message=choice.optJSONObject("message");if(message==null)throw new AiHttp.Failure("AI 响应缺少最终回答");
        Object content=message.opt("content");String answer="";
        if(content instanceof String)answer=(String)content;
        else if(content instanceof JSONArray){StringBuilder joined=new StringBuilder();JSONArray blocks=(JSONArray)content;for(int i=0;i<blocks.length();i++){JSONObject block=blocks.optJSONObject(i);if(block!=null&&("text".equals(block.optString("type"))||"output_text".equals(block.optString("type"))))joined.append(block.optString("text"));}answer=joined.toString();}
        answer=stripThinking(answer);
        if(answer.isEmpty())throw new AiHttp.Failure("模型未返回最终回答，请检查模型输出设置后重试");
        if(test)return new JSONObject().put("ok",true); // Connectivity never depends on model JSON compliance.
        try{return new JSONObject(jsonObject(answer));}catch(AiHttp.Failure e){throw e;}catch(Exception e){throw new AiHttp.Failure("AI 最终回答不符合数据格式，尚未写入指标，请重试");}
    }
    static String stripThinking(String input)throws AiHttp.Failure{
        String answer=input.trim();if(answer.startsWith("\uFEFF"))answer=answer.substring(1).trim();
        while(answer.regionMatches(true,0,"<think>",0,7)){
            int end=answer.toLowerCase(java.util.Locale.ROOT).indexOf("</think>");
            if(end<0)throw new AiHttp.Failure("模型仅返回未完成的思考内容，请稍后重试");
            answer=answer.substring(end+8).trim();
        }
        return answer;
    }
    static String jsonObject(String answer)throws AiHttp.Failure{
        if(answer.length()>150000)throw new AiHttp.Failure("AI 最终回答过长，请减少资料后重试");
        String found=null;int start=-1,depth=0;boolean quoted=false,escaped=false;
        for(int i=0;i<answer.length();i++){
            char c=answer.charAt(i);
            if(start<0){if(c=='{'){start=i;depth=1;quoted=false;escaped=false;}continue;}
            if(quoted){if(escaped)escaped=false;else if(c=='\\')escaped=true;else if(c=='\"')quoted=false;continue;}
            if(c=='\"')quoted=true;else if(c=='{')depth++;else if(c=='}'&&--depth==0){if(found!=null)throw new AiHttp.Failure("AI 返回多个冲突结果，请重新分析");found=answer.substring(start,i+1);start=-1;}
        }
        if(start>=0||found==null)throw new AiHttp.Failure("AI 最终回答不包含完整数据对象，尚未写入指标，请重试");
        return found;
    }
}
