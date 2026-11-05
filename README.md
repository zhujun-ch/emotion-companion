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
