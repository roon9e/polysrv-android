package org.telegram.polysrv;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONObject;
import android.text.TextUtils;

import org.telegram.messenger.ApplicationLoader;
import org.telegram.messenger.FileLog;
import org.telegram.messenger.UserConfig;
import org.telegram.tgnet.ConnectionsManager;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

public class PolySrvServers {

    private static final String PREFS_NAME = "polysrv_servers";
    private static final String KEY_CUSTOM_SERVERS = "custom_servers";
    private static final String KEY_ACCOUNT_SERVER = "account_server_";

    public static final String ID_TELEGRAM = "telegram";

    // Официальный Telegram (multi-DC, стоковый ключ).
    static final String TELEGRAM_RSA_KEY =
        "-----BEGIN RSA PUBLIC KEY-----\n" +
        "MIIBCgKCAQEA6LszBcC1LGzyr992NzE0ieY+BSaOW622Aa9Bd4ZHLl+TuFQ4lo4g\n" +
        "5nKaMBwK/BIb9xUfg0Q29/2mgIR6Zr9krM7HjuIcCzFvDtr+L0GQjae9H0pRB2OO\n" +
        "62cECs5HKhT5DZ98K33vmWiLowc621dQuwKWSQKjWf50XYFw42h21P2KXUGyp2y/\n" +
        "+aEyZ+uVgLLQbRA1dEjSDZ2iGRy12Mk5gpYc397aYp438fsJoHIgJ2lgMv5h7WY9\n" +
        "t6N/byY9Nw9p21Og3AoXSL2q/2IJ1WRUhebgAdGVMlV1fkuOQoEzR7EdpqtQD9Cs\n" +
        "5+bfo3Nhmcyvk5ftB0WkJ9z6bNZ7yxrP8wIDAQAB\n" +
        "-----END RSA PUBLIC KEY-----";
    static final long TELEGRAM_RSA_FINGERPRINT = 0xd09d1d85de64fd85L;

    // --- Built-in servers ---

    /** Официальный Telegram (multi-DC). */
    public static PolySrvServer telegramServer() {
        PolySrvServer s = new PolySrvServer();
        s.id                 = ID_TELEGRAM;
        s.name               = "Telegram";
        s.description        = "Official Telegram cloud. Sign in with your Telegram account.";
        s.host               = "149.154.167.51";
        s.port               = 443;
        s.isOfficial         = true;
        s.isTelegram         = true;
        s.multiDc            = true;
        s.mainDcId           = 2;
        s.rsaPublicKey       = TELEGRAM_RSA_KEY;
        s.rsaKeyFingerprint  = TELEGRAM_RSA_FINGERPRINT;
        return s;
    }

    // --- Server list ---

    public static List<PolySrvServer> listServers() {
        List<PolySrvServer> result = new ArrayList<>();
        result.add(telegramServer());
        result.addAll(loadCustomServers());
        return result;
    }

    public static PolySrvServer getServerById(String id) {
        if (id == null) return null;
        for (PolySrvServer s : listServers()) {
            if (id.equals(s.id)) return s;
        }
        return null;
    }

    // --- Custom server persistence ---

    public static List<PolySrvServer> loadCustomServers() {
        List<PolySrvServer> result = new ArrayList<>();
        try {
            String json = getPrefs().getString(KEY_CUSTOM_SERVERS, "[]");
            JSONArray array = new JSONArray(json);
            for (int i = 0; i < array.length(); i++) {
                result.add(PolySrvServer.fromJson(array.getJSONObject(i)));
            }
        } catch (Exception e) {
            FileLog.e(e);
        }
        return result;
    }

    private static void saveCustomServers(List<PolySrvServer> customs) {
        try {
            JSONArray array = new JSONArray();
            for (PolySrvServer s : customs) {
                array.put(s.toJson());
            }
            getPrefs().edit().putString(KEY_CUSTOM_SERVERS, array.toString()).apply();
        } catch (Exception e) {
            FileLog.e(e);
        }
    }

