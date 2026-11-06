# Emotion Companion

中文情绪识别与智能陪伴课程项目。前端位于 frontend 工作树，后端位于仓库根目录。

本地启动顺序：start-ollama.cmd、start-backend.cmd、start-frontend.cmd。
打开 http://127.0.0.1:5173/ 使用项目；test-flow.cmd 验证分类、回复和记录保存。

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

前 3 条用户消息不输出情绪倾向，第 4 条起检查最近最多 5 条用户表达。简短附和不作为主要证据；最近三条有效表达至少两条支持同一方向，且最新表达支持该方向、与至少另一条表达达到类别展示阈值，才给出较明确的参考。未达到条件时展示两个带“不确定”说明的候选方向，不把候选注入回复模型。多句汇总仅是保守规则，未宣称具备经过对话数据验证的准确率。

单句 CNN 原始预测仍存储用于对照，不直接显示给用户或无条件注入生成模型。没有可靠参考时，生成模型只依据用户原话和历史回复。页面统一展示近期参考，可提交“符合”或选择更正；反馈单独保存在 emotion_feedback，不覆盖原始预测，也不实时训练。打开已有对话时重新计算最近表达参考，只更新派生参考，不修改消息正文和原始预测。

训练新权重后执行：

```powershell
.\.venv\Scripts\python.exe calibrate_emotion.py
```

校准仅使用验证集：随机分成温度拟合和类别阈值选择两部分；目标为选择部分上至少 20 个样本、经验正确比例达到 80%。这是阈值选择目标，不能理解为实际聊天准确率承诺。原验证集曾用于模型选择，校准结果也不是独立最终评估；最终测试集不参与调参。惊奇类别本次无合格阈值，暂不展示自动结论。校准与权重 SHA-256 绑定；缺失或不匹配时拒绝输出倾向，仍可正常聊天。

重新训练不改变现有校准文件，但新权重不匹配时该文件自动失效；须重新运行校准。结果位于 artifacts/emotion_cnn/calibration.json。

验证命令：`.venv\Scripts\python.exe -m unittest discover -s tests -v`。

## 三端页面演示

先运行 `start-ollama.cmd` 和 `start-pages-demo-backend.cmd`，再分别打开三个前端。

- 网页客户端运行 `start-frontend.cmd`，打开 http://127.0.0.1:5173/ 。
- 管理端进入 `admin` 目录运行 `npm.cmd ci`，再运行 `npx.cmd vite --host 127.0.0.1 --port 5174`，打开 http://127.0.0.1:5174/ 。演示账号为 `reviewer`，默认口令为 `xinyu-demo`。
- 小程序运行 `build-demo-miniprogram.cmd`。微信开发者工具中打开仓库根目录项目并编译，也可直接导入 `frontend/unpackage/dist/dev/mp-weixin-mobile`。HBuilderX 安装位置不同时，通过 `HX_APP_ROOT` 指定。若重新构建后模拟器仍显示旧布局或文字错位，选择「项目 → 重新打开此项目」，再重新编译。

建议演示顺序为新增日记、查看看板、匿名投稿、管理端通过、用户端刷新树洞。树洞演示规则拦截链接和手机号，其余新投稿进入待审。日记与树洞共用一套虚构样例空间，聊天沿用现有本地身份。演示数据单独保存在 `artifacts/pages_demo.sqlite3` 与 `artifacts/pages_chat_demo.sqlite3`。

同网手机联调时，启动后端前将 `APP_HOST` 设为 `0.0.0.0`，构建小程序前将 `VITE_API_BASE` 设为电脑局域网的后端地址。小程序使用实际的真机调试配置。本轮演示只填虚构内容。
