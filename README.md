# Emotion Companion

中文情绪识别与智能陪伴课程项目。前端位于 frontend 工作树，后端位于仓库根目录。

[项目说明书（Word）](心屿情绪识别与智能陪伴系统项目说明书.docx)涵盖项目背景、技术分析、系统分析、系统设计、系统实现及总结与展望，已同步账号投稿归属、请求去重和部署访问控制。

本地启动顺序：start-ollama.cmd、start-backend.cmd、start-frontend.cmd。
打开 http://127.0.0.1:5173/ 使用项目；test-flow.cmd 注册随机测试账号并验证分类、回复和记录保存。三端演示模式下，在运行测试前把 `SQLITE_PATH` 设为 `artifacts/pages_chat_demo.sqlite3`。

## 情绪模型训练

使用项目 .venv：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-train.txt
.\.venv\Scripts\python.exe train_textcnn.py
```

数据目录为 `评测数据集`。训练读取 train 下的两个 JSON 格式 txt；验证读取 eval 下的 labeled txt；最终测试读取“真实评测集”下的 labeled txt。xlsx 为相同内容的副本，不重复读取；含混淆数据和无标签文件不参与训练。

训练/验证文本去重并移除标签冲突、空文本与二者重叠。词表只从训练集构建。最多训练 15 轮，验证宏平均 F1 连续 3 轮未改善则停止，选择验证 F1 最佳权重。

模型输出六类：愤怒、恐惧、快乐、中性、悲伤、惊奇。训练和推理共用 emotion_model.py。

训练产物位于 `artifacts/emotion_cnn/`：best_model.pt、vocab.json、config.json、history.json、metrics.json、data_audit.json。后端通过 EMOTION_MODEL_DIR（默认该目录）加载新权重；根目录旧 textcnn_model.pth/word2id.pkl 保留但不再加载。

2026-11-06 本地训练：训练 34378 条、验证 3831 条；第 8 轮最佳，共运行 11 轮。官方测试 8000 条：准确率 70.375%，宏平均 F1 0.63605；去重并排除训练/验证文本重叠后的 7308 条：准确率 68.623%，宏平均 F1 0.62340。该结果来自微博文本，聊天界面的实际效果仍取决于输入内容。

训练权重、原始数据、数据库和本机 .env 不应随代码提交。重新训练会覆盖默认产物目录；使用 --output 可指定另一个训练目录，并通过 EMOTION_MODEL_DIR 切换。

## 对话情绪参考（2026-11-06）

聊天先结合最近对话判断当前消息属于陪伴、混合请求、需澄清、偏题或紧急风险。偏题、澄清和紧急风险使用后端固定文本。混合请求从原文截取感受或处境供生成和后续上下文使用，聊天记录保留原文。陪伴和混合请求生成后再结合完整输入复核。未通过复核时显示固定追问，模型调用或检查失败时可重试。偏题轮次保留在会话记录里，后续模型上下文和情绪参考会跳过这些轮次。

运行 `.venv\Scripts\python.exe evaluate_chat_boundary.py` 可用 60 条合成样例对照原提示词、输入分类加边界提示词、输入分类加输出复核三种配置。结果逐条写入 `artifacts/chat-boundary-evaluation.jsonl`。样例使用人工设定的预期类别，生成回复的贴合度需要对照文本复核。

前 3 条用户消息不输出情绪倾向，第 4 条起检查最近最多 5 条用户表达。简短附和不作为主要证据；最近三条有效表达至少两条支持同一方向，且最新表达支持该方向、与至少另一条表达达到类别展示阈值，才给出较明确的参考。未达到条件时展示两个带“不确定”说明的候选方向，不把候选注入回复模型。多句汇总仅是保守规则，未宣称具备经过对话数据验证的准确率。

单句 CNN 原始预测仍存储用于对照，不直接显示给用户或无条件注入生成模型。没有可靠参考时，生成模型只依据用户原话和历史回复。页面统一展示近期参考，可提交“符合”或选择更正；反馈单独保存在 emotion_feedback，不覆盖原始预测，也不实时训练。打开已有对话时重新计算最近表达参考，只更新派生参考，不修改消息正文和原始预测。

训练新权重后执行：

```powershell
.\.venv\Scripts\python.exe calibrate_emotion.py
```

校准仅使用验证集：随机分成温度拟合和类别阈值选择两部分；目标为选择部分上至少 20 个样本、经验正确比例达到 80%。这是阈值选择目标，不能理解为实际聊天准确率承诺。原验证集曾用于模型选择，校准结果也不是独立最终评估；最终测试集不参与调参。惊奇类别本次无合格阈值，暂不展示自动结论。校准与权重 SHA-256 绑定；缺失或不匹配时拒绝输出倾向，仍可正常聊天。

重新训练不改变现有校准文件，但新权重不匹配时该文件自动失效；须重新运行校准。结果位于 artifacts/emotion_cnn/calibration.json。

验证命令：`.venv\Scripts\python.exe -m unittest discover -s tests -v`。
客户端请求编号重试验证：`node --test frontend/composables/requestIds.test.mjs`。

## 三端页面演示

先在本地 `.env` 中设置审核员密码哈希文件（`DEMO_REVIEWER_PASSWORD_HASH_FILE`，生成方法见下文；本地演示兼容 `DEMO_REVIEWER_PASSWORD`），再运行 `start-ollama.cmd` 和 `start-pages-demo-backend.cmd`，然后分别打开三个前端。

- 网页客户端运行 `start-frontend.cmd`，打开 http://127.0.0.1:5173/ 。
- 管理端进入 `admin` 目录运行 `npm.cmd ci`，再运行 `npx.cmd vite --host 127.0.0.1 --port 5174`，打开 http://127.0.0.1:5174/ 。演示账号默认为 `admin`，账号和口令由后端的 `DEMO_REVIEWER_USERNAME` 和 `DEMO_REVIEWER_PASSWORD` 配置。
- 小程序运行 `build-demo-miniprogram.cmd`。每次构建生成独立目录，成功后更新仓库根目录本地 `project.config.json` 的小程序路径。已在微信开发者工具中打开根目录项目时，选择「项目 → 重新打开此项目」，再编译。也可直接导入命令输出的构建目录。HBuilderX 安装位置不同时，通过 `HX_APP_ROOT` 指定。手机端需重新扫码加载新版。

树洞演示可分别提交鼓励、普通倾诉、明确违规和语境不明的虚构内容。Flask 先拦截链接和联系方式，再通过本机 Ollama 进行语义审核。低风险稿件自动发布，明确违规稿件拦截，疑难稿件和模型异常进入待审。树洞页面底部的「管理员登录」使用同一个演示审核员账号，登录后可在公开列表下架，或进入「待审核」与「处理记录」。独立网页管理端也可继续使用。

公开的树洞留言下可匿名回复，回复与主帖使用相同的自动审核。审核通过的回复立即显示在原留言下；拦截或待审的回复仅对作者显示状态，待审回复可由管理员通过或驳回。作者可在「我的投稿」撤回回复，管理员可下架已发布的回复。原留言下架后，其回复一并从公开列表隐藏，历史记录仍保存在数据库中。

网页和小程序共用心屿账号。先在任一端注册，再在另一端使用同一账号和密码登录。两个端各自持有登录凭据，进入页面时从服务端读取会话和消息；也可以使用刷新入口。退出一端只撤销该端凭据。心情日记、看板、树洞「我的投稿」和本人回复均按登录账号读取；公开留言和回复继续匿名展示，公开接口不返回作者账号、用户编号或投稿凭据。审核员账号独立。

旧设备仍保存投稿令牌时，登录后在树洞点击「关联本设备历史投稿」，将该令牌对应的旧投稿及回复一次性关联到当前账号。同一令牌可由同一账号重复认领，不能转给其他账号。没有旧凭据的内容保留原状态，不凭投稿编号或客户端传来的用户编号认领。游客可浏览公开内容，投稿、回复、本人记录及撤回需要登录；旧 `/posts/session` 接口返回 410，升级客户端后使用账号登录。

聊天会话和账号保存在 `pages_chat_demo.sqlite3`，树洞、审核记录和日记保存在 `pages_demo.sqlite3`。演示模式默认使用项目下的 `artifacts` 目录。升级前使用设备标识的聊天、共享日记和旧树洞投稿仍保留在数据库中，新注册的账号从空的会话与日记开始。

运行 `.venv\Scripts\python.exe inspect_sqlite.py`，打开 http://127.0.0.1:5175/ 查看本机 SQLite 的表结构、索引和行数。

同网手机联调时，运行 `start-pages-demo-backend.cmd lan` 让后端监听局域网，再运行 `build-demo-miniprogram.cmd lan`。构建会读取电脑当前有默认网关的物理网卡 IPv4 地址并写入小程序，默认使用 `5000` 端口。电脑换网或 IP 变化后，重新构建，在微信开发者工具重新打开项目，再生成真机调试码。多网卡、热点或自定义端口环境可以在构建前将 `VITE_API_BASE` 设为手机可访问的后端地址。本轮演示只填虚构内容。

### 部署时保留数据

用 `DEMO_DATA_DIR` 指定后端可读写的持久目录。单机可用固定数据目录，容器环境可把持久卷挂载到该目录。直接启动 Flask 时，演示模式设置 `ENABLE_DEMO_PAGES=1` 与 `DB_BACKEND=sqlite`。部署口令通过环境配置，使用独立强密码。

迁移时先备份两个 SQLite 数据库，并在新服务启动前将备份恢复到 `DEMO_DATA_DIR`。升级和重启继续使用同一目录。启动时自动增加账号归属、登录凭据元数据和请求回执表，原正文、状态和审核记录保留。已关联账号的投稿可换端读取；尚未认领的旧投稿需要保留原设备令牌才能关联。

运行中的数据库使用 [SQLite 备份接口](https://sqlite.org/backup.html) 生成一致性快照，备份存放在独立位置。恢复时停止使用目标数据库的服务，恢复后验证旧留言和会话可以读取。

## 请求编号与事务去重

聊天、新建会话、新增日记、树洞投稿和回复支持 JSON `request_id` 或 `X-Request-ID` 请求头，编号为 8～128 位字母、数字、下划线或连字符。新客户端为写入生成编号，网络失败重试时保留原编号；聊天失败气泡的重试也复用编号。收到明确成功响应后才清除对应的待确认请求。待确认记录按账号保存，退出登录会清除本机该账号的待确认记录。

服务端按「账号＋操作＋请求编号」保存内容摘要和结果；同编号同内容返回原结果，同编号不同内容返回 409。回执和业务写入在同一个 `BEGIN IMMEDIATE` 事务中提交，主帖/回复及审核日志、聊天消息对及情绪记录随事务一起回滚。并发进程即使同时完成模型调用，事务提交后也只有一份业务记录，返回同一组编号。此处保证写入去重，不保证并发时只调用一次模型。回执是原提交结果，当前审核状态以刷新列表为准。

聊天提交还核对生成前的消息数量；其他进程抢先提交时，旧上下文生成的另一条回复返回 409，刷新后可重试。模型失败不保存半轮消息。显式使用聊天请求编号时必须先创建会话并传 `session_id`；旧调用方不传编号时由服务器生成，但响应丢失后无法凭空恢复该编号。当前版本以 SQLite 作为事务写入源，`DB_BACKEND=mysql` 会拒绝启动，避免跨库写入产生不完整回执。日后切换 MySQL 时需整体迁移同一事务内的业务表与回执表。

## 登录凭据与访问控制

首页账号名称可打开「账号管理」：查看当前有效登录及到期时间、撤销指定端、退出所有端、修改密码。修改密码需要当前密码，成功后撤销全部登录凭据；账号和投稿归属不变。数据库仅保存密码哈希和令牌 SHA-256，不保存原始令牌。凭据默认 30 天，可通过 `ACCOUNT_TOKEN_TTL_SECONDS` 缩短（范围 300～2592000 秒）。登录/注册及改密尝试按来源 IP 和账号限流，使用数据库计数跨进程生效；超过限额返回 429，窗口为 15 分钟。审核员凭据仍保存在客户端内存中，服务端有效期 8 小时；更换审核员密码哈希后旧凭据失效。

在 Windows CMD 中生成新的审核员密码哈希文件（密码通过隐藏输入获取，不写进命令行；已存在文件不会覆盖）：

```bat
cd /d F:\workshop\emotion
.venv\Scripts\python.exe manage_reviewer.py artifacts\secrets\reviewer-v2.hash
```

在 `.env` 设置 `DEMO_REVIEWER_PASSWORD_HASH_FILE=artifacts/secrets/reviewer-v2.hash`，清空 `DEMO_REVIEWER_PASSWORD`，然后重启后端。文件仅供服务运行账号读取，不提交 Git。生产环境也支持由部署系统设置 `DEMO_REVIEWER_PASSWORD_HASH`；优先使用受保护文件挂载。

默认只允许本机网页来源与主机名；审核接口只接受回环网络。局域网测试在 `.env` 的 `APP_TRUSTED_HOSTS` 中加入电脑实际 IPv4；网页从其他设备打开时，在 `APP_ALLOWED_ORIGINS` 加入其完整来源（协议、主机、端口）。普通手机投稿无需开放审核网段。确需远程审核时，将可信管理网段加入 `REVIEWER_ALLOWED_NETWORKS`。拒绝任意来源、无效 Host 和不可信审核网络；不信任客户端提供的 `X-Forwarded-For`。API 响应禁止缓存，请求体限制为 32 KiB。

### 生产运行

生产入口使用支持 Windows 的 [Waitress](https://flask.palletsprojects.com/en/stable/deploying/waitress/)，后端仅监听回环地址；HTTPS 反向代理配置示例见 `deploy/nginx.conf.example`。主机白名单依据 [Flask 安全文档](https://flask.palletsprojects.com/en/stable/web-security/)设置。部署前替换示例域名、证书路径、静态目录和管理 VPN 网段，执行 `nginx -t` 检查配置。只将构建后的前端静态目录作为网站根目录，不将项目、数据库、备份或秘密文件目录映射到网站。

```bat
cd /d F:\workshop\emotion
.venv\Scripts\python.exe -m pip install -r requirements.txt
set APP_ENV=production
set ENABLE_DEMO_PAGES=1
set DB_BACKEND=sqlite
set APP_ALLOWED_ORIGINS=https://emotion.example.com
set APP_TRUSTED_HOSTS=emotion.example.com
set REVIEWER_ALLOWED_NETWORKS=127.0.0.1/32
set DEMO_REVIEWER_PASSWORD=
set DEMO_REVIEWER_PASSWORD_HASH_FILE=artifacts/secrets/reviewer-v2.hash
.venv\Scripts\python.exe serve_production.py
```

生产入口要求明确配置来源、主机、审核网段和密码哈希；来源须使用 HTTPS。反向代理转发后应用看到的是代理地址，因此 Nginx 的审核路径和 `/admin/` 路径还必须按真实来源 IP 限制，仅向管理 VPN 开放。后端 5000、Ollama 11434 和 SQLite 查看器 5175 不开放公网。网页和管理端分别以实际 HTTPS 地址设置 `VITE_API_BASE` 后构建，小程序使用同一个 HTTPS API 域名并配置微信合法请求域名。当前仓库提供本地验证过的 WSGI 入口和部署示例，未执行真实域名、证书或公网部署。