    public static void addCustomServer(PolySrvServer server) {
        if (server.id == null || server.id.isEmpty()) {
            server.id = UUID.randomUUID().toString();
        }
        server.isOfficial = false;
        List<PolySrvServer> customs = loadCustomServers();
        customs.add(server);
        saveCustomServers(customs);
    }

    public static void updateCustomServer(PolySrvServer updated) {
        List<PolySrvServer> customs = loadCustomServers();
        for (int i = 0; i < customs.size(); i++) {
            if (updated.id.equals(customs.get(i).id)) {
                customs.set(i, updated);
                saveCustomServers(customs);
                return;
            }
        }
    }

    public static void removeCustomServer(String id) {
        List<PolySrvServer> customs = loadCustomServers();
        for (int i = 0; i < customs.size(); i++) {
            if (id.equals(customs.get(i).id)) {
                customs.remove(i);
                saveCustomServers(customs);
                return;
            }
        }
    }

    // --- Account - server binding ---

    public static String getServerIdForAccount(int accountNum) {
        return getPrefs().getString(KEY_ACCOUNT_SERVER + accountNum, null);
    }

    public static void setServerForAccount(String serverId, int accountNum) {
        getPrefs().edit().putString(KEY_ACCOUNT_SERVER + accountNum, serverId).apply();
    }

    public static PolySrvServer getServerForAccount(int accountNum) {
        return getServerById(getServerIdForAccount(accountNum));
    }

    public static boolean hasServerForAccount(int accountNum) {
        return getServerIdForAccount(accountNum) != null;
    }

    /**
     * Stable key for grouping per-server local device state (currently: recent/frequently-used
     * emoji, see Emoji.java) by backend rather than by device. Two different custom servers do
     * NOT share a document-id namespace — a custom-emoji document id cached while using one
     * never resolves on another (or on official Telegram), so state keyed only by device would
     * leak cross-server ids into every account's UI, permanently unresolvable there (see
     * AnimatedEmojiDrawable.EmojiDocumentFetcher — a not-found custom emoji has no negative
     * cache/timeout, it just stays broken forever). Official Telegram, and anything we can't
     * identify a server for, get "" (the original, unsuffixed storage keys) so existing
     * installs' state is preserved unchanged. Host, not server id, is the actual identity that
     * matters here: the same physical backend added twice under different local ids should
     * still share one scope.
     */
    public static String serverScopeKeyForAccount(int accountNum) {
        PolySrvServer s = getServerForAccount(accountNum);
        if (s == null || s.isTelegram || TextUtils.isEmpty(s.host)) {
            return "";
        }
        return s.host.toLowerCase(java.util.Locale.US);
    }




    /**
     * True when two account slots target the same server. Used so the duplicate
     * login check (same phone / same user id) only triggers within one server —
     * the same phone number on a different server is a different account.
     * Matches by server id, or by resolved endpoint (host:port + Telegram flag)
     * so two profiles pointing at the same machine are still treated as one.
     */
    public static boolean sameAccountServer(int accountA, int accountB) {
        String idA = getServerIdForAccount(accountA);
        String idB = getServerIdForAccount(accountB);
        if (java.util.Objects.equals(idA, idB)) {
            return true;
        }
        PolySrvServer sa = getServerById(idA);
        PolySrvServer sb = getServerById(idB);
        if (sa == null || sb == null) {
            return false;
        }
        return sa.isTelegram == sb.isTelegram
                && sa.port == sb.port
                && sa.host != null && sa.host.equals(sb.host);
    }

    // --- DC application ---

    /**
     * Applies the selected server to the given account, atomically on the network
     * thread. Mirrors desktop ApplyServerToDcOptions + RestoreServerToAccount:
     *   - Telegram:       restore real Telegram DC 1-5, unlock, Telegram RSA key
     *   - Single-server:  map DC 1-5 all to one host:port, lock, server RSA key
     *
     * resetKeys=true clears auth keys (user picked a NEW server -> force re-handshake);
     * resetKeys=false keeps them (startup restore -> reuse the existing session).
     */
    public static void applyServerToAccount(PolySrvServer server, int accountNum) {
        applyServerToAccount(server, accountNum, true);
    }

