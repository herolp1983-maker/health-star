package cn.herohealth.app;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;

public class SummaryPolicyTest {
    @Test public void defaultAndCustomPreferencesReachThePromptWithFixedContract(){
        String built=SummaryPolicy.instruction("","EXPERT_DEFAULT","SYNTHETIC_DATA");
        assertTrue(built.contains("EXPERT_DEFAULT"));assertTrue(built.contains("SYNTHETIC_DATA"));assertTrue(built.contains("assessment"));
        String custom=SummaryPolicy.instruction("USER_PREFERENCE","EXPERT_DEFAULT","SYNTHETIC_DATA");
        assertTrue(custom.contains("USER_PREFERENCE"));assertFalse(custom.contains("EXPERT_DEFAULT"));assertTrue(custom.contains("固定约束"));assertTrue(custom.contains("关联不代表因果"));assertTrue(custom.contains("不建议自行启停药"));assertTrue(custom.contains("仅返回JSON对象"));
    }
    @Test public void changedPromptRejectsStaleSendAndInvalidPreferenceFailsClosed(){
        SummaryPolicy.checkExpected("","");SummaryPolicy.checkExpected("saved","saved");
        assertThrows(IllegalArgumentException.class,()->SummaryPolicy.checkExpected("old","new"));
        assertThrows(IllegalArgumentException.class,()->SummaryPolicy.preference(null,"default"));
        assertThrows(IllegalArgumentException.class,()->SummaryPolicy.preference("x".repeat(12001),"default"));
        assertEquals("default",SummaryPolicy.preference("  ","default"));
    }
    @Test public void allCardContextIncludesMultilineBackgroundAndKeepsPrivateFieldsOut()throws Exception{
        JSONObject card=new JSONObject().put("id","basic").put("name","基本信息").put("description","").put("patientBackground","SYNTHETIC_BACKGROUND\nSECOND_LINE").put("metricIds",new JSONArray()).put("apiKey","PRIVATE_SENTINEL");
        JSONObject archive=new JSONObject().put("cards",new JSONArray().put(card)).put("metrics",new JSONArray()).put("readings",new JSONArray()).put("reports",new JSONArray()).put("settings",new JSONObject().put("summaryPrompt","PROMPT_SENTINEL"));
        JSONArray projected=HealthContext.cards(archive);
        assertEquals("SYNTHETIC_BACKGROUND\nSECOND_LINE",projected.getJSONObject(0).getString("patientBackground"));
        assertFalse(projected.toString().contains("PRIVATE_SENTINEL"));assertFalse(projected.toString().contains("PROMPT_SENTINEL"));
    }
}
