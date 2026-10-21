# 健康星 Android 0.5.1

用户已将应用从Hero健康更名为健康星。包名cn.herohealth.app、设备密钥别名hero-health-local-v1、私有档案路径、备份标识hero-health-backup及发布证书保持原样，以支持覆盖升级。

## 本次修复与流程

- MiniMax适配与临床数据校验分开：AiProtocol检测HTTP200中的base_resp业务错误，解析最终回答字符串/文字块，剥离前置think标签，识别唯一完整JSON对象，拒绝截断、多对象和仅思考内容。不会从reasoning_content猜取指标，也不回显服务商原始正文。测试连接只检查可用的最终回答，不依赖JSON输出。
- MiniMax官方api.minimax.cn/.io请求启用reasoning_split；不发送其文档未列出的response_format，改由提示词请求并严格验证JSON。MiniMax-M3连接测试可关闭thinking；M3.1-Flash不强行关闭，测试使用low、分析使用medium思考档位。根地址自动补/v1，仅更改请求解析，不改手机配置或密钥。其他OpenAI兼容接口的分析继续使用JSON模式。
- 报告默认一键处理全部资料。先本地检查原件页数，再按每张关联卡片分组，每批最多8页/3份文件，长PDF分页。请求包含该卡片说明、定义、最近指标、已核对报告摘要，以及同次任务较早批次的“未核对”提取，避免冒充已确认历史。
- 按文件ID、卡片ID与原始页码验证模型输出，防止串卡片/错归文件。共享报告多卡片输出合并为同一批量分析版本；保留分批摘要、原始提取、核对值和来源。已有指标不被抹除，同来源/日期/数值去重。
- 每批结果立即加密保存；中断时保留部分结果并允许继续。报告全部相关批次完成后才可确认，未完成部分不能写入趋势。集中确认全部结果是一次档案提交，任何一份校验失败均不写入。
- 图标使用mipmap-anydpi-v26自适应图标，紫色背景完全不透明，前景占108dp图层中的78dp，视觉标记处于中心区域。兼容位图也铺不透明紫色。应用内部继续使用用户提供的原始Logo。

## 数据与运行边界

Java宿主+捆绑React/TypeScript，受限WebView只加载本地资源；原生HTTPS处理AI调用，无自建服务器。密钥不返回WebView、不进入健康备份；无广告统计SDK。拒绝HTTP、URL账号/查询参数/片段与重定向，不输出原始服务错误、不自动重试。

本地档案、报告及配置使用Android Keystore AES-256-GCM和AtomicFile。备份PBKDF2-SHA256 210000次+AES-256-GCM，恢复前校验并导出安全备份。整体恢复不改变本机AI配置。

报告单文件15 MiB、批量PDF1至500页，分析请求18 MiB，响应512 KiB；备份JSON90 MiB、导入包128 MiB。PDF私有临时明文在结束后删除，异常残留在下次启动清理。

## 构建

运行npm test，然后pwsh -NoProfile -File scripts/build-android.ps1。JDK17/SDK35/Build Tools35.0.0/Gradle8.11.1/AGP8.9.2。Windows中文路径通过带所有权标记的英文临时目录构建；签名文件本地保存且Git忽略，不能重建。

产物delivery/健康星-0.5.1.apk，versionCode=8。发布构建必须使用原有签名配置和密钥，缺失时立即停止；不会自动生成替代密钥。日常 PR 使用仓库根目录的 engineering/check-local.ps1 验证 Debug 构建。依赖org.json:json:20240303只用于JVM协议测试，不打包到Android运行时。验证记录见verification/BUILD-REPORT.md。

未获取手机真实API Key或发送真实健康资料。接口回归依据官方文档和受控响应，不能等同于真实MiniMax账户联调或Vivo桌面效果已经通过。

## 官方参考

- [MiniMax OpenAI兼容接口与thinking/reasoning_split](https://platform.minimax.cn/docs/api-reference/text-openai-api)
- [MiniMax错误码](https://platform.minimax.cn/docs/api-reference/errorcode)
- [Android自适应图标](https://developer.android.com/develop/ui/compose/system/icon_design_adaptive)
