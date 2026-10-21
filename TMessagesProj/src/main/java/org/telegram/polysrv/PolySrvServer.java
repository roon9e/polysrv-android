package org.telegram.polysrv;

import org.json.JSONException;
import org.json.JSONObject;

public class PolySrvServer {
    public String id;
    public String name;
    public String host;
    public int port;
    public String description = "";
    public String rsaPublicKey = "";
    public long rsaKeyFingerprint = 0;
    public String logoPath = "";
    public boolean isOfficial;
    public boolean isTelegram;
    public boolean multiDc;
    public int mainDcId;

    public int effectiveMainDcId() {
        if (mainDcId > 0) return mainDcId;
        return multiDc ? 2 : 1;
    }

    public JSONObject toJson() throws JSONException {
        JSONObject obj = new JSONObject();
        obj.put("id", id);
        obj.put("name", name);
        obj.put("host", host);
        obj.put("port", port);
        if (description != null && !description.isEmpty()) obj.put("description", description);
        if (rsaPublicKey != null && !rsaPublicKey.isEmpty()) obj.put("rsaPublicKey", rsaPublicKey);
        if (logoPath != null && !logoPath.isEmpty()) obj.put("logoPath", logoPath);
        if (multiDc) obj.put("multiDc", true);
        if (mainDcId > 0) obj.put("mainDcId", mainDcId);
        return obj;
    }

    public static PolySrvServer fromJson(JSONObject obj) throws JSONException {
        PolySrvServer s = new PolySrvServer();
        s.id = obj.getString("id");
        s.name = obj.getString("name");
        s.host = obj.getString("host");
        s.port = obj.getInt("port");
        s.description = obj.optString("description", "");
        s.rsaPublicKey = obj.optString("rsaPublicKey", "");
        s.logoPath = obj.optString("logoPath", "");
        s.isOfficial = false;
        s.multiDc = obj.optBoolean("multiDc", false);
        s.mainDcId = obj.optInt("mainDcId", 0);
        return s;
    }
}
