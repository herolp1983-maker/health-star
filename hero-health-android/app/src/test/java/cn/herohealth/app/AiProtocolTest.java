package cn.herohealth.app;

import org.junit.Test;
import org.json.JSONObject;
import org.json.JSONArray;
import static org.junit.Assert.*;

public class AiProtocolTest {
    private String wire(Object content)throws Exception{return new JSONObject().put("choices",new JSONArray().put(new JSONObject().put("finish_reason","stop").put("message",new JSONObject().put("content",content)))).put("base_resp",new JSONObject().put("status_code",0)).toString();}
    @Test public void miniMaxThinkingAndFencedJsonAreSeparated()throws Exception{
        JSONObject parsed=AiProtocol.parse(wire("<think>思考过程含 {\"wrong\":true}，不可用于指标。</think>\n```json\n{\"summary\":\"测试摘要\",\"metrics\":[]}\n```"),false);
        assertEquals("测试摘要",parsed.getString("summary"));assertFalse(parsed.has("wrong"));
    }
    @Test public void plainTextConnectivityDoesNotDependOnJson()throws Exception{
        assertTrue(AiProtocol.parse(wire("<think>测试服务</think>健康星连接成功。"),true).getBoolean("ok"));
        assertThrows(AiHttp.Failure.class,()->AiProtocol.parse(wire("健康星连接成功。"),false));
    }
    @Test public void supportsTextBlocksAndQuotedBraces()throws Exception{
        JSONArray content=new JSONArray().put(new JSONObject().put("type","text").put("text","```json\n")).put(new JSONObject().put("type","text").put("text","{\"quote\":\"原文包含 } 与 \\\" 引号\"}\n```"));
        assertEquals("原文包含 } 与 \" 引号",AiProtocol.parse(wire(content),false).getString("quote"));
    }
    @Test public void businessErrorsAreNotMisreportedAsJsonErrors()throws Exception{
        for(int code:new int[]{1004,1008,2013,9876}){
            String response=new JSONObject().put("base_resp",new JSONObject().put("status_code",code).put("status_msg","private-provider-body-never-echo")).toString();
            AiHttp.Failure error=assertThrows(AiHttp.Failure.class,()->AiProtocol.parse(response,true));
            assertTrue(error.getMessage().contains(String.valueOf(code)));assertFalse(error.getMessage().contains("private-provider-body"));
        }
    }
    @Test public void reasoningOnlyTruncatedAmbiguousAndIncompleteRepliesFail()throws Exception{
        assertThrows(AiHttp.Failure.class,()->AiProtocol.parse(wire("<think>unfinished"),true));
        assertThrows(AiHttp.Failure.class,()->AiProtocol.parse(wire("{\"one\":1} {\"two\":2}"),false));
        assertThrows(AiHttp.Failure.class,()->AiProtocol.parse(wire("{\"missing\":1"),false));
        JSONObject truncated=new JSONObject(wire("{}"));truncated.getJSONArray("choices").getJSONObject(0).put("finish_reason","length");
        assertTrue(assertThrows(AiHttp.Failure.class,()->AiProtocol.parse(truncated.toString(),false)).getMessage().contains("截断"));
        JSONObject reasoningOnly=new JSONObject().put("choices",new JSONArray().put(new JSONObject().put("message",new JSONObject().put("reasoning_content","{\"not-final\":1}"))));
        assertThrows(AiHttp.Failure.class,()->AiProtocol.parse(reasoningOnly.toString(),false));
    }
    @Test public void miniMaxRequestsUseDocumentedSplitWithoutUnsupportedJsonFlag()throws Exception{
        JSONObject request=AiProtocol.request("https://api.minimax.cn/v1","MiniMax-M3",new JSONArray(),false);
        assertTrue(request.getBoolean("reasoning_split"));assertFalse(request.has("response_format"));assertFalse(request.has("thinking"));
        JSONObject test=AiProtocol.request("https://api.minimax.cn/v1","MiniMax-M3",new JSONArray(),true);
        assertEquals("disabled",test.getJSONObject("thinking").getString("type"));
        JSONObject flash=AiProtocol.request("https://api.minimax.cn/v1","MiniMax-M3.1-Flash",new JSONArray(),true);
        assertFalse(flash.has("thinking"));assertEquals("low",flash.getString("reasoning_effort"));
    }
    @Test public void openAiKeepsJsonForAnalysisButNotForConnectivity()throws Exception{
        JSONObject analysis=AiProtocol.request("https://api.openai.com/v1","example",new JSONArray(),false);
        assertEquals("json_object",analysis.getJSONObject("response_format").getString("type"));assertFalse(analysis.getBoolean("store"));
        assertFalse(AiProtocol.request("https://example.com/v1","example",new JSONArray(),true).has("response_format"));
    }
    @Test public void knownMiniMaxRootExpandsToV1WithoutChangingSavedDestination()throws Exception{
        assertEquals("https://api.minimax.cn/v1/chat/completions",AiHttp.completionUrl("https://api.minimax.cn"));
        assertEquals("https://api.minimax.io/v1/chat/completions",AiHttp.completionUrl("https://api.minimax.io/"));
        assertEquals("https://custom.example/chat/completions",AiHttp.completionUrl("https://custom.example"));
        assertFalse(AiProtocol.miniMax("https://api.minimax.cn.attacker.example"));
    }
    @Test public void semanticAndPrintedPageEvidenceSurvivesProviderEnvelope()throws Exception{
        JSONObject metric=new JSONObject().put("metricId","weight").put("value",68.3).put("unit","kg").put("page",1).put("printedPage","2").put("quote","体质量68.3公斤");
        JSONObject pending=new JSONObject().put("category","review").put("name","血糖").put("value","5.4").put("unit","毫摩尔每升").put("page",1).put("reason","空腹条件不明");
        JSONObject result=new JSONObject().put("metrics",new JSONArray().put(metric)).put("reviewItems",new JSONArray().put(pending));
        JSONObject parsed=AiProtocol.parse(wire(result.toString()),false);
        assertEquals(1,parsed.getJSONArray("metrics").getJSONObject(0).getInt("page"));assertEquals("2",parsed.getJSONArray("metrics").getJSONObject(0).getString("printedPage"));assertEquals("体质量68.3公斤",parsed.getJSONArray("metrics").getJSONObject(0).getString("quote"));assertEquals("review",parsed.getJSONArray("reviewItems").getJSONObject(0).getString("category"));
    }
}
