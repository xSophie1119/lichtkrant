package nl.routepilot.mobile;

import org.json.JSONArray;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class RoutingClient {
    private static final ExecutorService EXEC=Executors.newFixedThreadPool(2);
    private RoutingClient(){}
    public interface GeocodeCallback{void result(List<Place> places,String error);}
    public interface RouteCallback{void result(List<Route> routes,String error);}

    public static void geocode(String query,GeocodeCallback cb){EXEC.execute(()->{
        List<Place> out=new ArrayList<>();String error=null;
        try{
            String u="https://api.pdok.nl/bzk/locatieserver/search/v3_1/free?q="+URLEncoder.encode(query,"UTF-8")+"&rows=7&fl=weergavenaam,centroide_ll,type,gemeentenaam&wt=json";
            JSONObject root=getJson(u);JSONObject response=root.optJSONObject("response");JSONArray docs=response==null?null:response.optJSONArray("docs");
            if(docs!=null)for(int i=0;i<docs.length();i++){JSONObject d=docs.optJSONObject(i);if(d==null)continue;double[] p=parseWkt(d.optString("centroide_ll"));if(p==null)continue;out.add(new Place(d.optString("weergavenaam","Onbekende locatie"),p[0],p[1],d.optString("type","")));}
            if(out.isEmpty())error="Geen adres gevonden";
        }catch(Exception ex){error=ex.getMessage();}
        cb.result(out,error);
    });}

    public static void route(double fromLat,double fromLon,double toLat,double toLon,KnowledgeEngine knowledge,RouteCallback cb){EXEC.execute(()->{
        List<Route> out=new ArrayList<>();String error=null;
        try{
            String u="https://router.project-osrm.org/route/v1/driving/"+fromLon+","+fromLat+";"+toLon+","+toLat+"?overview=full&geometries=geojson&alternatives=true&steps=false";
            JSONObject root=getJson(u);if(!"Ok".equalsIgnoreCase(root.optString("code","Ok")))throw new Exception(root.optString("message","Router kon geen route vinden"));
            JSONArray routes=root.optJSONArray("routes");if(routes==null||routes.length()==0)throw new Exception("Geen route gevonden");
            for(int i=0;i<routes.length();i++){JSONObject r=routes.optJSONObject(i);JSONObject geom=r.optJSONObject("geometry");JSONArray coords=geom==null?null:geom.optJSONArray("coordinates");if(coords==null)continue;double distance=r.optDouble("distance",0),duration=r.optDouble("duration",0);double base=duration+distance/50.0;double score=knowledge==null?base:knowledge.scoreRoute(coords,base);out.add(new Route(distance,duration,coords,score,"OSRM alternatief "+(i+1)));}
            addDiversityProbes(out,fromLat,fromLon,toLat,toLon,knowledge);
            dedupe(out);markDominated(out);Collections.sort(out,Comparator.comparingDouble(a->a.dominated?a.score+100000:a.score));
            if(out.size()>5)out=new ArrayList<>(out.subList(0,5));
        }catch(Exception ex){error=ex.getMessage();}
        cb.result(out,error);
    });}

    private static void addDiversityProbes(List<Route> out,double aLat,double aLon,double bLat,double bLon,KnowledgeEngine knowledge){
        if(out.size()>=3)return;double midLat=(aLat+bLat)/2,midLon=(aLon+bLon)/2;double dx=bLon-aLon,dy=bLat-aLat,len=Math.sqrt(dx*dx+dy*dy);if(len<0.01)return;double off=Math.min(0.018,Math.max(0.005,len*0.18));double px=-dy/len*off,py=dx/len*off;
        for(int sign:new int[]{1,-1}){try{double viaLat=midLat+py*sign,viaLon=midLon+px*sign;String u="https://router.project-osrm.org/route/v1/driving/"+aLon+","+aLat+";"+viaLon+","+viaLat+";"+bLon+","+bLat+"?overview=full&geometries=geojson&steps=false";JSONObject root=getJson(u);JSONArray rr=root.optJSONArray("routes");if(rr==null||rr.length()==0)continue;JSONObject r=rr.optJSONObject(0);JSONArray c=r.optJSONObject("geometry").optJSONArray("coordinates");double d=r.optDouble("distance",0),t=r.optDouble("duration",0);double base=t+d/50.0;double score=knowledge==null?base:knowledge.scoreRoute(c,base);out.add(new Route(d,t,c,score,"Ontdekte route"));}catch(Exception ignored){}}
    }

    private static void markDominated(List<Route> routes){for(Route r:routes){for(Route other:routes){if(r==other)continue;if(other.duration<=r.duration&&other.distance<=r.distance&&(other.duration<r.duration||other.distance<r.distance)){r.dominated=true;break;}}}}
    private static void dedupe(List<Route> routes){for(int i=routes.size()-1;i>=0;i--){Route a=routes.get(i);for(int j=0;j<i;j++){Route b=routes.get(j);if(Math.abs(a.distance-b.distance)<80&&Math.abs(a.duration-b.duration)<20){routes.remove(i);break;}}}}
    private static JSONObject getJson(String url)throws Exception{HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();c.setConnectTimeout(8000);c.setReadTimeout(18000);c.setRequestProperty("Accept","application/json");c.setRequestProperty("User-Agent","RoutePilot-Android/5.2.2");int code=c.getResponseCode();java.io.InputStream stream=(code>=200&&code<300)?c.getInputStream():c.getErrorStream();StringBuilder s=new StringBuilder();if(stream!=null)try(BufferedReader r=new BufferedReader(new InputStreamReader(stream,StandardCharsets.UTF_8))){String line;while((line=r.readLine())!=null)s.append(line);}c.disconnect();if(code<200||code>=300)throw new Exception("Routebron HTTP "+code);return new JSONObject(s.toString());}
    private static double[] parseWkt(String text){try{int a=text.indexOf('('),b=text.indexOf(')');if(a<0||b<a)return null;String[] p=text.substring(a+1,b).trim().split("\\s+");double lon=Double.parseDouble(p[0]),lat=Double.parseDouble(p[1]);return new double[]{lat,lon};}catch(Exception e){return null;}}

    public static final class Place{public final String name;public final double lat,lon;public final String type;public Place(String n,double la,double lo,String t){name=n;lat=la;lon=lo;type=t;}}
    public static final class Route{public final double distance,duration,score;public final JSONArray coords;public final String source;public boolean dominated=false;public Route(double d,double t,JSONArray c,double s,String src){distance=d;duration=t;coords=c;score=s;source=src;}public String label(){return Math.round(duration/60.0)+" min • "+String.format(java.util.Locale.US,"%.1f",distance/1000.0)+" km";}}
}
