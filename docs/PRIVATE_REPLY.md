# 私聊自动回复与新版微信

本分支增加了指定私聊的文本自动回复：私聊必须用微信账号 ID 加入 `reply_sender.allowed_chats`；空白名单不会启用私聊。发送者通过消息库 `Name2Id` 校验，自己的消息和无法确认来源的消息不会触发。接收者须通过联系人去重与窗口标题 OCR 校验，任一环节失败即拒绝发送。当前 OCR 仅支持 1760×1280 的微信窗口；窗口大小或布局改变时会拒绝发送。

控制台现有的「允许群聊」组件只显示群聊，保存该表单会覆盖私聊白名单；不要用该表单修改私聊配置。群聊 @ 仍沿用上游的文本判断，不属于本次私聊改造。

可选的 GUI 镜像包含腾讯官方 Linux 微信、中文 OCR 和 Frida：

```sh
docker compose -f docker-compose.yml -f docker-compose.selkies.yml build wechat-selkies
docker compose -f docker-compose.yml -f docker-compose.selkies.yml up -d wechat-selkies
```

构建时下载的是腾讯当前提供的版本，并非锁定版本；微信升级后，界面、密钥提取或 OCR 可能失效。保持控制台只绑定本机，远程访问请使用安全隧道。

如果原有的 Linux 密钥扫描无法处理新版微信，可在已有一个账号目录时使用实验性的 KDF 捕获脚本。它会附加到微信进程；`--spawn` 会启动一个新的微信进程，使用前需先正常退出现有微信，并可能需要重新扫码。捕获程序会验证密钥，不会把密钥打印到终端。密钥文件和解密库均属于敏感数据。

```sh
# 在微信容器内，以微信运行用户执行；必要时登录并打开会话。
docker compose exec -u abc -e PYTHONPATH=/opt/wechat-frida wechat-selkies \
  python3 /opt/wechat-controller/capture_linux_kdf.py --spawn
# 仅在捕获验证成功后，将密钥安装到同步服务使用的位置。
docker compose exec -u root wechat-selkies sh -c \
  'install -m 600 /config/.wechat-agent-keys.json /runtime/wechat-decrypt/keys/all_keys.json'
```

图片的 V2 密钥需要单独配置。WXGF 原图有 JPEG 缩略图时，预览优先使用缩略图。

`linux_wechat_capture.py` 的定位逻辑来自 [chatlog-keeper](https://github.com/labazhou2024/chatlog-keeper)，其 MIT 许可见 `agent_console/LINUX_WECHAT_CAPTURE_LICENSE`。
