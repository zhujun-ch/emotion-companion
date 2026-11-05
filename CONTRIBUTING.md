# 双人协作约定

两名成员共同参与前后端与算法，按功能任务轮换主负责人和审阅人。具体安排见 PROJECT_PLAN.md 第十节。

## 两种协作方式

推荐仓库所有者邀请同伴为协作者，接受邀请后，双方可推送各自的功能分支并发起 Pull Request。公开仓库不自动授予其他用户推送权限。

暂不邀请时，同伴先 Fork 仓库，在个人副本开发并推送，再向原仓库提交 Pull Request，由所有者审阅合并。此方式需要仓库允许相应 Pull Request。不要共享账号、密码或访问令牌。

## 推荐流程的操作命令

仓库所有者在 Settings → Collaborators → Add people 邀请同伴。同伴接受邀请，并在自己的电脑安装 Git；HTTPS 推送按提示使用浏览器或凭据管理器授权，也可运行 `gh auth login`。GitHub 网页登录本身不等于命令行已授权。

首次下载：

```powershell
git clone https://github.com/zhujun-ch/emotion-companion.git
cd emotion-companion
git config user.name "你的名字"
git config user.email "你的 GitHub 提交邮箱"
```

开始新功能前，确认本地没有未保存的修改，再同步主分支并新建分支：

```powershell
git switch main
git pull --ff-only origin main
git switch -c feat/chat-page
```

完成修改后，先检查差异和文件清单，只添加自己要提交的文件：

```powershell
git status
git diff
git add README.md
git commit -m "docs: update project instructions"
git push -u origin feat/chat-page
```

以上 `README.md` 和分支名是示例，应替换为实际修改的文件和本次功能名称。新增文件需确认内容后添加；不要为了方便把私人配置或数据强制加入 Git。

推送成功后，在 GitHub 打开 Compare & pull request，目标分支选择 main，另一人检查后合并。合并完成，双方更新：

```powershell
git switch main
git pull --ff-only origin main
```

如果尚有未提交修改，先提交到当前功能分支或妥善暂存，再切换分支。遇到冲突先定位并共同处理，不使用强制推送覆盖对方代码。拉取仓库不会自动安装依赖，也不会包含默认忽略的模型、原始数据和密钥。

## 不邀请时的操作

同伴在网页 Fork 原仓库，然后克隆自己的副本；将下面 YOUR_USERNAME 替换为同伴账号：

```powershell
git clone https://github.com/YOUR_USERNAME/emotion-companion.git
cd emotion-companion
git remote add upstream https://github.com/zhujun-ch/emotion-companion.git
git fetch upstream
git switch -c feat/chat-page upstream/main
```

完成后提交并推送到自己的 origin，在网页发起从个人 Fork 到 zhujun-ch/emotion-companion 的 Pull Request。以后在本地 main 没有额外提交的情况下，可用以下命令同步原仓库：

```powershell
git switch main
git fetch upstream
git merge --ff-only upstream/main
git push origin main
```

## 分支与合并

- `main` 保存能够运行或完成审阅的内容。
- 开发使用 `feat/功能名`、`fix/问题名` 或 `docs/主题` 分支。
- 每个任务通过 Issue 记录目标、负责人和验收条件。
- 通过 Pull Request 合并，另一位成员检查接口兼容性和验证结果。
- 接口、情绪标签或数据结构发生变化时，同步更新文档，并通知另一位成员。

## 模块协作

- 模型开发期间，前端按双方确认的接口示例使用模拟数据；演示真实识别时必须连接真实模型。
- 训练脚本保存随机种子、数据划分标识、参数和评估结果。
- 提交模型结构或推理代码时，说明匹配的模型版本和获取方式。
- 每次合并说明实际验证步骤；尚未完成的功能应明确列出。

## 提交内容

- 不提交密钥、数据库密码、私人开发工具配置或真实用户倾诉记录。
- 原始语料、处理后的数据和模型权重默认不进入 Git；在确认使用条件后，通过双方可访问的受控方式共享。
- 示例数据使用虚构文本，并明确标注为示例。
- 依赖清单、无密钥配置示例、启动说明和数据库结构定义应纳入版本控制。
- `.gitignore` 默认忽略 SQL 导出文件；数据库结构脚本确定目录后，单独添加白名单规则。

