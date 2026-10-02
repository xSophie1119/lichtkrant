package nl.routepilot.mobile;

import android.content.Context;
import android.content.SharedPreferences;
import java.io.PrintWriter;
import java.io.StringWriter;

public final class CrashLogger {
    private static final String KEY_CRASH = "last_crash";
    private static final String KEY_CRASH_AT = "last_crash_at";
    private CrashLogger(){}

    public static void install(Context context){
        final Context app=context.getApplicationContext();
        final Thread.UncaughtExceptionHandler previous=Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((thread,error)->{
            try{
                StringWriter sw=new StringWriter();
                error.printStackTrace(new PrintWriter(sw));
                SharedPreferences p=RoutePilotApp.prefs(app);
                p.edit().putString(KEY_CRASH,sw.toString()).putLong(KEY_CRASH_AT,System.currentTimeMillis()).commit();
            }catch(Throwable ignored){}
            if(previous!=null) previous.uncaughtException(thread,error);
        });
    }

    public static String consumeLastCrash(Context context){
        SharedPreferences p=RoutePilotApp.prefs(context);
        String s=p.getString(KEY_CRASH,"");
        if(s==null||s.isEmpty()) return "";
        p.edit().remove(KEY_CRASH).apply();
        return s;
    }

    public static void noteNonFatal(Context context,Throwable error){
        try{
            StringWriter sw=new StringWriter();error.printStackTrace(new PrintWriter(sw));
            RoutePilotApp.prefs(context).edit().putString("last_nonfatal",sw.toString()).putLong("last_nonfatal_at",System.currentTimeMillis()).apply();
        }catch(Throwable ignored){}
    }
}
