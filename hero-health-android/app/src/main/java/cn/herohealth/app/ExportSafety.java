package cn.herohealth.app;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

final class ExportSafety {
    private ExportSafety() {}

    static void writeAndClose(OutputStream stream, String text) throws IOException {
        try (OutputStream out = stream) {
            out.write(text.getBytes(StandardCharsets.UTF_8));
            out.flush();
        }
    }
}
