package nl.routepilot.mobile;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

public class RoutePilotDb extends SQLiteOpenHelper {
    private static final String DB_NAME = "routepilot-v5.sqlite3";
    private static final int DB_VERSION = 1;
    private static RoutePilotDb INSTANCE;

    public static synchronized RoutePilotDb get(Context c) {
        if (INSTANCE == null) INSTANCE = new RoutePilotDb(c.getApplicationContext());
        return INSTANCE;
    }

    private RoutePilotDb(Context context) { super(context, DB_NAME, null, DB_VERSION); }

    @Override public void onConfigure(SQLiteDatabase db) {
        super.onConfigure(db);
        db.setForeignKeyConstraintsEnabled(true);
        db.enableWriteAheadLogging();
    }

    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE shifts(shift_id TEXT PRIMARY KEY, started_at INTEGER NOT NULL, ended_at INTEGER NOT NULL DEFAULT 0, uploaded INTEGER NOT NULL DEFAULT 0, upload_error TEXT NOT NULL DEFAULT '')");
        db.execSQL("CREATE TABLE trips(trip_id TEXT PRIMARY KEY, shift_id TEXT NOT NULL, destination TEXT NOT NULL, dest_lat REAL NOT NULL, dest_lon REAL NOT NULL, started_at INTEGER NOT NULL, ended_at INTEGER NOT NULL DEFAULT 0, planned_distance_m REAL NOT NULL DEFAULT 0, planned_duration_s REAL NOT NULL DEFAULT 0, planned_json TEXT NOT NULL DEFAULT '[]', warnings_json TEXT NOT NULL DEFAULT '[]', reroutes INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(shift_id) REFERENCES shifts(shift_id) ON DELETE CASCADE)");
        db.execSQL("CREATE TABLE track_points(id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id TEXT NOT NULL, t INTEGER NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL, speed REAL, heading REAL, accuracy REAL, FOREIGN KEY(trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE)");
        db.execSQL("CREATE INDEX idx_track_trip ON track_points(trip_id,id)");
        db.execSQL("CREATE TABLE knowledge(id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL DEFAULT 0, hash TEXT NOT NULL DEFAULT '', json TEXT NOT NULL DEFAULT '{}', updated_at INTEGER NOT NULL DEFAULT 0)");
        db.execSQL("INSERT INTO knowledge(id,revision,hash,json,updated_at) VALUES(1,0,'','{}',0)");
    }

    @Override public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) { }

    public String startShift() {
        String id = "android-" + System.currentTimeMillis() + "-" + UUID.randomUUID().toString().substring(0,8);
        ContentValues v = new ContentValues();
        v.put("shift_id", id); v.put("started_at", System.currentTimeMillis());
        getWritableDatabase().insertOrThrow("shifts", null, v);
        return id;
    }

    public void endShift(String shiftId) {
        ContentValues v = new ContentValues(); v.put("ended_at", System.currentTimeMillis()); v.put("uploaded",0);
        getWritableDatabase().update("shifts", v, "shift_id=?", new String[]{shiftId});
    }

    public String startTrip(String shiftId, String destination, double lat, double lon, double plannedDistance, double plannedDuration, JSONArray plannedPoints) {
        String id = "trip-" + System.currentTimeMillis() + "-" + UUID.randomUUID().toString().substring(0,8);
        ContentValues v = new ContentValues();
        v.put("trip_id",id); v.put("shift_id",shiftId); v.put("destination",destination);
        v.put("dest_lat",lat); v.put("dest_lon",lon); v.put("started_at",System.currentTimeMillis());
        v.put("planned_distance_m",plannedDistance); v.put("planned_duration_s",plannedDuration);
        v.put("planned_json", plannedPoints == null ? "[]" : plannedPoints.toString());
        getWritableDatabase().insertOrThrow("trips", null, v);
        return id;
    }

    public void endTrip(String tripId) {
        ContentValues v = new ContentValues(); v.put("ended_at", System.currentTimeMillis());
        getWritableDatabase().update("trips", v, "trip_id=?", new String[]{tripId});
    }

    public void addWarning(String tripId, String warning) {
        try {
            SQLiteDatabase db = getWritableDatabase();
            String old="[]";
            try (Cursor c=db.rawQuery("SELECT warnings_json FROM trips WHERE trip_id=?",new String[]{tripId})) { if(c.moveToFirst()) old=c.getString(0); }
            JSONArray a=new JSONArray(old); a.put(warning);
            ContentValues v=new ContentValues(); v.put("warnings_json",a.toString());
            db.update("trips",v,"trip_id=?",new String[]{tripId});
        } catch(Exception ignored) { }
    }

    public void incrementReroute(String tripId) {
        getWritableDatabase().execSQL("UPDATE trips SET reroutes=reroutes+1 WHERE trip_id=?",new Object[]{tripId});
    }

    public void addTrackPoint(String tripId, long t, double lat, double lon, Double speed, Double heading, Double accuracy) {
        if(tripId==null || tripId.isEmpty()) return;
        ContentValues v=new ContentValues(); v.put("trip_id",tripId); v.put("t",t); v.put("lat",lat); v.put("lon",lon);
        if(speed!=null)v.put("speed",speed); if(heading!=null)v.put("heading",heading); if(accuracy!=null)v.put("accuracy",accuracy);
        getWritableDatabase().insert("track_points",null,v);
    }

    public int pendingShiftCount() {
        try(Cursor c=getReadableDatabase().rawQuery("SELECT COUNT(*) FROM shifts WHERE ended_at>0 AND uploaded=0",null)){ return c.moveToFirst()?c.getInt(0):0; }
    }

    public int tripCountForShift(String shiftId) {
        try(Cursor c=getReadableDatabase().rawQuery("SELECT COUNT(*) FROM trips WHERE shift_id=?",new String[]{shiftId})){ return c.moveToFirst()?c.getInt(0):0; }
    }

    public List<String> pendingShiftIds() {
        List<String> ids=new ArrayList<>();
        try(Cursor c=getReadableDatabase().rawQuery("SELECT shift_id FROM shifts WHERE ended_at>0 AND uploaded=0 ORDER BY started_at",null)) { while(c.moveToNext()) ids.add(c.getString(0)); }
        return ids;
    }

    public void markShiftUploaded(String shiftId) {
        ContentValues v=new ContentValues();v.put("uploaded",1);v.put("upload_error","");
        getWritableDatabase().update("shifts",v,"shift_id=?",new String[]{shiftId});
    }

    public void markShiftError(String shiftId,String error) {
        ContentValues v=new ContentValues();v.put("upload_error",error==null?"":error);
        getWritableDatabase().update("shifts",v,"shift_id=?",new String[]{shiftId});
    }

    public JSONObject shiftPayload(String shiftId, String deviceId, String deviceName) throws Exception {
        SQLiteDatabase db=getReadableDatabase();
        JSONObject root=new JSONObject(); root.put("device_id",deviceId);root.put("device_name",deviceName);root.put("app_version","5.2.1-android");
        try(Cursor s=db.rawQuery("SELECT started_at,ended_at FROM shifts WHERE shift_id=?",new String[]{shiftId})){
            if(!s.moveToFirst())throw new IllegalStateException("Dienst niet gevonden");
            root.put("shift_id",shiftId);root.put("started_at",s.getLong(0));root.put("ended_at",s.getLong(1));
        }
        JSONArray trips=new JSONArray();
        try(Cursor c=db.rawQuery("SELECT trip_id,destination,started_at,ended_at,planned_distance_m,warnings_json,reroutes,planned_json FROM trips WHERE shift_id=? ORDER BY started_at",new String[]{shiftId})){
            while(c.moveToNext()){
                String tripId=c.getString(0);
                JSONObject t=new JSONObject(); t.put("trip_id",tripId);t.put("destination",c.getString(1));t.put("started_at",c.getLong(2));t.put("ended_at",c.getLong(3));
                t.put("planned_distance_m",c.getDouble(4));t.put("warnings",new JSONArray(c.getString(5)));t.put("reroutes",c.getInt(6));t.put("planned_points",new JSONArray(c.getString(7)));
                JSONArray actual=new JSONArray(); double actualDistance=0; Double lastLat=null,lastLon=null;
                try(Cursor p=db.rawQuery("SELECT t,lat,lon,speed,heading,accuracy FROM track_points WHERE trip_id=? ORDER BY id",new String[]{tripId})){
                    while(p.moveToNext()){
                        double lat=p.getDouble(1),lon=p.getDouble(2);
                        JSONObject pt=new JSONObject();pt.put("t",p.getLong(0));pt.put("lat",lat);pt.put("lon",lon);
                        if(!p.isNull(3))pt.put("speed",p.getDouble(3));if(!p.isNull(4))pt.put("heading",p.getDouble(4));if(!p.isNull(5))pt.put("accuracy",p.getDouble(5));
                        actual.put(pt);
                        if(lastLat!=null)actualDistance+=haversine(lastLat,lastLon,lat,lon); lastLat=lat;lastLon=lon;
                    }
                }
                t.put("actual_points",actual);t.put("actual_distance_m",Math.round(actualDistance)); trips.put(t);
            }
        }
        root.put("trips",trips);return root;
    }

    private static double haversine(double aLat,double aLon,double bLat,double bLon){double r=6371000.0,p1=Math.toRadians(aLat),p2=Math.toRadians(bLat),dp=Math.toRadians(bLat-aLat),dl=Math.toRadians(bLon-aLon);double h=Math.sin(dp/2)*Math.sin(dp/2)+Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)*Math.sin(dl/2);return 2*r*Math.asin(Math.min(1,Math.sqrt(h)));}

    public void saveKnowledge(int revision,String hash,JSONObject knowledge){ContentValues v=new ContentValues();v.put("revision",revision);v.put("hash",hash);v.put("json",knowledge.toString());v.put("updated_at",System.currentTimeMillis());getWritableDatabase().update("knowledge",v,"id=1",null);}
    public int knowledgeRevision(){try(Cursor c=getReadableDatabase().rawQuery("SELECT revision FROM knowledge WHERE id=1",null)){return c.moveToFirst()?c.getInt(0):0;}}
    public String knowledgeHash(){try(Cursor c=getReadableDatabase().rawQuery("SELECT hash FROM knowledge WHERE id=1",null)){return c.moveToFirst()?c.getString(0):"";}}
    public JSONObject knowledge(){try(Cursor c=getReadableDatabase().rawQuery("SELECT json FROM knowledge WHERE id=1",null)){if(c.moveToFirst())return new JSONObject(c.getString(0));}catch(Exception ignored){}return new JSONObject();}

    public JSONObject currentTrip(String tripId){
        if(tripId==null||tripId.isEmpty())return null;
        try(Cursor c=getReadableDatabase().rawQuery("SELECT trip_id,shift_id,destination,dest_lat,dest_lon,started_at,ended_at,planned_distance_m,planned_duration_s,planned_json FROM trips WHERE trip_id=?",new String[]{tripId})){
            if(!c.moveToFirst())return null;JSONObject o=new JSONObject();o.put("trip_id",c.getString(0));o.put("shift_id",c.getString(1));o.put("destination",c.getString(2));o.put("dest_lat",c.getDouble(3));o.put("dest_lon",c.getDouble(4));o.put("started_at",c.getLong(5));o.put("ended_at",c.getLong(6));o.put("planned_distance_m",c.getDouble(7));o.put("planned_duration_s",c.getDouble(8));o.put("planned_points",new JSONArray(c.getString(9)));return o;
        }catch(Exception e){return null;}
    }
}
