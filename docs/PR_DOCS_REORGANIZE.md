## 文档信息整理：重新组织 architecture.md, development.md 等文档

### Summary

对 `docs/` 目录进行系统性整理，填充空文件、重写过时内容、消除重复、精简冗余。

**7 files changed, 2 commits.**

### Problem

`docs/` 目录存在以下问题：

1. `development.md`、`challenge.md`、`pwnhustcollege_deployment.md` 三个文件为空，但 README.md 引用了它们
2. `architecture.md` 内容过时，未覆盖 SSO、sensai AI 助教、Prometheus/Grafana 监控栈、KOOK/Discord 集成、请求日志追踪等 HUST 特有功能
3. `data_config_env.md` 结构松散，缺乏 SSO 和 AI 助教配置说明
4. `User_Manual_For_Teachers.md` 第三节学生手册与 `User_Manual_For_Students.md` 完全重复

### Changes

#### 1. 重写 `architecture.md`

在保留原有基础设施描述的基础上，新增 `## HUST 特有功能` 大节，涵盖：
- SSO 统一身份认证（CAS 协议、条件注册、自动登录）
- KOOK / Discord 聊天集成（奖励通知、欢迎消息）
- sensai AI 助教（基于 Open WebUI）
- Prometheus / Grafana 监控栈（5 个 exporter + 自定义指标）
- 请求日志与追踪（trace_id 传播、结构化日志）
- 奖励体系（绶带晋级 + emoji 徽章）
- Seccomp 安全加固（clone/unshare/setns/sethostname 已收紧）

补充 docker-compose 13 容器职责表、dojo_plugin 代码分层、flag HMAC 签发机制。

#### 2. 填充 `development.md`（原为空）

- 环境准备与本地开发流程
- 插件/主题热更新机制（dojo sync）
- dojo 命令参考表
- pytest 测试框架（关键 fixture 和辅助函数）
- 代码组织（pages/api/utils/models 分层）
- 分支策略（hustsec_dev、CTFd 3.6.0 锁定）
- 常见开发任务和调试技巧

#### 3. 填充 `challenge.md`（原为空）

- 挑战安全模型（hacker UID 1000、/flag setuid、flag 独立签发）
- 道馆 YAML 定义参考（Dojo/Module/Challenge/Resources 完整字段）
- 挑战容器生命周期（启动→6h超时→practice vs normal）
- 镜像级别（nano/micro/mini/full）与工具预装配置
- 工作区三种访问方式（VSCode/桌面/SSH）
- 内核挑战、虚拟机、变体反作弊

#### 4. 填充 `pwnhustcollege_deployment.md`（原为空）

HUST 特定部署流程：
- 华科镜像源安装 Docker、构建、启动
- HTTPS 证书部署
- SSO 配置与启用
- KOOK、Discord 机器人配置
- AI 助教（sensai）配置
- Prometheus/Grafana 监控配置
- 备份恢复与更新流程

#### 5. 更新 `data_config_env.md`

- 补充 `ENABLE_SSO`、`CAS_*` 等 SSO 配置变量
- 补充 `OLLAMA_BASE_URLS`、`OPENAI_API_BASE_URL` AI 助教配置变量
- 新增核心配置字段和工具安装选项的表格说明

#### 6. 去重 `User_Manual_For_Teachers.md`

删除第三节"学生手册"（与 `User_Manual_For_Students.md` 完全重复），替换为交叉引用。

#### 7. 更新 `README.md`

新增 `data_config_env.md`、学生手册、教师手册链接。

### Verification

- [x] 3 个之前为空的文件现已填充完整
- [x] README.md 所有 9 个链接指向有效文件
- [x] architecture.md 提到的功能均有对应代码支撑
- [x] User_Manual_For_Teachers.md 不再包含学生手册重复内容

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
