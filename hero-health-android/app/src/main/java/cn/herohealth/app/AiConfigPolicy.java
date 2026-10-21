package cn.herohealth.app;

import java.net.URI;

/** Pure configuration rules. This class never sends requests or logs credentials. */
final class AiConfigPolicy {
    static final class Invalid extends Exception {
        Invalid(String message) { super(message); }
    }
    static final class Config {
        final String endpoint, model, apiKey;
        Config(String endpoint, String model, String apiKey) {
            this.endpoint=endpoint; this.model=model; this.apiKey=apiKey;
        }
    }
    static Config update(String endpoint, String model, String enteredKey, boolean clearKey, Config previous) throws Invalid {
        String address=endpoint.trim(), name=model.trim(), secret=enteredKey.trim();
        if(address.isEmpty() || address.length()>2048) throw new Invalid("请填写有效的 HTTPS 服务地址");
        try {
            URI uri=new URI(address);
            if(!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost()==null || uri.getRawUserInfo()!=null || uri.getRawQuery()!=null || uri.getRawFragment()!=null || uri.getPort()==0 || uri.getPort()>65535)
                throw new Exception();
        } catch(Exception error) { throw new Invalid("服务地址须使用 HTTPS，且不能包含账号、查询参数或片段"); }
        address=address.replaceAll("/+$", "");
        if(name.isEmpty() || name.length()>200 || hasControl(name)) throw new Invalid("请填写模型名称，最多200个字符");
        if(secret.length()>8192 || hasControl(secret) || secret.chars().anyMatch(Character::isWhitespace)) throw new Invalid("密钥不能包含空格或换行，且不能超过8192个字符");
        if(clearKey && !secret.isEmpty()) throw new Invalid("清除密钥时请勿同时填写新密钥");
        // A retained credential belongs to its saved destination. Changing destinations cannot silently reuse it.
        String nextKey=clearKey?"":!secret.isEmpty()?secret:address.equals(previous.endpoint)?previous.apiKey:"";
        return new Config(address,name,nextKey);
    }
    private static boolean hasControl(String value) { return value.chars().anyMatch(c->Character.isISOControl(c)); }
}
