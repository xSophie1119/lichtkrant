package nl.routepilot.mobile;

import android.Manifest;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
import org.json.JSONArray;
import org.json.JSONObject;
import org.osmdroid.tileprovider.tilesource.TileSourceFactory;
import org.osmdroid.util.GeoPoint;
import org.osmdroid.views.MapView;
import org.osmdroid.views.overlay.Marker;
import org.osmdroid.views.overlay.Polyline;
import java.util.ArrayList;
import java.util.List;

public class MainActivity extends AppCompatActivity implements LocationListener {
    private MapView map;
    private Marker meMarker,destMarker;
    private Polyline routeLine;
    private TextView topStatus,serviceStatus,routeStatus,syncStatus,arrivalStatus,knowledgeStatus;
    private EditText searchInput;
    private Button shiftButton,tripButton,syncButton,settingsButton,searchButton;
    private LinearLayout alternatives;
    private LocationManager locationManager;
    private Location currentLocation;
    private RoutingClient.Place destination;
    private List<RoutingClient.Route> routeCandidates=new ArrayList<>();
    private RoutingClient.Route selectedRoute;
    private RoutePilotDb db;
    private SharedPreferences prefs;
    private KnowledgeEngine knowledge;
    private final ActivityResultLauncher<String[]> permissions=registerForActivityResult(new ActivityResultContracts.RequestMultiplePermissions(),r->startLocationUpdates());

    @Override protected void onCreate(Bundle state){
        super.onCreate(state);db=RoutePilotDb.get(this);prefs=RoutePilotApp.prefs(this);knowledge=new KnowledgeEngine(db.knowledge());
        locationManager=(LocationManager)getSystemService(LOCATION_SERVICE);buildUi();refreshUi();showPreviousCrashIfAny();requestLocationPermissions();
        if(!prefs.getString(RoutePilotApp.KEY_SERVER_URL,"").trim().isEmpty())SyncManager.syncAsync(this,(ok,msg)->{syncStatus.setText(msg);knowledge=new KnowledgeEngine(db.knowledge());refreshUi();});
    }

    private void buildUi(){
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setBackgroundColor(Color.rgb(245,247,251));
        LinearLayout header=new LinearLayout(this);header.setGravity(Gravity.CENTER_VERTICAL);header.setPadding(dp(14),dp(10),dp(10),dp(8));header.setBackgroundColor(Color.rgb(33,71,217));
        TextView title=new TextView(this);title.setText("RoutePilot V5");title.setTextColor(Color.WHITE);title.setTextSize(22);title.setTypeface(null,1);header.addView(title,new LinearLayout.LayoutParams(0,dp(48),1));
        settingsButton=button("⚙");settingsButton.setOnClickListener(v->showSettings());header.addView(settingsButton,new LinearLayout.LayoutParams(dp(54),dp(48)));
        root.addView(header);
        topStatus=new TextView(this);topStatus.setPadding(dp(14),dp(7),dp(14),dp(7));topStatus.setTextColor(Color.DKGRAY);topStatus.setTextSize(13);root.addView(topStatus,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT));

