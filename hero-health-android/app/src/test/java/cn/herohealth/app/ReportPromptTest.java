package cn.herohealth.app;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;
public class ReportPromptTest {
 @Test public void singleAndBatchExamplesContainAllRequiredArrays()throws Exception{
  for(boolean batch:new boolean[]{false,true}){String prompt=ReportPrompt.outputSchema(batch);JSONObject top=new JSONObject(AiProtocol.jsonObject(prompt)),report=batch?top.getJSONArray("reports").getJSONObject(0):top;
   for(String field:new String[]{"metrics","reviewItems","readabilityIssues","notes"})assertNotNull(report.getJSONArray(field));
   assertTrue(report.has("reportDate"));assertTrue(report.has("summary"));assertTrue(batch?top.has("card"):report.has("cards"));
   JSONObject metric=report.getJSONArray("metrics").getJSONObject(0);assertFalse(metric.has("printedPage"));assertFalse(metric.has("matchReason"));assertEquals("review",report.getJSONArray("reviewItems").getJSONObject(0).getString("category"));assertTrue(prompt.contains("flag"));assertTrue(prompt.contains("无标记省略"));
  }
 }
 @Test public void onlyActualObservedResultsMayBeExtractedAndSynonymsAreNotAllAmbiguous(){
  assertTrue(ReportPrompt.RULES.contains("报告未测、空白"));assertTrue(ReportPrompt.RULES.contains("不要因字面不同而全部放进reviewItems"));assertTrue(ReportPrompt.RULES.contains("不得省略、不得填null"));assertTrue(ReportPrompt.RULES.contains("不进行数值换算"));assertTrue(ReportPrompt.RULES.contains("物理页序号"));assertTrue(ReportPrompt.RULES.contains("可选布尔flag"));assertTrue(ReportPrompt.RULES.contains("不得仅按参考范围"));
 }
}
