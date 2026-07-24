# 架构

## 平台核心架构概览

pwn.hust.college 平台基于 pwn.college 的 DOJO 架构开发，定位为实践型网络安全教育平台。平台采用夺旗赛（CTF）竞赛模式，学习者通过解决挑战获取 flag 以证明技能掌握。与传统平台不同，平台提供预配置环境，支持浏览器或 SSH 访问，学习者可直接投入实战挑战，无需自行搭建环境。平台整体作为热门 CTFd 平台的"插件"实现，CTFd 提供用户、挑战及提交 flag 等基础功能，平台在此基础上扩展，允许教师创建挑战，学生在浏览器式工作区环境中解题。

## 基础设施容器化

平台组件由 **docker compose** 管理，管理员可在裸机上启动，实际部署时整个基础设施运行在一个 docker 容器（称为"外部 docker"或 `dojo` 容器）内。该容器通过 `Dockerfile` 构建，基于 Ubuntu 22.04，内部安装 Docker CE，形成 **Docker-in-Docker** 架构。

内部 compose 栈包含以下容器：

| 容器 | 职责 |
|------|------|
| `ctfd` | CTFd 主服务，含 dojo_plugin 和 dojo_theme |
| `db` | mariadb 10.4 数据库 |
| `cache` | redis 4 缓存 |
| `sshd` | SSH 访问入口，通过 `docker exec` 进入用户容器 |
| `nginx` | nginx-proxy 反向代理，处理 HTTP/HTTPS |
| `nginx-certs` | acme-companion，自动管理 HTTPS 证书 |
| `open-webui` | sensai AI 助教（基于 Open WebUI） |
| `prometheus` | Prometheus 监控采集 |
| `grafana` | Grafana 可视化仪表盘 |
| `node-exporter` | 系统级指标导出 |
| `mysql-exporter` | 数据库指标导出 |
| `redis-exporter` | 缓存指标导出 |
| `nginx-exporter` | Web 服务器指标导出 |

所有容器共享自定义 `user_network` 桥接网络（`10.114.0.0/16`）。用户挑战容器也启动在同一网络上，通过挂载进 `ctfd` 容器的宿主机 Docker socket（`/var/run/docker.sock`）进行管理。

## CTFd 与平台插件

平台前端界面是一个全转换式 CTFd 插件。插件 `dojo_plugin` 及其配套主题 `dojo_theme` 几乎取代所有前端功能，二者以只读方式绑定挂载进 ctfd 容器。

`dojo_plugin` 在 `__init__.py` 的 `load()` 函数中完成初始化：

- 注册 `DojoChallenge` 挑战类型和 `DojoFlag` 标志类型。Flag 使用 HMAC 按 `(account_id, challenge_id)` 签名——每个用户获得独立 flag，无静态 flag 表。
- 覆盖 CTFd 内置视图函数（`views.static_html`、`views.settings`、`challenges.listing`），删除内置排行榜/用户蓝图，由插件完全替换。
- 注册 14 个 Blueprint：`dojos`、`dojo`、`workspace`、`desktop`、`sso`（条件注册，由 `ENABLE_SSO` 控制）、`users`、`course`、`writeups`、`belts`、`kook`、`discord`、`sensai`、`api`（REST API，前缀 `/pwncollege_api/v1`）。
- 通过 `DispatcherMiddleware` 在 `/metrics` 暴露 Prometheus 指标端点。
- 加载时调用 `bootstrap()`：设置 `ctf_name`、`user_mode=users`、`ctf_theme=dojo_theme`，首次运行时创建 `admin/admin` 管理员账户。

插件代码分层：

