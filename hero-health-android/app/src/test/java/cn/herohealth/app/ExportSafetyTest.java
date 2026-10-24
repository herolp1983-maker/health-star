package cn.herohealth.app;

import org.junit.Test;
import java.io.ByteArrayOutputStream;
import java.io.IOException;

import static org.junit.Assert.*;

public class ExportSafetyTest {
    @Test public void closeFailureIsNotReportedAsSuccessfulExport() {
        ByteArrayOutputStream out = new ByteArrayOutputStream() {
            @Override public void close() throws IOException { throw new IOException("provider close failed"); }
        };
        assertThrows(IOException.class, () -> ExportSafety.writeAndClose(out, "encrypted backup"));
    }

    @Test public void successfulExportIsFullyClosed() throws Exception {
        final boolean[] closed = {false};
        ByteArrayOutputStream out = new ByteArrayOutputStream() {
            @Override public void close() throws IOException { closed[0] = true; super.close(); }
        };
        ExportSafety.writeAndClose(out, "encrypted backup");
        assertTrue(closed[0]);
        assertEquals("encrypted backup", out.toString("UTF-8"));
    }
}
