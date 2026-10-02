package nl.routepilot.mobile;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URLEncoder;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class SyncManager {
    private static final ExecutorService EXECUTOR=Executors.newSingleThreadExecutor();
    private SyncManager(){}
    public interface Callback { void done(boolean ok,String message); }

    public static void syncAsync(Context context, Callback callback){
        Context app=context.getApplicationContext();
        EXECUTOR.execute(()->{
            SyncResult r=syncBlocking(app);
            if(callback!=null) new android.os.Handler(android.os.Looper.getMainLooper()).post(()->callback.done(r.ok,r.message));
        });
    }

    public static SyncResult syncBlocking(Context context){
        SharedPreferences p=RoutePilotApp.prefs(context);
        String base=normalizeBase(p.getString(RoutePilotApp.KEY_SERVER_URL,""));
        if(base.isEmpty())return new SyncResult(false,"Stel eerst de RoutePilot webapp-URL in.");
        String token=p.getString(RoutePilotApp.KEY_SERVER_TOKEN,"");
        String deviceId=p.getString(RoutePilotApp.KEY_DEVICE_ID,"");
        String deviceName=p.getString(RoutePilotApp.KEY_DEVICE_NAME,"");
        RoutePilotDb db=RoutePilotDb.get(context);
        int uploaded=0;
        try{
            JSONObject health=request(base+"/api/health","GET",token,null);
            if(!health.optBoolean("ok",false))throw new Exception("Webapp healthcheck mislukt");
            List<String> pending=db.pendingShiftIds();
            for(String shiftId:pending){
                try{
                    JSONObject payload=db.shiftPayload(shiftId,deviceId,deviceName);
                    JSONObject response=request(base+"/api/sync/shift","POST",token,payload);
                    if(!response.optBoolean("ok",false))throw new Exception(response.optString("error","dienstupload geweigerd"));
                    db.markShiftUploaded(shiftId);uploaded++;
                }catch(Exception ex){db.markShiftError(shiftId,ex.getMessage());throw ex;}
            }
            int since=db.knowledgeRevision();
            String qs="?since="+since+"&device_id="+enc(deviceId)+"&device_name="+enc(deviceName)+"&app_version="+enc("5.2.1-android");
            JSONObject pull=request(base+"/api/sync/training"+qs,"GET",token,null);
            if(!pull.optBoolean("ok",false))throw new Exception(pull.optString("error","trainingssync mislukt"));
            int revision=pull.optInt("revision",since);
            boolean changed=pull.optBoolean("changed",false);
            if(changed){
                JSONObject knowledge=pull.optJSONObject("knowledge");if(knowledge==null)knowledge=new JSONObject();
                db.saveKnowledge(revision,pull.optString("hash",""),knowledge);
                JSONObject ack=new JSONObject();ack.put("device_id",deviceId);ack.put("device_name",deviceName);ack.put("app_version","5.2.1-android");ack.put("revision",revision);
                request(base+"/api/sync/ack","POST",token,ack);
            }
            p.edit().putLong("last_sync_at",System.currentTimeMillis()).putString("last_sync_error","").apply();
            String msg="Sync klaar • "+uploaded+" dienst(en) omhoog • kennis rev "+db.knowledgeRevision()+ (changed?" bijgewerkt":" actueel");
            return new SyncResult(true,msg);
        }catch(Exception ex){
            p.edit().putString("last_sync_error",ex.getMessage()==null?ex.toString():ex.getMessage()).apply();
            return new SyncResult(false,"Sync niet gelukt: "+(ex.getMessage()==null?ex.toString():ex.getMessage()));
        }
    }

    public static JSONObject request(String url,String method,String token,JSONObject body)throws Exception{
        HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();c.setRequestMethod(method);c.setConnectTimeout(8000);c.setReadTimeout(25000);c.setRequestProperty("Accept","application/json");c.setRequestProperty("User-Agent","RoutePilot-Android/5.2.1");
        if(token!=null&&!token.trim().isEmpty()){c.setRequestProperty("Authorization","Bearer "+token.trim());c.setRequestProperty("X-RoutePilot-Token",token.trim());}
        if(body!=null){c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json; charset=utf-8");byte[] bytes=body.toString().getBytes(StandardCharsets.UTF_8);c.setFixedLengthStreamingMode(bytes.length);try(OutputStream out=c.getOutputStream()){out.write(bytes);}}
        int code=c.getResponseCode();InputStream in=(code>=200&&code<300)?c.getInputStream():c.getErrorStream();String text=readAll(in);c.disconnect();
        JSONObject o;try{o=new JSONObject(text.isEmpty()?"{}":text);}catch(Exception ex){throw new Exception("HTTP "+code+" gaf geen geldige JSON");}
        if(code<200||code>=300)throw new Exception("HTTP "+code+": "+o.optString("error",text));return o;
    }
    private static String readAll(InputStream in)throws Exception{if(in==null)return"";StringBuilder b=new StringBuilder();try(BufferedReader r=new BufferedReader(new InputStreamReader(in,StandardCharsets.UTF_8))){String line;while((line=r.readLine())!=null)b.append(line);}return b.toString();}
    private static String normalizeBase(String s){s=s==null?"":s.trim();while(s.endsWith("/"))s=s.substring(0,s.length()-1);return s;}
    private static String enc(String s)throws Exception{return URLEncoder.encode(s==null?"":s,"UTF-8");}
    public static final class SyncResult{public final boolean ok;public final String message;public SyncResult(boolean ok,String message){this.ok=ok;this.message=message;}}
}
