# 本地资产 API

主 WebUI 提供只读资产接口，用于按顺序或指定下标读取邮箱与已注册平台凭据。默认地址为 `http://127.0.0.1:8799`。

## 鉴权

未配置 `REG_FACTORY_ASSET_API_KEY` 时，接口只接受本机请求。配置后，请求必须携带其中一种请求头：

```text
X-API-Key: your-key
Authorization: Bearer your-key
```

不要把 WebUI 监听到公网；这些接口返回邮箱密码、refresh token、Cookie 或平台 token。

## 邮箱

```bash
# 按 emails.txt 顺序取下一个，并推进邮箱游标
curl http://127.0.0.1:8799/api/assets/emails

# 精确读取第 3 条，不推进游标
curl "http://127.0.0.1:8799/api/assets/emails?index=2"

# 返回原始四段文本
curl "http://127.0.0.1:8799/api/assets/emails?format=line"
```

`format=json` 返回 `email`、`password`、`refresh_token`、`client_id`；`format=line` 返回原始 `----` 分隔文本。

## 平台 Cookie 与下游格式

```bash
# Claude 有效 Cookie 数组
curl "http://127.0.0.1:8799/api/assets/cookies/claude?format=raw"

# 浏览器 Cookie 请求头
curl "http://127.0.0.1:8799/api/assets/cookies/chatgpt?format=header&index=0"

# ChatGPT -> SUB2API 导入内容
curl "http://127.0.0.1:8799/api/assets/cookies/chatgpt?format=sub2api"

# ChatGPT -> CPA codex 授权 JSON
curl "http://127.0.0.1:8799/api/assets/cookies/chatgpt?format=cpa"

# ChatGPT -> chatgpt2api account
curl "http://127.0.0.1:8799/api/assets/cookies/chatgpt?format=chatgpt2api"

# Grok -> SUB2API SSO 请求体
curl "http://127.0.0.1:8799/api/assets/cookies/grok?format=sub2api"
```

支持的平台与格式：

| 平台 | 格式 |
|---|---|
| Claude | `raw`、`header` |
| ChatGPT | `raw`、`header`、`session`、`sub2api`、`cpa`、`chatgpt2api` |
| Grok | `raw`、`header`、`session`、`sub2api` |

响应中的 `index` 是本次下标，`total` 是当前总数，`next_index` 是下一下标。省略 `index` 会推进对应的独立游标；指定 `index` 只读取该条，不改变游标。

## 状态与重置

```bash
curl http://127.0.0.1:8799/api/assets/summary

# 重置全部顺序游标
curl -X POST http://127.0.0.1:8799/api/assets/cursors/reset \
  -H "Content-Type: application/json" -d '{"scope":"all"}'

# 只重置 ChatGPT CPA 游标
curl -X POST http://127.0.0.1:8799/api/assets/cursors/reset \
  -H "Content-Type: application/json" -d '{"scope":"cookie:chatgpt:cpa"}'
```

游标保存在 `runtime/state/asset_api_cursors.json`；它不会修改 `emails.txt`、Cookie 或 Token 文件。
