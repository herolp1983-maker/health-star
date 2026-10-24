package cn.herohealth.app;

import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.List;

/** Explicit card projection: never reads chats, credentials or attachment payloads. */
final class HealthContext {
    static JSONArray dateEvidence(JSONObject analysis)throws Exception{JSONArray result=new JSONArray(),segments=analysis.optJSONArray("batchSegments");if(segments!=null)for(int i=0;i<segments.length();i++){JSONObject date=segments.getJSONObject(i).optJSONObject("reportDate");if(date!=null)result.put(date);}return result;}
    static JSONArray medications(JSONArray input)throws Exception{JSONArray result=new JSONArray();if(input==null)return result;String[] fields={"id","name","dose","frequency","startDate","endDate","status","note"};for(int i=0;i<input.length();i++){JSONObject safe=new JSONObject(),item=input.getJSONObject(i);for(String field:fields)if(item.has(field))safe.put(field,item.get(field));result.put(safe);}return result;}
    static JSONArray cards(JSONObject archive)throws Exception {
        JSONArray result=new JSONArray(),cards=archive.getJSONArray("cards"),defs=archive.getJSONArray("metrics"),all=archive.getJSONArray("readings"),reports=archive.getJSONArray("reports");
        for(int i=0;i<cards.length();i++){
            JSONObject card=cards.getJSONObject(i),out=new JSONObject().put("id",card.getString("id")).put("name",card.getString("name")).put("description",card.optString("description")).put("patientBackground",card.optString("patientBackground")).put("archived",card.optBoolean("archived")).put("medications",medications(card.optJSONArray("medications")));
            JSONArray metrics=new JSONArray(),ids=card.getJSONArray("metricIds"),notes=new JSONArray();
            for(int j=0;j<ids.length();j++){String id=ids.getString(j);JSONObject def=null;for(int k=0;k<defs.length();k++)if(id.equals(defs.getJSONObject(k).getString("id")))def=defs.getJSONObject(k);if(def==null)continue;
                List<JSONObject> rows=new ArrayList<>();for(int k=0;k<all.length();k++)if(id.equals(all.getJSONObject(k).getString("metricId")))rows.add(all.getJSONObject(k));rows.sort((a,b)->a.optString("date").compareTo(b.optString("date")));JSONArray history=new JSONArray();for(int k=Math.max(0,rows.size()-10);k<rows.size();k++){JSONObject r=rows.get(k),safe=new JSONObject().put("date",r.getString("date")).put("value",r.getDouble("value"));if(r.has("second"))safe.put("second",r.getDouble("second"));if(r.has("flag"))safe.put("flag",r.getBoolean("flag"));history.put(safe);}
                metrics.put(new JSONObject().put("id",id).put("name",def.getString("name")).put("unit",def.getString("unit")).put("history",history).put("totalRecords",rows.size()));
            }
            List<JSONObject> sorted=new ArrayList<>();for(int j=0;j<reports.length();j++)sorted.add(reports.getJSONObject(j));sorted.sort((a,b)->b.optString("date").compareTo(a.optString("date")));
            for(JSONObject r:sorted){JSONArray analyses=r.optJSONArray("analyses");if(analyses==null)continue;for(int k=analyses.length()-1;k>=0;k--){JSONObject a=analyses.getJSONObject(k);if(!a.optBoolean("accepted")||!a.optBoolean("useCardNotes",true))continue;JSONArray ns=a.optJSONArray("cards");if(ns!=null)for(int n=0;n<ns.length();n++)if(card.getString("id").equals(ns.getJSONObject(n).optString("cardId"))){notes.put(ns.getJSONObject(n));break;}break;}if(notes.length()>0)break;}
            out.put("metrics",metrics).put("latestConfirmedCardNotes",notes);result.put(out);
        }return result;
    }
}
