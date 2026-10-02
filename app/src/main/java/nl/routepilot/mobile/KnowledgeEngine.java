package nl.routepilot.mobile;

import org.json.JSONArray;
import org.json.JSONObject;

public final class KnowledgeEngine {
    private final JSONObject knowledge;
    public KnowledgeEngine(JSONObject knowledge){this.knowledge=knowledge==null?new JSONObject():knowledge;}

    public double scoreRoute(JSONArray coords,double baseScore){
        double score=baseScore;
        JSONArray corrections=knowledge.optJSONArray("corrections");
        if(corrections!=null){for(int i=0;i<corrections.length();i++){
            JSONObject c=corrections.optJSONObject(i);if(c==null||c.optInt("active",1)==0)continue;
            double lat=c.optDouble("lat",Double.NaN),lon=c.optDouble("lon",Double.NaN);if(Double.isNaN(lat)||Double.isNaN(lon))continue;
            double d=minDistance(lat,lon,coords);double radius=Math.max(15,c.optDouble("radius_m",60));if(d>radius)continue;
            String type=c.optString("type","");int strength=Math.max(1,c.optInt("strength",1));
            if(type.equals("avoid")||type.equals("road_closed")||type.equals("too_narrow")||type.equals("bus_trap")||type.equals("height_block")||type.equals("bus_lane_forbidden"))score+=5000.0*strength;
            else if(type.equals("prefer"))score-=Math.min(25,5.0*strength);
            else if(type.equals("good_stop"))score-=Math.min(40,15.0*strength);
            else if(type.equals("bad_stop"))score+=250.0*strength;
        }}
        JSONArray patterns=knowledge.optJSONArray("learning_patterns");
        if(patterns!=null){for(int i=0;i<patterns.length();i++){
            JSONObject p=patterns.optJSONObject(i);if(p==null||!p.optBoolean("apply_to_routing",false))continue;JSONArray g=p.optJSONArray("geometry");if(g==null||g.length()<2)continue;
            if(geometriesNear(g,coords,75)){double confidence=p.optDouble("confidence",0.5);String status=p.optString("status","");double bonus=status.contains("trusted")?18:8;score-=bonus*Math.max(0.5,confidence);}
        }}
        return score;
    }

    public JSONObject bestStopNear(double lat,double lon){
        JSONArray corrections=knowledge.optJSONArray("corrections");JSONObject best=null;double bestD=Double.MAX_VALUE;if(corrections==null)return null;
        for(int i=0;i<corrections.length();i++){JSONObject c=corrections.optJSONObject(i);if(c==null||!"good_stop".equals(c.optString("type")))continue;double la=c.optDouble("lat",Double.NaN),lo=c.optDouble("lon",Double.NaN);if(Double.isNaN(la)||Double.isNaN(lo))continue;double d=dist(lat,lon,la,lo);if(d<350&&d<bestD){best=c;bestD=d;}}
        return best;
    }

    public String counts(){
        int c=len("corrections"),p=len("learning_patterns"),l=len("training_locations"),b=len("tilburg_bus_lanes");return c+" correcties • "+p+" patronen • "+l+" locaties • "+b+" busbanen";
    }
    private int len(String k){JSONArray a=knowledge.optJSONArray(k);return a==null?0:a.length();}
    private static boolean geometriesNear(JSONArray a,JSONArray b,double max){int stepA=Math.max(1,a.length()/40),stepB=Math.max(1,b.length()/100);for(int i=0;i<a.length();i+=stepA){double[] p=point(a.optJSONArray(i));if(p==null)continue;for(int j=0;j<b.length();j+=stepB){double[] q=point(b.optJSONArray(j));if(q!=null&&dist(p[0],p[1],q[0],q[1])<=max)return true;}}return false;}
    private static double minDistance(double lat,double lon,JSONArray coords){double best=Double.MAX_VALUE;int step=Math.max(1,coords.length()/500);for(int i=0;i<coords.length();i+=step){double[] p=point(coords.optJSONArray(i));if(p!=null)best=Math.min(best,dist(lat,lon,p[0],p[1]));}return best;}
    private static double[] point(JSONArray p){if(p==null||p.length()<2)return null;double lon=p.optDouble(0,Double.NaN),lat=p.optDouble(1,Double.NaN);if(Double.isNaN(lat)||Double.isNaN(lon))return null;return new double[]{lat,lon};}
    public static double dist(double aLat,double aLon,double bLat,double bLon){double r=6371000,p1=Math.toRadians(aLat),p2=Math.toRadians(bLat),dp=Math.toRadians(bLat-aLat),dl=Math.toRadians(bLon-aLon);double h=Math.sin(dp/2)*Math.sin(dp/2)+Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)*Math.sin(dl/2);return 2*r*Math.asin(Math.min(1,Math.sqrt(h)));}
}