    public static void applyServerToAccount(PolySrvServer server, int accountNum, boolean resetKeys) {
        if (server == null) return;
        final String key;
        final long fingerprint;
        if (server.isTelegram) {
            key = TELEGRAM_RSA_KEY;
            fingerprint = TELEGRAM_RSA_FINGERPRINT;
        } else if (server.rsaPublicKey != null && !server.rsaPublicKey.isEmpty()) {
            // Custom server with its own RSA key. Pass fingerprint 0 so the native
            // layer derives it from the PEM (we can't compute it in Java).
            key = server.rsaPublicKey;
            fingerprint = (server.rsaKeyFingerprint != 0) ? server.rsaKeyFingerprint : 0;
        } else {
            // Ключ не задан -> стоковый Telegram-ключ (подходит для Telegram-совместимых прокси).
            key = TELEGRAM_RSA_KEY;
            fingerprint = TELEGRAM_RSA_FINGERPRINT;
        }
        int mainDc = server.mainDcId > 0
                ? server.mainDcId
                : (server.isTelegram ? 2 : 1);
        ConnectionsManager.native_applyServerConfig(
                accountNum,
                server.host,
                server.port,
                server.isTelegram,
                mainDc,
                key,
                fingerprint,
                resetKeys);
    }

    /**
     * Called from ApplicationLoader after each account's ConnectionsManager is
     * initialized, to restore the previously selected server config. Does NOT
     * reset auth keys so an already-authorized session keeps working.
     */
    public static void applyStoredServerToAccount(int accountNum) {
        PolySrvServer server = getServerForAccount(accountNum);
        if (server != null) {
            applyServerToAccount(server, accountNum, false);
        }
    }

    // --- Helpers ---

    private static SharedPreferences getPrefs() {
        return ApplicationLoader.applicationContext
                .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    /** Returns true when at least one active account uses a Telegram-official server. */
    public static boolean anyAccountIsTelegram() {
        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {
            if (UserConfig.getInstance(a).isClientActivated()) {
                PolySrvServer s = getServerForAccount(a);
                if (s != null && s.isTelegram) return true;
            }
        }
        return false;
    }




    /**
     * Display name of the server an account is on, or null if unknown. Used for
     * the main app header so it shows the current server instead of "Telegram".
     */
    public static String serverNameForAccount(int accountNum) {
        PolySrvServer s = getServerForAccount(accountNum);
        return (s != null) ? s.name : null;
    }

    // --- Account limits (mirrors desktop: premium cap is Telegram-only) ---

    /** First unused account slot (any server), or -1 if all slots are taken. */
    public static int firstFreeAccountSlot() {
        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {
            if (!UserConfig.getInstance(a).isClientActivated()) {
                return a;
            }
        }
        return -1;
    }

    /** Number of activated accounts on a Telegram-official server. */
    public static int countTelegramAccounts() {
        int n = 0;
        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {
            if (UserConfig.getInstance(a).isClientActivated()) {
                PolySrvServer s = getServerForAccount(a);
                if (s != null && s.isTelegram) n++;
            }
        }
        return n;
    }

    // Telegram-official account caps, mirroring the desktop client:
    //   kMaxAccounts = 3 (free), kPremiumMaxAccounts = 6 (with premium).
    private static final int TELEGRAM_FREE_LIMIT = 3;
    private static final int TELEGRAM_PREMIUM_LIMIT = 6;

    /**
     * Telegram-account cap (premium raises it from 3 to 6). Only Telegram accounts
     * count toward this; custom/self-hosted accounts are limited solely by the hard
     * total slot count (MAX_ACCOUNT_COUNT).
     */
    public static int telegramAccountLimit() {
        int limit = UserConfig.hasPremiumOnAccounts()
                ? TELEGRAM_PREMIUM_LIMIT
                : TELEGRAM_FREE_LIMIT;
        return Math.min(limit, UserConfig.MAX_ACCOUNT_COUNT);
    }

    /** True if another Telegram account can still be added under the premium cap. */
    public static boolean canAddTelegramAccount() {
        return countTelegramAccounts() < telegramAccountLimit();
    }
}
