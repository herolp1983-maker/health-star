package cn.herohealth.app;
import org.junit.Test;
import static org.junit.Assert.*;

public class AiConfigPolicyTest {
    private final AiConfigPolicy.Config saved=new AiConfigPolicy.Config("https://example.com/v1","old-model","test-credential-never-live");
    @Test public void maintainsAndReplacesCredentials() throws Exception {
        AiConfigPolicy.Config retained=AiConfigPolicy.update(" https://example.com/v1/ ","new-model","",false,saved);
        assertEquals(saved.apiKey,retained.apiKey);
        assertEquals("new-model",retained.model);
        assertEquals("https://example.com/v1",retained.endpoint);
        assertEquals("replacement-test-value",AiConfigPolicy.update(saved.endpoint,saved.model,"replacement-test-value",false,saved).apiKey);
        assertEquals("",AiConfigPolicy.update(saved.endpoint,saved.model,"",true,saved).apiKey);
    }
    @Test public void differentDestinationCannotReuseExistingCredential() throws Exception {
        assertEquals("",AiConfigPolicy.update("https://other.example/v1",saved.model,"",false,saved).apiKey);
        assertEquals("new-test-value",AiConfigPolicy.update("https://other.example/v1",saved.model,"new-test-value",false,saved).apiKey);
        assertEquals("",AiConfigPolicy.update("https://example.com/other",saved.model,"",false,saved).apiKey);
    }
    @Test public void rejectsInsecureOrCredentialBearingAddresses() {
        for(String address:new String[]{"", "http://example.com/v1","https://user:pass@example.com/v1","https://example.com/v1?key=test","https://example.com/v1#fragment","https://","https://example.com:0/v1","https://example.com:70000/v1"}) {
            assertThrows(AiConfigPolicy.Invalid.class,()->AiConfigPolicy.update(address,saved.model,"",false,saved));
        }
    }
    @Test public void rejectsInvalidInputsWithoutChangingExistingConfigOrEchoingSecrets() {
        for(String secret:new String[]{"test with space","test\r\nheader","x".repeat(8193)}) {
            AiConfigPolicy.Invalid error=assertThrows(AiConfigPolicy.Invalid.class,()->AiConfigPolicy.update(saved.endpoint,saved.model,secret,false,saved));
            assertFalse(error.getMessage().contains(secret));
        }
        assertThrows(AiConfigPolicy.Invalid.class,()->AiConfigPolicy.update(saved.endpoint,"","",false,saved));
        assertThrows(AiConfigPolicy.Invalid.class,()->AiConfigPolicy.update(saved.endpoint,saved.model,"new-value",true,saved));
        assertEquals("test-credential-never-live",saved.apiKey);
    }
}
