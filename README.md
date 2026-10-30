# Emotion Companion

中文情绪识别与智能陪伴课程项目，由两人共同开发前后端与算法实验。

## 项目方案

- [完整项目方案](PROJECT_PLAN.md)
- [双人协作流程](CONTRIBUTING.md)

技术路线：uni-app Vue3、Flask、MySQL、scikit-learn 和 PyTorch。情绪标签采用 SMP2020-EWECT 原生六分类；SVM 与 TextCNN 自行训练，智谱 GLM 仅负责生成陪伴回复。

## 当前状态

目前完成项目方案与协作仓库初始化，尚未实现可运行系统，也没有已验证的训练结果。开发周期为六周，先完成本地及局域网真机演示，云端部署后续决定。

## 目录规划

- `frontend/`：uni-app 小程序及 H5。
- `backend/`：Flask API、身份与会话、模型推理。
- `training/`：数据处理、模型训练和评估。
- `analysis/`：K-Means、t-SNE 离线实验。
- `database/migrations/`：版本化数据库结构。
- `docs/`：接口、环境、实验和演示说明。

以上是规划目录，代码按开发任务逐步加入。

## 本地运行

运行说明将在首个可运行版本中补齐。原始数据、模型权重和密钥默认不进入仓库。不要把真实倾诉记录用于公开演示或提交。

## 协作权限

公开仓库允许直接克隆和拉取；直接推送需要协作者写权限。不邀请时可 Fork，在个人副本开发后向本仓库提交 Pull Request。建议长期双人协作使用邀请协作者的方式。

