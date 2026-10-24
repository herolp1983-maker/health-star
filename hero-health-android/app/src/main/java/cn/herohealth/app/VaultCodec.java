package cn.herohealth.app;

import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.util.Arrays;
import javax.crypto.Cipher;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Authenticated envelope, bound to the file identity. Never logs plaintext or keys. */
public final class VaultCodec {
    private static final byte[] MAGIC = new byte[]{'H','H','V',1};
    private VaultCodec() {}
    public static byte[] encrypt(SecretKey key, byte[] plain, String context) throws GeneralSecurityException {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE,key);
        byte[] iv=cipher.getIV();
        if(iv.length!=12)throw new GeneralSecurityException("Unsupported IV length");
        cipher.updateAAD(context.getBytes(StandardCharsets.UTF_8));
        byte[] body=cipher.doFinal(plain),out=new byte[16+body.length];
        System.arraycopy(MAGIC,0,out,0,4); System.arraycopy(iv,0,out,4,12); System.arraycopy(body,0,out,16,body.length);
        return out;
    }
    public static byte[] decrypt(SecretKey key, byte[] envelope, String context) throws GeneralSecurityException {
        if(envelope.length<32 || !Arrays.equals(MAGIC,Arrays.copyOf(envelope,4))) throw new GeneralSecurityException("Invalid encrypted file");
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE,key,new GCMParameterSpec(128,Arrays.copyOfRange(envelope,4,16)));
        cipher.updateAAD(context.getBytes(StandardCharsets.UTF_8));
        return cipher.doFinal(Arrays.copyOfRange(envelope,16,envelope.length));
    }
}
