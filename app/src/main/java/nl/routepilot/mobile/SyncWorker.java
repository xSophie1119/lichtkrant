package nl.routepilot.mobile;
import android.content.Context;
import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

public class SyncWorker extends Worker {
    public SyncWorker(@NonNull Context context,@NonNull WorkerParameters params){super(context,params);}
    @NonNull @Override public Result doWork(){
        if(RoutePilotApp.prefs(getApplicationContext()).getString(RoutePilotApp.KEY_SERVER_URL,"").trim().isEmpty())return Result.success();
        SyncManager.SyncResult r=SyncManager.syncBlocking(getApplicationContext());return r.ok?Result.success():Result.retry();
    }
}