- `pages/` — Flask Blueprint，HTML 视图（dojos、workspace、desktop、sso、kook、discord、sensai、course、writeups、belts、users、settings）
- `api/v1/` — REST API Blueprint（`docker.py` 启动挑战容器、`scoreboard.py` 排行榜、`belts.py` 绶带、`dojo.py` 道馆管理、`sso_login.py` SSO 认证后端等）
- `utils/` — 业务逻辑（flag 序列化、markdown 渲染、道馆加载、防火墙、seccomp、奖励追踪、IP 地址、请求日志）
- `models/` — SQLAlchemy 模型（Dojos、DojoChallenges、Belts、Emojis、DojoMembers、DojoAdmins 等）
- `config.py` — 启动引导 + 环境变量解析（从 docker-compose 环境读入）
- `prometheus_metrics.py` — 自定义 Prometheus 指标（请求计数、解题计数、登录计数等）

`dojo_theme` 位于 `dojo_theme/`，包含 `templates/`（Jinja2 模板）和 `static/`（CSS/JS/图片）。编辑插件或主题文件后，运行 `dojo sync` 并重启 ctfd 即可生效，无需重建镜像。

## 平台脚本

- `dojo-init`：初始化主机环境，为后续运行做准备。该脚本是**幂等**的——仅设置尚未定义的配置变量，避免覆盖已有配置。主要工作包括：创建 `data/config.env` 种子配置、创建 1 GB `homes/homefs` loopback ext4 镜像用于用户持久化 home 目录、设置 `iptables` 用户防火墙规则、生成 `/etc/docker/seccomp.json`。
- `dojo`：bash 命令分发器（`dojo/dojo`），提供与数据库、用户容器及平台容器的交互功能。支持 `start`、`sync`、`update`、`compose`、`flask`、`db`、`enter`、`backup`、`restore`、`logs`、`wait` 子命令。所有 `dojo` 命令在外部 dojo 容器内运行。

## 平台启动流程

外部 docker 通过 `Dockerfile` 构建，入口点为 `CMD ["dojo", "start"]`。启动流程为：

1. `dojo sync` — 复制 `ctfd/*` → `/opt/CTFd/`、`dojo_plugin` → `/opt/CTFd/CTFd/plugins/`、`dojo_theme` → `/opt/CTFd/CTFd/themes/`。
2. `dojo-init` — 初始化环境（幂等，见上节）。
3. `exec /usr/bin/systemd` — 启动 systemd，触发 `pwn.college.service`（即 `docker compose up`）。

同时存在多个 systemd 定时服务：每小时将平台主数据库备份到 `/data/backups`、每分钟刷新 redis 缓存以保证前端流畅、每分钟刷新挑战容器状态等。

## 平台配置

平台核心配置位于 `/data/config.env` 文件，若不存在，由 `dojo-init` 自动创建。该文件以环境变量键值对形式集中定义平台运行参数，被 `docker-compose.yml`、`dojo` 分发器和 `dojo-init` 共同读取。

关键变量包括：

- `DOJO_HOST`：服务域名（如 `pwn.cse.hust.edu.cn`）
- `DOJO_ENV`：运行环境（`development` 使用 Flask 开发服务器，其他使用 gunicorn）
- `DOJO_CHALLENGE`：挑战镜像尺寸（`challenge-nano`/`micro`/`mini`/`full`）
- `SECRET_KEY`：HMAC 密钥，用于 flag 签名（丢失会使所有用户 flag 失效）
- `INTERNET_FOR_ALL`：用户容器外网访问控制
- `ENABLE_SSO`：是否启用华科统一身份认证

详细配置说明见 `data_config_env.md`。

## 平台数据库

平台使用 **mariadb** 数据库，默认在 `db` 容器中运行。通过在 `config.env` 中设置 `DB_HOST` 可使用外部数据库，设置 `DB_EXTERNAL=yes` 可避免 `db` 容器启动。可通过 `dojo db` 启动数据库客户端会话。

CTFd 使用 **SQLAlchemy ORM** 访问数据库，可通过 `dojo flask` 进入 Python shell 进行数据库操作。插件定义的核心模型包括 `Dojos`（道馆）、`DojoModules`（模块）、`DojoChallenges`（挑战）、`DojoResources`（资源）、`Belts`（绶带，继承 CTFd Awards）、`Emojis`（徽章，继承 CTFd Awards）等。

