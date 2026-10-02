package nl.routepilot.mobile;

import android.app.Application;
import android.content.Context;
import android.content.SharedPreferences;
import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import org.osmdroid.config.Configuration;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

public class RoutePilotApp extends Application {
    public static final String PREFS = "routepilot_prefs";
    public static final String KEY_SERVER_URL = "server_url";
    public static final String KEY_SERVER_TOKEN = "server_token";
    public static final String KEY_DEVICE_ID = "device_id";
    public static final String KEY_DEVICE_NAME = "device_name";
    public static final String KEY_ACTIVE_SHIFT = "active_shift";
    public static final String KEY_ACTIVE_TRIP = "active_trip";
    public static final String KEY_LAST_LAT = "last_lat";
    public static final String KEY_LAST_LON = "last_lon";
    public static final String KEY_LAST_LOCATION_AT = "last_location_at";

    @Override public void onCreate() {
        super.onCreate();
        Configuration.getInstance().setUserAgentValue(getPackageName() + "/5.2.1");
        prefs(this);
        scheduleBackgroundSync(this);
    }

    public static SharedPreferences prefs(Context c) {
        SharedPreferences p = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        if (!p.contains(KEY_DEVICE_ID)) {
            p.edit().putString(KEY_DEVICE_ID, UUID.randomUUID().toString()).apply();
        }
        if (!p.contains(KEY_DEVICE_NAME)) {
            p.edit().putString(KEY_DEVICE_NAME, android.os.Build.MANUFACTURER + " " + android.os.Build.MODEL).apply();
        }
        return p;
    }

    public static void scheduleBackgroundSync(Context context) {
        Constraints constraints = new Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build();
        PeriodicWorkRequest work = new PeriodicWorkRequest.Builder(SyncWorker.class, 15, TimeUnit.MINUTES)
                .setConstraints(constraints).build();
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                "routepilot-bidirectional-sync", ExistingPeriodicWorkPolicy.UPDATE, work);
    }
}
