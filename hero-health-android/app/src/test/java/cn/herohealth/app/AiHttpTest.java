package cn.herohealth.app;

import org.junit.Test;
import javax.net.ssl.HttpsURLConnection;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.cert.Certificate;
import static org.junit.Assert.*;

public class AiHttpTest {
    static class Fake extends HttpsURLConnection {
        final ByteArrayOutputStream sent=new ByteArrayOutputStream();int status=200;boolean closed,read,timeout;
        byte[] response="{\"choices\":[]}".getBytes(StandardCharsets.UTF_8);
        Fake()throws Exception{super(new URL("https://example.com/v1/chat/completions"));}
        @Override public void disconnect(){closed=true;}
        @Override public boolean usingProxy(){return false;}
        @Override public void connect(){}
        @Override public OutputStream getOutputStream(){return sent;}
        @Override public int getResponseCode()throws IOException{if(timeout)throw new SocketTimeoutException();return status;}
        @Override public InputStream getInputStream(){read=true;return new ByteArrayInputStream(response);}
        @Override public String getCipherSuite(){return "test";}
        @Override public Certificate[] getLocalCertificates(){return null;}
        @Override public Certificate[] getServerCertificates(){return null;}
    }
    @Test public void resolvesBaseAndFullEndpointsAndRejectsUnsafeAddresses()throws Exception{
        assertEquals("https://example.com/v1/chat/completions",AiHttp.completionUrl("https://example.com/v1/"));
        assertEquals("https://example.com/v1/chat/completions",AiHttp.completionUrl("https://example.com/v1/chat/completions"));
        for(String url:new String[]{"http://example.com","https://u:p@example.com/v1","https://example.com?key=test","https://example.com#test"})assertThrows(AiHttp.Failure.class,()->AiHttp.completionUrl(url));
    }
    @Test public void sendsUtf8JsonAndBearerOnlyToExplicitConnection()throws Exception{
        Fake connection=new Fake();String json="{\"model\":\"test\",\"content\":\"测试\"}";
        assertEquals("{\"choices\":[]}",AiHttp.exchange(connection,"test-value-not-live",json));
        assertEquals(json,connection.sent.toString("UTF-8"));assertEquals("POST",connection.getRequestMethod());
        assertEquals("Bearer test-value-not-live",connection.getRequestProperty("Authorization"));
        assertEquals("application/json; charset=utf-8",connection.getRequestProperty("Content-Type"));
        assertFalse(connection.getInstanceFollowRedirects());assertTrue(connection.closed);
    }
    @Test public void authenticationErrorsNeverReadOrExposeProviderBodies()throws Exception{
        Fake connection=new Fake();connection.status=401;connection.response="sensitive-provider-body".getBytes(StandardCharsets.UTF_8);
        AiHttp.Failure error=assertThrows(AiHttp.Failure.class,()->AiHttp.exchange(connection,"test-secret", "{}"));
        assertTrue(error.getMessage().contains("密钥"));assertFalse(error.getMessage().contains("test-secret"));assertFalse(error.getMessage().contains("sensitive"));assertFalse(connection.read);assertTrue(connection.closed);
    }
    @Test public void redirectsAreRejectedInsteadOfForwardingCredentials()throws Exception{
        Fake connection=new Fake();connection.status=302;
        assertTrue(assertThrows(AiHttp.Failure.class,()->AiHttp.exchange(connection,"test-only","{}")).getMessage().contains("跳转"));
        assertFalse(connection.getInstanceFollowRedirects());assertFalse(connection.read);assertTrue(connection.closed);
    }
    @Test public void boundedResponsesAndTimeoutsFailClearly()throws Exception{
        Fake large=new Fake();large.response=new byte[513*1024];
        assertTrue(assertThrows(AiHttp.Failure.class,()->AiHttp.exchange(large,"test-only","{}")).getMessage().contains("过大"));assertTrue(large.closed);
        Fake timeout=new Fake();timeout.timeout=true;
        assertTrue(assertThrows(AiHttp.Failure.class,()->AiHttp.exchange(timeout,"test-only","{}")).getMessage().contains("超时"));assertTrue(timeout.closed);
    }
}
