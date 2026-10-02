package nl.routepilot.mobile;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Build;
import android.os.IBinder;
import androidx.annotation.Nullable;
import androidx.core.app.ActivityCompat;
import androidx.core.app.NotificationCompat;

public class TrackingService extends Service implements LocationListener {
    private static final String CHANNEL="routepilot_tracking";private LocationManager lm;
    @Override public void onCreate(){super.onCreate();createChannel();lm=(LocationManager)getSystemService(LOCATION_SERVICE);}
    @Override public int onStartCommand(Intent intent,int flags,int startId){startForeground(42,notification());requestUpdates();return START_STICKY;}
    private void requestUpdates(){if(ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)!= PackageManager.PERMISSION_GRANTED)return;try{lm.requestLocationUpdates(LocationManager.GPS_PROVIDER,2500,3,this);}catch(Exception ignored){}try{lm.requestLocationUpdates(LocationManager.NETWORK_PROVIDER,5000,8,this);}catch(Exception ignored){}}
    @Override public void onLocationChanged(Location loc){String trip=RoutePilotApp.prefs(this).getString(RoutePilotApp.KEY_ACTIVE_TRIP,"");if(trip==null||trip.isEmpty())return;RoutePilotDb.get(this).addTrackPoint(trip,System.currentTimeMillis(),loc.getLatitude(),loc.getLongitude(),loc.hasSpeed()?(double)loc.getSpeed():null,loc.hasBearing()?(double)loc.getBearing():null,loc.hasAccuracy()?(double)loc.getAccuracy():null);RoutePilotApp.prefs(this).edit().putLong(RoutePilotApp.KEY_LAST_LAT,Double.doubleToRawLongBits(loc.getLatitude())).putLong(RoutePilotApp.KEY_LAST_LON,Double.doubleToRawLongBits(loc.getLongitude())).putLong(RoutePilotApp.KEY_LAST_LOCATION_AT,System.currentTimeMillis()).apply();}
    @Override public void onDestroy(){if(lm!=null)try{lm.removeUpdates(this);}catch(Exception ignored){}super.onDestroy();}
    private Notification notification(){Intent open=new Intent(this,MainActivity.class);PendingIntent pi=PendingIntent.getActivity(this,0,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);return new NotificationCompat.Builder(this,CHANNEL).setSmallIcon(android.R.drawable.ic_menu_mylocation).setContentTitle("RoutePilot registreert de echte rit").setContentText("GPS-track wordt lokaal bewaard voor training na je dienst.").setOngoing(true).setContentIntent(pi).build();}
    private void createChannel(){if(Build.VERSION.SDK_INT>=26){NotificationChannel ch=new NotificationChannel(CHANNEL,"RoutePilot ritregistratie",NotificationManager.IMPORTANCE_LOW);((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(ch);}}
    @Nullable @Override public IBinder onBind(Intent intent){return null;}
}