        map=new MapView(this);map.setTileSource(TileSourceFactory.MAPNIK);map.setMultiTouchControls(true);map.getController().setZoom(13.5);map.getController().setCenter(new GeoPoint(51.5606,5.0919));root.addView(map,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,0,1));

        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(false);LinearLayout panel=new LinearLayout(this);panel.setOrientation(LinearLayout.VERTICAL);panel.setPadding(dp(12),dp(10),dp(12),dp(20));scroll.addView(panel);root.addView(scroll,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(340)));

        serviceStatus=label(panel,"Dienst",17,true);knowledgeStatus=label(panel,"",12,false);
        LinearLayout shiftRow=row(panel);shiftButton=button("Dienst starten");shiftButton.setOnClickListener(v->toggleShift());shiftRow.addView(shiftButton,new LinearLayout.LayoutParams(0,dp(50),1));syncButton=button("↕ Sync");syncButton.setOnClickListener(v->manualSync());shiftRow.addView(syncButton,new LinearLayout.LayoutParams(dp(115),dp(50)));
        syncStatus=label(panel,"Nog niet gesynchroniseerd",12,false);

        searchInput=new EditText(this);searchInput.setHint("Adres of zorglocatie zoeken…");searchInput.setSingleLine(true);searchInput.setTextSize(16);panel.addView(searchInput,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(52)));
        searchButton=button("Zoek route");searchButton.setOnClickListener(v->searchDestination());panel.addView(searchButton,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(50)));
        routeStatus=label(panel,"Nog geen route gekozen",13,false);
        HorizontalScrollView hs=new HorizontalScrollView(this);alternatives=new LinearLayout(this);alternatives.setOrientation(LinearLayout.HORIZONTAL);hs.addView(alternatives);panel.addView(hs,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(58)));
        arrivalStatus=label(panel,"",13,true);
        tripButton=button("Rit starten");tripButton.setOnClickListener(v->toggleTrip());panel.addView(tripButton,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(54)));
        setContentView(root);
    }

    private TextView label(LinearLayout parent,String text,int size,boolean bold){TextView t=new TextView(this);t.setText(text);t.setTextSize(size);t.setTextColor(Color.rgb(35,38,44));t.setPadding(dp(2),dp(5),dp(2),dp(5));if(bold)t.setTypeface(null,1);parent.addView(t,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT));return t;}
    private LinearLayout row(LinearLayout parent){LinearLayout r=new LinearLayout(this);r.setOrientation(LinearLayout.HORIZONTAL);r.setPadding(0,dp(4),0,dp(4));parent.addView(r,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT));return r;}
    private Button button(String text){Button b=new Button(this);b.setText(text);b.setTextSize(15);b.setAllCaps(false);return b;}
    private int dp(int d){return Math.round(d*getResources().getDisplayMetrics().density);}

    private void requestLocationPermissions(){List<String> p=new ArrayList<>();if(ContextCompat.checkSelfPermission(this,Manifest.permission.ACCESS_FINE_LOCATION)!=PackageManager.PERMISSION_GRANTED)p.add(Manifest.permission.ACCESS_FINE_LOCATION);if(Build.VERSION.SDK_INT>=33&&ContextCompat.checkSelfPermission(this,Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)p.add(Manifest.permission.POST_NOTIFICATIONS);if(p.isEmpty())startLocationUpdates();else permissions.launch(p.toArray(new String[0]));}
    private void startLocationUpdates(){if(ContextCompat.checkSelfPermission(this,Manifest.permission.ACCESS_FINE_LOCATION)!=PackageManager.PERMISSION_GRANTED)return;try{locationManager.requestLocationUpdates(LocationManager.GPS_PROVIDER,2500,2,this);}catch(Exception ignored){}try{Location l=locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER);if(l!=null)onLocationChanged(l);}catch(Exception ignored){}}

    @Override public void onLocationChanged(Location location){currentLocation=location;updateMeMarker(location);updateArrival();}
    private void updateMeMarker(Location l){GeoPoint p=new GeoPoint(l.getLatitude(),l.getLongitude());if(meMarker==null){meMarker=new Marker(map);meMarker.setTitle("Huidige positie");map.getOverlays().add(meMarker);}meMarker.setPosition(p);if(map.getZoomLevelDouble()<12)map.getController().setZoom(14);map.invalidate();}

    private void toggleShift(){String shift=prefs.getString(RoutePilotApp.KEY_ACTIVE_SHIFT,"");if(shift.isEmpty()){shift=db.startShift();prefs.edit().putString(RoutePilotApp.KEY_ACTIVE_SHIFT,shift).apply();toast("Dienst gestart. Echte ritten worden lokaal bewaard.");}else{String trip=prefs.getString(RoutePilotApp.KEY_ACTIVE_TRIP,"");if(!trip.isEmpty()){toast("Beëindig eerst de actieve rit.");return;}db.endShift(shift);prefs.edit().remove(RoutePilotApp.KEY_ACTIVE_SHIFT).apply();toast("Dienst beëindigd • routes worden naar de webapp gestuurd zodra die bereikbaar is.");manualSync();}refreshUi();}

    private void searchDestination(){String q=searchInput.getText().toString().trim();if(q.length()<3){toast("Vul minimaal 3 tekens in.");return;}if(currentLocation==null){toast("Wacht nog even op GPS.");return;}searchButton.setEnabled(false);routeStatus.setText("Adres zoeken…");RoutingClient.geocode(q,(places,error)->runOnUiThread(()->{searchButton.setEnabled(true);if(error!=null){routeStatus.setText("Zoeken mislukt: "+error);return;}String[] labels=new String[places.size()];for(int i=0;i<places.size();i++)labels[i]=places.get(i).name;new AlertDialog.Builder(this).setTitle("Kies bestemming").setItems(labels,(d,which)->chooseDestination(places.get(which))).show();}));}

    private void chooseDestination(RoutingClient.Place p){JSONObject stop=knowledge.bestStopNear(p.lat,p.lon);if(stop!=null){double la=stop.optDouble("lat",p.lat),lo=stop.optDouble("lon",p.lon);destination=new RoutingClient.Place(p.name+" • geleerd stoppunt",la,lo,p.type);routeStatus.setText("Geleerd WMO-stoppunt gebruikt voor "+p.name);}else destination=p;showDestinationMarker();calculateRoutes();}
    private void showDestinationMarker(){if(destination==null)return;if(destMarker==null){destMarker=new Marker(map);map.getOverlays().add(destMarker);}destMarker.setPosition(new GeoPoint(destination.lat,destination.lon));destMarker.setTitle(destination.name);map.invalidate();}

    private void calculateRoutes(){if(currentLocation==null||destination==null)return;routeStatus.setText("RoutePilot probeert meerdere routes…");searchButton.setEnabled(false);RoutingClient.route(currentLocation.getLatitude(),currentLocation.getLongitude(),destination.lat,destination.lon,knowledge,(routes,error)->runOnUiThread(()->{searchButton.setEnabled(true);if(error!=null||routes.isEmpty()){routeStatus.setText("Routeren mislukt: "+(error==null?"geen route":error));return;}routeCandidates=routes;selectRoute(0);renderAlternatives();}));}
    private void renderAlternatives(){alternatives.removeAllViews();for(int i=0;i<routeCandidates.size();i++){RoutingClient.Route r=routeCandidates.get(i);Button b=button((i==0?"🏆 ":"")+r.label());final int idx=i;b.setOnClickListener(v->selectRoute(idx));alternatives.addView(b,new LinearLayout.LayoutParams(dp(155),dp(52)));}}
    private void selectRoute(int idx){if(idx<0||idx>=routeCandidates.size())return;selectedRoute=routeCandidates.get(idx);drawRoute(selectedRoute);String extra=selectedRoute.dominated?" • langer én langzamer dan een alternatief":"";routeStatus.setText("Gekozen: "+selectedRoute.label()+" • "+selectedRoute.source+extra+" • RoutePilot-score "+Math.round(selectedRoute.score));}
    private void drawRoute(RoutingClient.Route r){if(routeLine!=null)map.getOverlays().remove(routeLine);routeLine=new Polyline();routeLine.setColor(Color.rgb(33,71,217));routeLine.setWidth(10f);List<GeoPoint> pts=new ArrayList<>();for(int i=0;i<r.coords.length();i++){JSONArray p=r.coords.optJSONArray(i);if(p!=null&&p.length()>=2)pts.add(new GeoPoint(p.optDouble(1),p.optDouble(0)));}routeLine.setPoints(pts);map.getOverlays().add(routeLine);if(!pts.isEmpty())map.zoomToBoundingBox(routeLine.getBounds(),true,dp(48));map.invalidate();}

    private void toggleTrip(){String trip=prefs.getString(RoutePilotApp.KEY_ACTIVE_TRIP,"");if(trip.isEmpty()){startTrip();}else endTrip();}
    private void startTrip(){String shift=prefs.getString(RoutePilotApp.KEY_ACTIVE_SHIFT,"");if(shift.isEmpty()){toast("Start eerst je dienst.");return;}if(destination==null||selectedRoute==null){toast("Kies eerst een route.");return;}String trip=db.startTrip(shift,destination.name,destination.lat,destination.lon,selectedRoute.distance,selectedRoute.duration,selectedRoute.coords);prefs.edit().putString(RoutePilotApp.KEY_ACTIVE_TRIP,trip).apply();ContextCompat.startForegroundService(this,new Intent(this,TrackingService.class));toast("Rit gestart • echte GPS-route wordt vastgelegd.");refreshUi();}
    private void endTrip(){String trip=prefs.getString(RoutePilotApp.KEY_ACTIVE_TRIP,"");if(trip.isEmpty())return;db.endTrip(trip);prefs.edit().remove(RoutePilotApp.KEY_ACTIVE_TRIP).apply();stopService(new Intent(this,TrackingService.class));toast("Rit opgeslagen als echte trainingsrit.");refreshUi();}

    private void updateArrival(){String trip=prefs.getString(RoutePilotApp.KEY_ACTIVE_TRIP,"");if(trip.isEmpty()||destination==null||currentLocation==null){arrivalStatus.setText("");return;}double d=KnowledgeEngine.dist(currentLocation.getLatitude(),currentLocation.getLongitude(),destination.lat,destination.lon);if(d<700){arrivalStatus.setText("Aankomstmodus • nog "+Math.round(d)+" m • let op geschikt stoppunt en houd ruimte achter de bus voor de lift.");}else arrivalStatus.setText("");}

    private void manualSync(){syncButton.setEnabled(false);syncStatus.setText("Synchroniseren: echte ritten ↑ • trainingskennis ↓ …");SyncManager.syncAsync(this,(ok,msg)->{syncButton.setEnabled(true);syncStatus.setText(msg);knowledge=new KnowledgeEngine(db.knowledge());refreshUi();});}

    private void showSettings(){
        LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);int p=dp(18);box.setPadding(p,p,p,0);
        EditText url=new EditText(this);url.setHint("http://192.168.1.20:8765");url.setText(prefs.getString(RoutePilotApp.KEY_SERVER_URL,""));url.setSingleLine(true);box.addView(url);
        EditText token=new EditText(this);token.setHint("Portal token (optioneel)");token.setText(prefs.getString(RoutePilotApp.KEY_SERVER_TOKEN,""));token.setSingleLine(true);token.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);box.addView(token);
        TextView info=new TextView(this);info.setPadding(0,dp(12),0,0);info.setText("Na iedere dienst: echte GPS-ritten → webapp.\nBij sync: nieuwe RoutePilot-kennis → Android.\nGeen verbinding? Ritten blijven veilig pending.");box.addView(info);
        new AlertDialog.Builder(this).setTitle("RoutePilot Sync").setView(box).setNegativeButton("Annuleren",null).setPositiveButton("Opslaan",(d,w)->{prefs.edit().putString(RoutePilotApp.KEY_SERVER_URL,url.getText().toString().trim()).putString(RoutePilotApp.KEY_SERVER_TOKEN,token.getText().toString().trim()).apply();refreshUi();manualSync();}).show();
    }

    private void refreshUi(){
        String shift=prefs.getString(RoutePilotApp.KEY_ACTIVE_SHIFT,"");String trip=prefs.getString(RoutePilotApp.KEY_ACTIVE_TRIP,"");
        shiftButton.setText(shift.isEmpty()?"Dienst starten":"Dienst beëindigen");tripButton.setText(trip.isEmpty()?"Rit starten":"Rit beëindigen");
        serviceStatus.setText(shift.isEmpty()?"Geen actieve dienst":"Dienst actief • "+db.tripCountForShift(shift)+" rit(ten) geregistreerd"+(trip.isEmpty()?"":" • rit loopt"));
        KnowledgeEngine k=new KnowledgeEngine(db.knowledge());knowledgeStatus.setText("Kennis rev "+db.knowledgeRevision()+" • "+k.counts()+" • pending diensten: "+db.pendingShiftCount());
        long last=prefs.getLong("last_sync_at",0);String err=prefs.getString("last_sync_error","");if(last>0&&syncStatus.getText().toString().equals("Nog niet gesynchroniseerd"))syncStatus.setText("Laatste sync: "+android.text.format.DateFormat.format("HH:mm",last)+(err.isEmpty()?"":" • "+err));
        String server=prefs.getString(RoutePilotApp.KEY_SERVER_URL,"");topStatus.setText((trip.isEmpty()?"CHAUFFEURMODUS":"● LIVE RIT")+" • "+(server.isEmpty()?"sync nog niet ingesteld":"2-richtingen-sync actief"));
        if(!trip.isEmpty()){JSONObject t=db.currentTrip(trip);if(t!=null&&destination==null){destination=new RoutingClient.Place(t.optString("destination"),t.optDouble("dest_lat"),t.optDouble("dest_lon"),"");showDestinationMarker();}}
        updateArrival();
    }

    private void showPreviousCrashIfAny(){
        String crash=CrashLogger.consumeLastCrash(this);
        if(crash==null||crash.isEmpty())return;
        String compact=crash.length()>6500?crash.substring(0,6500)+"\n…":crash;
        new AlertDialog.Builder(this)
                .setTitle("RoutePilot hersteld na een crash")
                .setMessage(compact)
                .setPositiveButton("Sluiten",null)
                .show();
    }

    private void toast(String s){Toast.makeText(this,s,Toast.LENGTH_LONG).show();}
    @Override protected void onResume(){super.onResume();map.onResume();refreshUi();}
    @Override protected void onPause(){map.onPause();super.onPause();}
    @Override protected void onDestroy(){try{locationManager.removeUpdates(this);}catch(Exception ignored){}super.onDestroy();}
}
