package fi.opendefence.core;

import android.util.Log;
import android.webkit.ClientCertRequest;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import com.getcapacitor.Bridge;
import com.getcapacitor.BridgeWebViewClient;
import java.security.PrivateKey;
import java.security.cert.X509Certificate;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Answers app.<domain>'s client certificate request from the Keystore. */
class MtlsWebViewClient extends BridgeWebViewClient {

    private static final String TAG = "MtlsWebViewClient";

    // Keystore access would block the UI thread
    private final ExecutorService keystore = Executors.newSingleThreadExecutor();

    MtlsWebViewClient(Bridge bridge) {
        super(bridge);
    }

    @Override
    public void onReceivedClientCertRequest(WebView view, ClientCertRequest request) {
        if (!ClientIdentity.isAppHost(view.getContext(), request.getHost())) {
            request.cancel();
            return;
        }
        keystore.execute(() -> {
            try {
                PrivateKey key = ClientIdentity.privateKey();
                X509Certificate[] chain = ClientIdentity.chain();
                if (key == null || chain == null) {
                    request.cancel();
                    return;
                }
                request.proceed(key, chain);
            } catch (Exception e) {
                Log.w(TAG, "No client certificate for " + request.getHost(), e);
                request.cancel();
            }
        });
    }

    @Override
    public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
        // Other hosts open in the browser
        if (ClientIdentity.isDeploymentHost(view.getContext(), request.getUrl().getHost())) return false;
        return super.shouldOverrideUrlLoading(view, request);
    }
}
