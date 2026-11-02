package fi.opendefence.core;

import android.os.Build;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.security.keystore.KeyInfo;
import android.util.Base64;
import android.webkit.WebView;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.security.PrivateKey;
import java.security.ProviderException;
import java.security.Signature;
import java.security.cert.Certificate;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.security.spec.ECGenParameterSpec;
import java.util.Arrays;

/** Keeps the client key in the Android Keystore. */
@CapacitorPlugin(name = "ClientCertificate")
public class ClientCertificatePlugin extends Plugin {

    private static final String CURVE = "secp256r1";
    private static final String SIGNATURE = "SHA256withECDSA";

    @PluginMethod
    public void generateKey(PluginCall call) {
        try {
            KeyStore store = ClientIdentity.keyStore();
            if (store.containsAlias(ClientIdentity.ALIAS)) store.deleteEntry(ClientIdentity.ALIAS);

            byte[] spki;
            try {
                spki = generate(true);
            } catch (ProviderException e) {
                // No StrongBox, fall back to the TEE
                spki = generate(false);
            }
            JSObject result = new JSObject();
            result.put("spki", Base64.encodeToString(spki, Base64.NO_WRAP));
            result.put("hardware", isHardwareBacked());
            call.resolve(result);
        } catch (Exception e) {
            call.reject("Key generation failed", e);
        }
    }

    @PluginMethod
    public void sign(PluginCall call) {
        String data = call.getString("data");
        if (data == null) {
            call.reject("data is required");
            return;
        }
        try {
            Signature signature = Signature.getInstance(SIGNATURE);
            signature.initSign(ClientIdentity.privateKey());
            signature.update(Base64.decode(data, Base64.DEFAULT));
            JSObject result = new JSObject();
            result.put("signature", Base64.encodeToString(signature.sign(), Base64.NO_WRAP));
            call.resolve(result);
        } catch (Exception e) {
            call.reject("Signing failed", e);
        }
    }

    @PluginMethod
    public void storeChain(PluginCall call) {
        String pem = call.getString("chainPem");
        if (pem == null) {
            call.reject("chainPem is required");
            return;
        }
        try {
            CertificateFactory factory = CertificateFactory.getInstance("X.509");
            Certificate[] chain = factory
                .generateCertificates(new ByteArrayInputStream(pem.getBytes(StandardCharsets.US_ASCII)))
                .toArray(new Certificate[0]);
            KeyStore store = ClientIdentity.keyStore();
            Certificate current = store.getCertificate(ClientIdentity.ALIAS);
            if (chain.length == 0 || current == null) {
                call.reject("No key or no certificate");
                return;
            }
            byte[] ours = current.getPublicKey().getEncoded();
            if (!Arrays.equals(ours, chain[0].getPublicKey().getEncoded())) {
                call.reject("Certificate is for another key");
                return;
            }
            PrivateKey key = ClientIdentity.privateKey();
            store.setKeyEntry(ClientIdentity.ALIAS, key, null, chain);
            // The WebView caches its answer per host
            getActivity().runOnUiThread(() -> WebView.clearClientCertPreferences(null));
            call.resolve(status());
        } catch (Exception e) {
            call.reject("Storing the chain failed", e);
        }
    }

    @PluginMethod
    public void status(PluginCall call) {
        try {
            call.resolve(status());
        } catch (Exception e) {
            call.reject("Status failed", e);
        }
    }

    @PluginMethod
    public void remove(PluginCall call) {
        try {
            KeyStore store = ClientIdentity.keyStore();
            if (store.containsAlias(ClientIdentity.ALIAS)) store.deleteEntry(ClientIdentity.ALIAS);
            getActivity().runOnUiThread(() -> WebView.clearClientCertPreferences(null));
            call.resolve();
        } catch (Exception e) {
            call.reject("Removing the key failed", e);
        }
    }

    @PluginMethod
    public void setDomain(PluginCall call) {
        String domain = call.getString("domain");
        if (domain == null || domain.isEmpty()) {
            call.reject("domain is required");
            return;
        }
        ClientIdentity.setDomain(getContext(), domain);
        call.resolve();
    }

    private byte[] generate(boolean strongBox) throws Exception {
        KeyGenParameterSpec.Builder spec = new KeyGenParameterSpec.Builder(
            ClientIdentity.ALIAS,
            KeyProperties.PURPOSE_SIGN
        )
            .setAlgorithmParameterSpec(new ECGenParameterSpec(CURVE))
            .setDigests(KeyProperties.DIGEST_SHA256);
        if (strongBox && Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) spec.setIsStrongBoxBacked(true);

        KeyPairGenerator generator = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, ClientIdentity.KEYSTORE);
        generator.initialize(spec.build());
        return generator.generateKeyPair().getPublic().getEncoded();
    }

    private boolean isHardwareBacked() throws Exception {
        PrivateKey key = ClientIdentity.privateKey();
        KeyFactory factory = KeyFactory.getInstance(key.getAlgorithm(), ClientIdentity.KEYSTORE);
        KeyInfo info = factory.getKeySpec(key, KeyInfo.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            return info.getSecurityLevel() != KeyProperties.SECURITY_LEVEL_SOFTWARE;
        }
        return info.isInsideSecureHardware();
    }

    private JSObject status() throws Exception {
        KeyStore store = ClientIdentity.keyStore();
        X509Certificate[] chain = ClientIdentity.chain();
        JSObject result = new JSObject();
        result.put("hasKey", store.containsAlias(ClientIdentity.ALIAS));
        result.put("hasChain", chain != null);
        if (chain != null) {
            result.put("notAfter", chain[0].getNotAfter().getTime());
            result.put("subject", chain[0].getSubjectX500Principal().getName());
        }
        return result;
    }
}
