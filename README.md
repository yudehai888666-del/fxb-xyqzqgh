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

如果需要先检查当前版本是否具备启动条件：

```bash
./scripts/check_local.sh
```

## 临时公网访问

需要把当前本地服务临时开放给外部访问时，先安装 `cloudflared`，然后执行：

```bash
./scripts/start_public.sh
```

macOS 安装 `cloudflared`：

```bash
brew install cloudflared
```

脚本会先确认本地服务运行在 `http://127.0.0.1:5050`，再开启临时公网。终端中出现的 `https://*.trycloudflare.com` 就是临时公网地址。

## 本地运行

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5050

## Tests

```bash
. .venv/bin/activate
python -m pytest -v
```
