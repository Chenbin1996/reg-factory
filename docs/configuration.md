# 配置说明

## 前置条件

### 指纹浏览器

三选一；外部客户端模式需要保持客户端运行：

- 内置 Chromium：`FINGERPRINT_BROWSER=bundled`，安装程序会配置浏览器路径。
- [BitBrowser 官方下载页](https://www.bitbrowser.cn/download)：默认 API 为 `http://127.0.0.1:54345`。
- AdsPower：默认 API 为 `http://127.0.0.1:50325`，启用鉴权时还需 API Key。

在 `.env` 中用 `FINGERPRINT_BROWSER=bundled|bitbrowser|adspower` 切换。

### 网络出口

WebUI 左侧“网络出口”页提供三种互斥模式：

| 模式 | `PROXY_MODE` | 行为 |
|---|---|---|
| 自动轮换 | `clash_auto` | 从 Clash 代理组选择可响应节点，注册流程可按失败或批次继续换节点 |
| 固定节点 | `clash_fixed` | 始终强制使用 `CLASH_FIXED_NODE`，脚本传入其他节点也不会覆盖 |
| 动态住宅 IP | `residential` | 使用单个住宅代理或持久轮换代理池，可调用供应商换 IP 接口 |

Clash 模式先安装 [Clash Verge 2.5.2 Windows x64](https://github.com/clash-verge-rev/clash-verge-rev/releases/download/v2.5.2/Clash.Verge_2.5.2_x64-setup.exe)，再开启 External Controller，记录控制器地址、secret 和 mixed port：

开启 External Controller，记录控制器地址、secret 和 mixed port。默认值：

```env
CLASH_API=http://127.0.0.1:9097
CLASH_PROXY=http://127.0.0.1:7897
CLASH_GROUP=GLOBAL
CLASH_SECRET=
```

固定节点模式额外配置：

```env
PROXY_MODE=clash_fixed
CLASH_FIXED_NODE=美国 01
```

住宅代理支持 `http`、`https`、`socks4` 和 `socks5`；BitBrowser 窗口支持 `http`、`https` 和 `socks5`。代理池优先于单个代理；`.env` 中用逗号分隔，WebUI 中可每行填写一个：

```env
PROXY_MODE=residential
REG_FACTORY_PROXY=http://user:pass@host:port
REG_FACTORY_PROXY_POOL=http://user:pass@host-a:8000,http://user:pass@host-b:8000
REG_FACTORY_PROXY_ROTATE_URL=https://provider.example/rotate
REG_FACTORY_PROXY_ROTATE_METHOD=GET
```

`REG_FACTORY_PROXY_ROTATE_URL` 可留空。点击“立即轮换”时，程序会推进代理池索引，并在配置后调用供应商接口。当前池索引保存在 `runtime/state/residential_proxy_index.txt`。

BitBrowser 创建新窗口时会写入当前住宅代理的地址、端口、用户名和密码。代理池轮换后，下一个新建窗口使用新的代理；已经打开的注册窗口不会被强制改 IP，以免破坏当前登录会话。

旧变量 `RESIDENTIAL_PROXY`、`DIRECT_PROXY` 和 `RESIDENTIAL_PROXY_POOL` 仍兼容；新配置应使用 `REG_FACTORY_*`。

### Python 与 Node.js

- Python 3.10+ 是主流程必需依赖。
- Node.js 20+ 只在构建或运行 Codex K12 时需要。
- Gmail Android 流程还需要 BlueStacks、ADB、Appium 2.x 和 UiAutomator2 driver。

## 创建配置

Windows：

```powershell
Copy-Item .env.example .env
```

macOS / Linux：

```bash
cp .env.example .env
```

真实进程环境变量优先于 `.env`。WebUI 保存配置后，新任务立即使用新值，不需要重启主服务。

本地邮箱/Cookie 读取接口默认只允许回环地址调用。需要由其他本机服务统一携带密钥时，设置 `REG_FACTORY_ASSET_API_KEY`，并使用 `X-API-Key` 或 Bearer Token；完整接口见 [本地资产 API](api.md)。

## 配置分组

`.env.example` 是全部配置项和默认值的唯一完整清单。通常只需要填写当前流程涉及的分组。

| 分组 | 常用变量 | 使用场景 |
|---|---|---|
| 指纹浏览器 | `FINGERPRINT_BROWSER`、`BITBROWSER_API`、`ADSPOWER_*` | 浏览器注册流程 |
| 网络出口 | `PROXY_MODE`、`CLASH_*`、`REG_FACTORY_PROXY*` | Clash 节点或住宅代理 |
| Claude 验证 | `CLAUDE_VISION_*`、`CLAUDE_HCAPTCHA_*` | Claude 图形验证 |
| 通用视觉 | `VISION_*`、`VOTE_*`、`IMAGE_EDIT_*` | 多模型视觉投票 |
| 临时邮箱 | `YYDS_API_KEY` 等 provider 配置 | 不使用 Outlook 池时 |
| 接码 | `SMSMAN_*`、`SMS_TOKEN`、`HERO_SMS_*` | 手机验证 |
| SUB2API | `SUB2API_*` | Codex / Grok 下游导入 |
| CPA | `CPA_URL`、`CPA_MGMT_KEY` | Codex 凭据导入 |
| chatgpt2api | `CHATGPT2API_URL`、`CHATGPT2API_KEY` | 普通 ChatGPT 网页号导入 |

密钥必须留在 `.env` 或进程环境变量中。不要把真实值写进 `.env.example`、README、测试和截图。

## 连通性检查

推荐从 WebUI 的“环境配置”页面执行测试。命令行也可检查 Clash：

```bash
python -m common.proxy_switch list
python -m common.proxy_switch current
python -m common.proxy_switch rotate
python _clash_verge.py ping
```

配置问题的常见表现和处理方式见 [常见问题](troubleshooting.md)。
