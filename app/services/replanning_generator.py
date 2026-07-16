def value(data, key, fallback="未填写"):
    raw = data.get(key, fallback) if hasattr(data, "get") else fallback
    if raw is None:
        return fallback
    text = str(raw).strip()
    return text or fallback


def generate_replanning_agreement(student, data):
    original_goal = value(data, "original_goal")
    new_primary_goal = value(data, "new_primary_goal")
    new_secondary_goal = value(data, "new_secondary_goal")
    new_third_goal = value(data, "new_third_goal")
    trigger_event = value(data, "trigger_event")
    responsibility_type = value(data, "responsibility_type")
    fee_adjustment_type = value(data, "fee_adjustment_type")

    return "\n".join(
        [
            f"# {student.name}执行变更与重规划补充协议草稿",
            "",
            "## 一、变更背景",
            f"学生原阶段目标为：{original_goal}。",
            f"本次触发重规划的事件为：{trigger_event}。",
            f"原因说明：{value(data, 'trigger_reason')}。",
            f"初步责任归因：{responsibility_type}。",
            "",
            "## 二、原服务完成情况",
            f"原服务范围：{value(data, 'original_service_scope')}。",
            f"已完成工作：{value(data, 'completed_work')}。",
            "双方确认，已完成工作应作为本次重规划的依据之一；可复用成果应优先转入新路径，避免前期投入浪费。",
            "",
            "## 三、新目标路径",
            f"- 新第一目标：{new_primary_goal}",
            f"- 新第二目标：{new_secondary_goal}",
            f"- 新第三目标：{new_third_goal}",
            "若新第一目标再次因学生执行、材料真实性、政策变化、成绩条件或不可抗因素无法推进，应按本协议约定再次触发复盘。",
            "",
            "## 四、新服务范围",
            value(data, "new_service_scope"),
            "",
            "## 五、费用调整",
            f"费用调整方式：{fee_adjustment_type}。",
            f"新增费用：{value(data, 'additional_fee')}。",
            f"抵扣或退费：{value(data, 'refund_or_credit')}。",
            f"费用说明：{value(data, 'fee_notes')}。",
            "所有新增专项服务、课时、申请、材料、竞赛科研、语言考试、就业辅导等费用，应在启动前单独确认。",
            "",
            "## 六、免责与确认",
            "本补充协议不承诺保研、考研录取、留学录取、就业录用、转专业成功、考试通过或其他外部结果。",
            "学生执行情况、材料真实性、学校政策、考试结果、市场变化及外部录取规则变化，均可能影响最终结果。",
            "因学生方原因导致原第一目标无法完成时，后续转入第二或第三目标所产生的服务范围变化与费用变化，应以本补充协议或后续确认文件为准。",
            "",
            "## 七、其他约定",
            value(data, "agreement_terms"),
        ]
    )