## 用户挑战容器

当用户启动挑战时，CTFd 通过宿主机 Docker socket 启动一个与基础设施容器并行运行的 docker 容器，具体操作包括：

- 将挑战文件复制到容器中（`/challenge/` 目录）。
- 将工作区工具覆盖层挂载到容器。
- 将用户的 home 目录以 `nosuid` 方式挂载到容器。
- 应用自定义 seccomp 安全配置（见下节"网络安全"）。

容器初始化通过 `docker-initialize.sh` 完成，包括确保标准文件充分初始化（如 `hacker` 用户在 `/etc/passwd` 中存在、`/bin/sh` 有效等）、设置 `/flag` 以及运行 `/challenge/.init`（若存在）。挑战容器启动命令为 `sleep 6h`，因此 6 小时后自动超时停止。

容器的核心安全模型：
- 用户以 `hacker` 身份运行（UID 1000）。
- `/flag` 文件仅 `root`（UID 0）可读。
- 挑战程序作为 root 拥有的 **setuid 二进制文件**运行，因此能读取 flag。
- 学习者需满足挑战要求或利用挑战程序漏洞来获取 flag。

## 用户 home 目录

平台支持每个用户的持久化 home 目录，采用老版本 DOJO 的目录管理方式，通过常规的 docker 卷挂载实现数据持久化。所有用户的 home 目录存储在 `/data/homes/homefs` loopback ext4 镜像中（由 `dojo-init` 创建，默认 1 GB per user 总空间）。用户 home 目录在挑战容器间持久化，允许学生保存工作并跨挑战使用。

关键安全措施：home 目录以 `nosuid` 选项挂载，防止学生在不同环境之间传递 root-owned SUID 二进制文件。

## 工作区访问

- **HTTP 访问**：`nginx-proxy` 反向代理 → CTFd → 插件启动/接入用户容器。支持三种工作区：VSCode（浏览器内代码编辑器+终端）、桌面环境（基于 XFCE + noVNC）、帮助（AI 助教）。
- **SSH 访问**：端口 22 由 `sshd` 容器处理，该容器检查提供的公钥与数据库中的密钥表，检索对应的用户，并通过 `docker exec` 进入该用户正在运行的挑战容器。

## 网络安全

### Seccomp 配置

Docker seccomp 安全配置文件在 `dojo-init` 时由 `config.py::create_seccomp()` 生成，部署到 `/etc/docker/seccomp.json`。配置在 Docker 默认 seccomp 规则基础上：
- 扩展 `personality` 系统调用允许的 flag 组合（`READ_IMPLIES_EXEC` 和 `ADDR_NO_RANDOMIZE`），支持特定挑战类型。
- 其他危险系统调用（`clone`、`unshare`、`setns`、`sethostname`）遵循 Docker 默认 seccomp 策略，不再无条件允许。

### 用户防火墙

用户容器的出网流量受 `iptables` 规则限制（由 `dojo-init` 设置）。允许访问的地址定义在 `user_firewall.allowed` 文件中，由 `config.py` 解析为 `USER_FIREWALL_ALLOWED` 字典并注入容器的 `/etc/hosts`。此外，sensai 容器（`10.114.0.11`）显式允许访问。`INTERNET_FOR_ALL` 环境变量控制是否允许用户容器完全访问外网。

## 平台日志

管理或开发时可能需要查看的日志：

- **dojo-init**：`docker logs dojo`（外部 docker 的日志）
- **dojo**：`journalctl -b -u pwn.college.*`
- **ctfd**：`docker logs ctfd`
- **nginx**：`docker logs nginx-proxy`

除第一个外，其余需在外部 docker 内部运行。若在外部 docker 外（如宿主机），可使用 `docker exec dojo journalctl -b -u pwn.college` 等命令。
