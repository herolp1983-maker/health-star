package cn.herohealth.app;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.AtomicFile;
import android.util.Base64;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.util.UUID;
import java.util.HashSet;
import java.util.Set;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;

final class HealthVault {
    private static HealthVault instance;
    static synchronized HealthVault open(Context context) throws Exception {if(instance==null)instance=new HealthVault(context.getApplicationContext());return instance;}
    private final File root,attachments;
    private final AtomicFile state,aiConfig;
    private final SecretKey key;
    HealthVault(Context context) throws Exception {
        root=new File(context.getFilesDir(),"health-vault");attachments=new File(root,"reports");
        if(!attachments.isDirectory()&&!attachments.mkdirs()) throw new Exception("Storage unavailable");
        state=new AtomicFile(new File(root,"archive.hhv"));
        aiConfig=new AtomicFile(new File(root,"ai-config.hhv"));
        KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
        String alias="hero-health-local-v1";
        if(!store.containsAlias(alias)){
            if(state.getBaseFile().exists()||new File(state.getBaseFile()+".bak").exists()||aiConfig.getBaseFile().exists()||new File(aiConfig.getBaseFile()+".bak").exists())throw new Exception("Device key unavailable");
            KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setKeySize(256).setRandomizedEncryptionRequired(true).build());
            generator.generateKey();
        }
        key=(SecretKey)store.getKey(alias,null);
    }
    private AiConfigPolicy.Config privateAiConfig() throws Exception {
        if(!aiConfig.getBaseFile().exists()&&!new File(aiConfig.getBaseFile()+".bak").exists())return new AiConfigPolicy.Config("","","");
        JSONObject saved=new JSONObject(new String(VaultCodec.decrypt(key,aiConfig.readFully(),"hero-health-ai-config-v1"),StandardCharsets.UTF_8));
        return new AiConfigPolicy.Config(saved.getString("endpoint"),saved.getString("model"),saved.getString("apiKey"));
    }
    private JSONObject publicAiConfig(AiConfigPolicy.Config saved) throws Exception {
        // No action returns a saved credential to the WebView, including masked suffixes.
        return new JSONObject().put("endpoint",saved.endpoint).put("model",saved.model).put("hasKey",!saved.apiKey.isEmpty());
    }
    synchronized JSONObject readAiConfig() throws Exception { return publicAiConfig(privateAiConfig()); }
    synchronized AiConfigPolicy.Config aiCredential() throws Exception { return privateAiConfig(); }
    synchronized JSONObject saveAiConfig(JSONObject payload) throws Exception {
        AiConfigPolicy.Config next=AiConfigPolicy.update(payload.getString("endpoint"),payload.getString("model"),payload.optString("newKey",""),payload.optBoolean("clearKey",false),privateAiConfig());
        writeAiConfig(next);
        return publicAiConfig(next);
    }
    synchronized JSONObject clearAiKey() throws Exception {
        AiConfigPolicy.Config previous=privateAiConfig();
        AiConfigPolicy.Config next=new AiConfigPolicy.Config(previous.endpoint,previous.model,"");
        writeAiConfig(next);
        return publicAiConfig(next);
    }
    private void writeAiConfig(AiConfigPolicy.Config next) throws Exception {
        JSONObject data=new JSONObject().put("endpoint",next.endpoint).put("model",next.model).put("apiKey",next.apiKey);
        atomicWrite(aiConfig,VaultCodec.encrypt(key,data.toString().getBytes(StandardCharsets.UTF_8),"hero-health-ai-config-v1"));
    }
    synchronized JSONObject readState() throws Exception {
        if(!state.getBaseFile().exists()&&!new File(state.getBaseFile()+".bak").exists())return null;
        byte[] encrypted=state.readFully();
        return new JSONObject(new String(VaultCodec.decrypt(key,encrypted,"hero-health-state"),StandardCharsets.UTF_8));
    }
    synchronized JSONObject saveState(JSONObject data) throws Exception {
        if(data.getInt("schema")!=1)throw new Exception("Invalid schema");
        JSONArray reports=data.getJSONArray("reports");
        for(int i=0;i<reports.length();i++){
            JSONObject report=reports.getJSONObject(i),file=report.optJSONObject("file");if(file==null)continue;
            String mime=file.getString("mime"),url=file.getString("dataUrl");
            if(!mime.equals("application/pdf")&&!mime.equals("image/png")&&!mime.equals("image/jpeg")&&!mime.equals("image/webp"))throw new Exception("Invalid file type");
            if(url.startsWith("data:"+mime+";base64,")){
                byte[] bytes=Base64.decode(url.substring(url.indexOf(',')+1),Base64.NO_WRAP);
                if(bytes.length>15*1024*1024||!validFile(bytes,mime))throw new Exception("报告文件无效或超过15 MB");
                String id=UUID.randomUUID().toString();
                atomicWrite(new AtomicFile(attachmentFile(id)),VaultCodec.encrypt(key,bytes,"hero-health-report:"+id));
                file.put("id",id);file.put("dataUrl","https://app.hero.local/reports/"+id);
                file.put("sha256",hex(MessageDigest.getInstance("SHA-256").digest(bytes)));
            } else {
                String id=file.getString("id");
                if(!url.equals("https://app.hero.local/reports/"+id)||!attachmentFile(id).isFile())throw new Exception("原件不存在，请重新导入");
            }
        }
        byte[] encoded=data.toString().getBytes(StandardCharsets.UTF_8);
        atomicWrite(state,VaultCodec.encrypt(key,encoded,"hero-health-state"));
        // Only collect unreferenced ciphertext after the new archive has committed.
        Set<String> live=new HashSet<>();
        for(int i=0;i<reports.length();i++){JSONObject file=reports.getJSONObject(i).optJSONObject("file");if(file!=null)live.add(file.optString("id")+".hhv");}
        File[] stale=attachments.listFiles((dir,name)->name.matches("[0-9a-f-]{36}\\.hhv")&&!live.contains(name));
        if(stale!=null)for(File file:stale){try{Files.deleteIfExists(file.toPath());}catch(Exception ignored){}}
        return data;
    }
    synchronized byte[] attachment(String id) throws Exception {
        return VaultCodec.decrypt(key,Files.readAllBytes(attachmentFile(id).toPath()),"hero-health-report:"+id);
    }
    synchronized JSONObject fileMetadata(String id) throws Exception {
        JSONObject archive=readState();if(archive==null)throw new Exception("No archive");
        JSONArray reports=archive.getJSONArray("reports");
        for(int i=0;i<reports.length();i++){JSONObject file=reports.getJSONObject(i).optJSONObject("file");if(file!=null&&id.equals(file.optString("id")))return file;}
        throw new Exception("报告不存在");
    }
    synchronized String attachmentDataUrl(String id) throws Exception {
        return "data:"+fileMetadata(id).getString("mime")+";base64,"+Base64.encodeToString(attachment(id),Base64.NO_WRAP);
    }
    private File attachmentFile(String id){if(!UUID.fromString(id).toString().equals(id))throw new IllegalArgumentException("Invalid report ID");return new File(attachments,id+".hhv");}
    private static void atomicWrite(AtomicFile target,byte[] bytes) throws Exception {
        FileOutputStream out=null;
        try{out=target.startWrite();out.write(bytes);target.finishWrite(out);}catch(Exception error){if(out!=null)target.failWrite(out);throw error;}
    }
    private static String hex(byte[] bytes){StringBuilder result=new StringBuilder();for(byte b:bytes)result.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return result.toString();}
    private static boolean validFile(byte[] b,String mime){
        if(b.length<12)return false;
        if(mime.equals("application/pdf"))return b[0]=='%'&&b[1]=='P'&&b[2]=='D'&&b[3]=='F'&&b[4]=='-';
        if(mime.equals("image/png"))return (b[0]&255)==137&&b[1]=='P'&&b[2]=='N'&&b[3]=='G';
        if(mime.equals("image/jpeg"))return (b[0]&255)==255&&(b[1]&255)==216&&(b[2]&255)==255;
        return b[0]=='R'&&b[1]=='I'&&b[2]=='F'&&b[3]=='F'&&b[8]=='W'&&b[9]=='E'&&b[10]=='B'&&b[11]=='P';
    }
}
