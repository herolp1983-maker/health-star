package cn.herohealth.app;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;

public class ReportSelectionTest {
    private JSONArray reports()throws Exception{return new JSONArray().put(new JSONObject().put("id","old")).put(new JSONObject().put("id","new"));}
    @Test public void scopedInventorySelectsOnlyTheUploadedReport()throws Exception{
        JSONArray all=reports(),selected=ReportSelection.select(all,new JSONObject().put("reportId","new"));
        assertEquals(1,selected.length());assertEquals("new",selected.getJSONObject(0).getString("id"));assertEquals(2,all.length());
    }
    @Test public void missingReportDoesNotFallBackToAll()throws Exception{
        assertThrows(IllegalArgumentException.class,()->ReportSelection.select(reports(),new JSONObject().put("reportId","missing")));
    }
    @Test public void invalidScopeCannotBecomeAnUnscopedRequest()throws Exception{
        for(Object id:new Object[]{"",42,true,JSONObject.NULL})assertThrows(IllegalArgumentException.class,()->ReportSelection.select(reports(),new JSONObject().put("reportId",id)));
    }
    @Test public void legacyExplicitBulkInventoryRemainsAvailable()throws Exception{
        JSONArray all=reports();assertSame(all,ReportSelection.select(all,new JSONObject()));assertSame(all,ReportSelection.select(all,null));
    }
}
