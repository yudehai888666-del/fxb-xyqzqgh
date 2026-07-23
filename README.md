# 学业规划本地网页系统

## 第一阶段实现内容

- 学生主档案
- 主要家长问卷
- 学生问卷
- 可选材料上传
- 材料缺失免责确认
- 老师访谈与内部诊断
- 信息完整度状态

## 第二阶段实现内容

- 初步规划草稿生成
- 信息依据与免责声明自动写入规划草稿
- 目标风险、备选路径与责任边界章节
- 本地 Markdown 文件保存
- 学生详情页查看已有规划草稿

生成的规划草稿默认保存到：

```text
generated/plans/student-<学生ID>/plan-<规划ID>.md
```

## 断点恢复启动

如果开发中断、上下文丢失、或者需要从 Git 仓库恢复到保存好的最新版本，按下面顺序执行：

```bash
./scripts/bootstrap_latest.sh
./scripts/start_local.sh
```

打开：

```text
http://127.0.0.1:5050
```

也可以直接用一行命令：

```bash
/Users/yu/Desktop/学业规划/scripts/launch_local.command
```

桌面上可以放两个双击入口：

```text
启动学业规划.command
启动学业规划-公网.command
```

`启动学业规划.command` 会拉取 Git 最新版、后台启动本地服务，并自动打开浏览器。`启动学业规划-公网.command` 会拉取 Git 最新版，然后开启临时公网。

默认检查账号：

```text
用户名：check-admin
密码：check123456
```

如果需要先检查当前版本是否具备启动条件：

```bash
./scripts/check_local.sh
```

## 临时公网访问

需要把当前本地服务临时开放给外部访问时，执行：

```bash
./scripts/start_public.sh
```

脚本会优先使用 `cloudflared`。如果本机没有 `cloudflared`，但有 `npx`，会自动改用 `localtunnel`。

macOS 安装 `cloudflared`：

```bash
brew install cloudflared
```

脚本会先确认本地服务运行在 `http://127.0.0.1:5050`，再开启临时公网。终端中出现的 `https://*.trycloudflare.com` 或 localtunnel 的 `https://...` 就是临时公网地址。

## 本地运行

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5050

## 就业市场数据运行手册

造船与计算机职业族的岗位、技能、薪资和发展方向均须经过来源、审核和有效期治理，不能把未经审核的采集结果直接用于学生规划。

首次可由管理员在已存在管理员账号后写入待审核的种子知识：

```bash
python scripts/seed_career_knowledge.py --db instance/academic_planning.sqlite3 --owner-user-id <管理员ID> --reviewer-user-id <管理员ID>
```

该命令只写入草稿。采集前，管理员和老师必须在后台逐项审核并发布种子中的专业、岗位、技能，以及需要用于推荐的专业-岗位关联和岗位-技能关联。岗位-技能关联必须先补齐已启用来源、样本量、核验日期和限制说明，才可以发布；未发布岗位不能被爬虫采集。

完成来源登记、知识审核和岗位发布后，才可针对已发布岗位和城市运行采集：

```bash
python scripts/career_crawler.py --job "船舶设计工程师" --city "上海"
```

老师的操作顺序：

1. 管理员运行种子命令，得到待审核的造船与计算机专业、岗位、技能和关联草稿。
2. 管理员登记公开来源、填写合规说明并启用来源。
3. 管理员或老师核验并发布所需的专业、岗位、技能和专业-岗位关联；为岗位-技能关联补齐来源、样本量、核验日期和限制说明后再发布。
4. 管理员确认目标岗位已是“已发布”状态，再为该岗位和城市运行采集任务。
5. 老师核验市场快照草稿的来源、来源快照、样本量、限制说明和技能关系。
6. 管理员发布市场快照和岗位技能关系。
7. 老师在学生就业工作区选择专业推荐或个人计划，并确认目标岗位。

遇到验证码、登录要求、`429`、`503`、页面解析错误、来源未启用、置信度低或没有已发布数据时，相关采集或引用步骤必须停止。不得绕过这些控制；应补充合规来源、等待恢复、人工核验或重新审核后再继续。

## Tests

```bash
. .venv/bin/activate
python -m pytest -v
```
