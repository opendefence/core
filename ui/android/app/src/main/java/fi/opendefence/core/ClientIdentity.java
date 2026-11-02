package fi.opendefence.core;

import android.content.Context;
import android.content.SharedPreferences;
import java.security.KeyStore;
import java.security.PrivateKey;
import java.security.cert.Certificate;
import java.security.cert.X509Certificate;
import java.util.Arrays;

/** The Keystore key, its chain, and the joined domain. */
final class ClientIdentity {

    static final String KEYSTORE = "AndroidKeyStore";
    static final String ALIAS = "opendefence-client";

    private static final String PREFS = "client_identity";
    private static final String DOMAIN = "domain";
    private static final String APP_LABEL = "app.";

    private ClientIdentity() {}

    static KeyStore keyStore() throws Exception {
        KeyStore store = KeyStore.getInstance(KEYSTORE);
        store.load(null);
        return store;
    }

    static PrivateKey privateKey() throws Exception {
        return (PrivateKey) keyStore().getKey(ALIAS, null);
    }

    /** Null until the deployment has signed the key. */
    static X509Certificate[] chain() throws Exception {
        Certificate[] chain = keyStore().getCertificateChain(ALIAS);
        if (chain == null) return null;
        X509Certificate[] x509 = Arrays.copyOf(chain, chain.length, X509Certificate[].class);
        // generateKey leaves a self-signed placeholder
        X509Certificate leaf = x509[0];
        if (leaf.getSubjectX500Principal().equals(leaf.getIssuerX500Principal())) return null;
        return x509;
    }

    static void setDomain(Context context, String domain) {
        prefs(context).edit().putString(DOMAIN, domain).apply();
    }

    static boolean isAppHost(Context context, String host) {
        String domain = prefs(context).getString(DOMAIN, null);
        return domain != null && host != null && host.equalsIgnoreCase(APP_LABEL + domain);
    }

    static boolean isDeploymentHost(Context context, String host) {
        String domain = prefs(context).getString(DOMAIN, null);
        return domain != null && host != null && (host.equalsIgnoreCase(domain) || isAppHost(context, host));
    }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }
}
