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
