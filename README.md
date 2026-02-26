# Sing-box 部署脚本

> Sing-box 内核独立部署脚本，支持 Hysteria2、Tuic、AnyTLS、Any-Reality、Shadowsocks-2022、Vmess-ws、Socks5 等协议。

## 目录说明

```
app/                    # 程序主目录
├── sing-box            # Sing-box 内核
├── sb.json             # 配置文件
├── private.key         # TLS 私钥
└── cert.pem            # TLS 证书

app-data/              # 数据目录
├── common/             # 公共数据
│   ├── uuid            # 用户UUID
│   ├── v4, v6         # 服务器IP
│   ├── warp_*          # WARP配置
│   └── ym_vl_re       # Reality域名
└── singbox/           # Sing-box 数据
    ├── keys/           # Reality密钥
    ├── port_hy2       # Hysteria2端口
    ├── port_tu         # Tuic端口
    ├── port_an         # AnyTLS端口
    ├── port_ar         # Any-Reality端口
    ├── port_ss        # Shadowsocks端口
    ├── port_vm_ws     # Vmess端口
    ├── port_so        # Socks5端口
    └── sskey          # Shadowsocks密钥
```

## 环境变量

| 变量 | 协议 | 推荐端口 | 说明 |
|------|------|----------|------|
| `hypt` | Hysteria2 | 5443, 8443, 10000-65535 | Hysteria2 协议端口 |
| `tupt` | Tuic | 5441, 8443, 10000-65535 | Tuic 协议端口 |
| `anpt` | AnyTLS | 5444, 8443, 10000-65535 | AnyTLS 协议端口 |
| `arpt` | Any-Reality | 5445, 8443, 10000-65535 | Any-Reality 协议端口 |
| `sspt` | Shadowsocks-2022 | 5446, 8443, 10000-65535 | Shadowsocks-2022 端口 |
| `vmpt` | Vmess-ws | 8081, 8080, 10000-65535 | Vmess-WebSocket 端口 |
| `sopt` | Socks5 | 7890, 1080, 10000-65535 | Socks5 端口 |
| `warp` | WARP 模式 | - | 出站模式 |

## 端口注意事项

### 被限制的端口

以下端口可能被云服务商封锁，**不建议使用**：

```
22, 23, 25, 53, 80, 110, 143, 443, 465, 587, 993, 995,
1433, 1434, 3306, 3389, 5432, 6379, 8080, 8443, 8888, 9000
```

### 推荐端口范围

- **10000-65535**：随机端口默认范围，自动避开被限制端口
- **5443, 5441, 8081**：已测试可用的端口

## WARP 模式说明

| 模式 | 说明 |
|------|------|
| `sx` | Sing-box 走 WARP，Xray 直连（默认） |
| `xs` | Sing-box 直连，Xray 走 WARP |
| `s` | Sing-box 走 WARP，Xray 直连 |
| `s4` | Sing-box 走 WARP IPv4，Xray 直连 |
| `s6` | Sing-box 走 WARP IPv6，Xray 直连 |
| `x` | Sing-box 直连，Xray 走 WARP |
| `x4` | Sing-box 直连，Xray 走 WARP IPv4 |
| `x6` | Sing-box 直连，Xray 走 WARP IPv6 |

## 使用方法

### 安装（指定端口）

```bash
# 安装 Hysteria2 协议
hypt=5443 python3 app.py install

# 安装 Tuic 协议
tupt=5441 python3 app.py install

# 安装 AnyTLS 协议
anpt=5444 python3 app.py install

# 安装 Any-Reality 协议
arpt=5445 python3 app.py install

# 安装 Shadowsocks-2022 协议
sspt=5446 python3 app.py install

# 安装 Vmess-ws 协议
vmpt=8081 python3 app.py install

# 安装 Socks5 协议
sopt=7890 python3 app.py install
```

### 安装（随机端口）

```bash
# 不指定端口时，默认安装所有协议（随机端口）
python3 app.py install

# 指定 "auto" 使用随机端口
hypt=auto python3 app.py install

# 部分协议使用随机端口
hypt=auto tupt=auto sspt=auto python3 app.py install
```

### 安装（多个协议组合）

```bash
# Hysteria2 + Tuic + Shadowsocks-2022
hypt=5443 tupt=5441 sspt=5446 python3 app.py install

# Hysteria2 + WARP
hypt=5443 warp=sx python3 app.py install

# 所有协议
hypt=5443 tupt=5441 anpt=5444 arpt=5445 sspt=5446 vmpt=8081 sopt=7890 python3 app.py install
```

### 查看节点配置

```bash
python3 app.py list
```

### 查看运行状态

```bash
python3 app.py status
```

### 重启服务

```bash
python3 app.py restart
```

### 停止服务

```bash
python3 app.py stop
```

### 更新内核

```bash
python3 app.py upsingbox
```

### 卸载

```bash
python3 app.py del
```

## Docker 部署

### 构建镜像

```bash
docker build -t singbox-deploy .
```

### 运行容器

```bash
# 查看帮助
docker run --rm singbox-deploy

# 安装 Hysteria2
docker run --rm -e hypt=5443 singbox-deploy python3 /root/app.py install

# 查看节点
docker run --rm singbox-deploy python3 /root/app.py list
```

## 推荐配置

### 常用端口分配

| 端口 | 协议 | 备注 |
|------|------|------|
| 5443 | Hysteria2 | 推荐 |
| 5441 | Tuic | 推荐 |
| 8081 | Vmess-ws | 推荐 |
| 7890 | Socks5 | 本地代理 |

### 简单配置示例

```bash
# 最简配置：仅 Hysteria2
hypt=5443 python3 app.py install
```

```bash
# 多协议配置
hypt=5443 tupt=5441 sspt=5446 python3 app.py install
```

```bash
# 完整配置 + WARP
hypt=5443 tupt=5441 anpt=5444 arpt=5445 sspt=5446 vmpt=8081 sopt=7890 warp=sx python3 app.py install
```

## 注意事项

1. **端口限制**：云服务商可能封锁常用端口（443, 80, 8080 等），建议使用 10000-65535 范围
2. **防火墙**：请在防火墙开放相应端口
3. **WARP**：首次安装会配置 WARP，可能需要等待
4. **数据持久化**：配置和密钥保存在 `app-data/` 目录，升级/重装不会丢失
5. **IPv6**：脚本会自动检测服务器 IPv6 支持情况

## License

MIT
