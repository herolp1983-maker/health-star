package cn.herohealth.app;
import org.junit.Test;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.util.Arrays;
import static org.junit.Assert.*;
public class VaultCodecTest {
    private SecretKey key() throws Exception {KeyGenerator g=KeyGenerator.getInstance("AES");g.init(256);return g.generateKey();}
    @Test public void encryptsAndAuthenticatesPrivateData() throws Exception {SecretKey key=key();byte[] plain="健康资料 test 178".getBytes(StandardCharsets.UTF_8),encrypted=VaultCodec.encrypt(key,plain,"state");assertFalse(new String(encrypted,StandardCharsets.UTF_8).contains("健康资料"));assertArrayEquals(plain,VaultCodec.decrypt(key,encrypted,"state"));assertFalse(Arrays.equals(encrypted,VaultCodec.encrypt(key,plain,"state")));}
    @Test public void corruptedCiphertextAndWrongKeysAreRejected() throws Exception {SecretKey key=key();byte[] encrypted=VaultCodec.encrypt(key,new byte[]{1,2,3},"state");assertThrows(GeneralSecurityException.class,()->VaultCodec.decrypt(key(),encrypted,"state"));encrypted[encrypted.length-1]^=1;assertThrows(GeneralSecurityException.class,()->VaultCodec.decrypt(key,encrypted,"state"));}
    @Test public void filesCannotBeSwappedBetweenIdentities() throws Exception {SecretKey key=key();byte[] encrypted=VaultCodec.encrypt(key,new byte[]{1,2,3},"report:one");assertThrows(GeneralSecurityException.class,()->VaultCodec.decrypt(key,encrypted,"report:two"));assertThrows(GeneralSecurityException.class,()->VaultCodec.decrypt(key,new byte[]{1,2},"report:one"));}
}
