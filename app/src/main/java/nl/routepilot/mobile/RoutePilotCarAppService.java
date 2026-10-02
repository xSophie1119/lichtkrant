package nl.routepilot.mobile;

import android.content.Intent;
import androidx.annotation.NonNull;
import androidx.car.app.CarAppService;
import androidx.car.app.CarContext;
import androidx.car.app.Screen;
import androidx.car.app.Session;
import androidx.car.app.model.Action;
import androidx.car.app.model.Pane;
import androidx.car.app.model.PaneTemplate;
import androidx.car.app.model.Row;
import androidx.car.app.model.Template;
import androidx.car.app.validation.HostValidator;
import org.json.JSONObject;

public class RoutePilotCarAppService extends CarAppService {
    @NonNull @Override public HostValidator createHostValidator(){return HostValidator.ALLOW_ALL_HOSTS_VALIDATOR;}
    @NonNull @Override public Session onCreateSession(){return new RoutePilotSession();}

    static class RoutePilotSession extends Session {
        @NonNull @Override public Screen onCreateScreen(@NonNull Intent intent){return new RoutePilotScreen(getCarContext());}
    }

    static class RoutePilotScreen extends Screen {
        RoutePilotScreen(@NonNull CarContext context){super(context);}
        @NonNull @Override public Template onGetTemplate(){
            String shift=RoutePilotApp.prefs(getCarContext()).getString(RoutePilotApp.KEY_ACTIVE_SHIFT,"");
            String trip=RoutePilotApp.prefs(getCarContext()).getString(RoutePilotApp.KEY_ACTIVE_TRIP,"");
            RoutePilotDb db=RoutePilotDb.get(getCarContext());
            Pane.Builder pane=new Pane.Builder();
            pane.addRow(new Row.Builder().setTitle(shift.isEmpty()?"Geen actieve dienst":"Dienst actief").addText(shift.isEmpty()?"Start je dienst op de telefoon.":"Echte routes worden automatisch geregistreerd.").build());
            if(!trip.isEmpty()){
                JSONObject t=db.currentTrip(trip);String dest=t==null?"Actieve rit":t.optString("destination","Actieve rit");
                pane.addRow(new Row.Builder().setTitle("Navigatie actief").addText(dest).build());
            }else if(!shift.isEmpty())pane.addRow(new Row.Builder().setTitle("Klaar voor volgende rit").addText("Kies de bestemming op je telefoon.").build());
            pane.addRow(new Row.Builder().setTitle("RoutePilot kennis").addText("Revision "+db.knowledgeRevision()+" • pending diensten "+db.pendingShiftCount()).build());
            return new PaneTemplate.Builder(pane.build()).setTitle("RoutePilot").setHeaderAction(Action.APP_ICON).build();
        }
    }
}
