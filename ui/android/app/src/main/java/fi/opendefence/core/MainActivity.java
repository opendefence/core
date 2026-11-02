package fi.opendefence.core;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        registerPlugin(ClientCertificatePlugin.class);
        super.onCreate(savedInstanceState);
        bridge.setWebViewClient(new MtlsWebViewClient(bridge));
    }
}
