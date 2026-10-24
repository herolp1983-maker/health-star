package cn.herohealth.app;
import org.json.JSONArray;
import org.json.JSONObject;

/** A scoped inventory must never fall back to scanning all reports. */
final class ReportSelection {
    static JSONArray select(JSONArray reports,JSONObject request)throws Exception{
        if(request==null||!request.has("reportId"))return reports;
        Object value=request.get("reportId");
        if(!(value instanceof String)||((String)value).isEmpty())throw new IllegalArgumentException("无效报告ID");
        for(int i=0;i<reports.length();i++)if(value.equals(reports.getJSONObject(i).getString("id")))return new JSONArray().put(reports.getJSONObject(i));
        throw new IllegalArgumentException("报告不存在");
    }
}
