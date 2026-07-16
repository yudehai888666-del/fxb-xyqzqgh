from app import repositories


def row_to_dict(row):
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    return {key: row[key] for key in row.keys()}


def value(data, key, fallback="未填写"):
    if data is None:
        return fallback
    if hasattr(data, "get"):
        raw_value = data.get(key, fallback)
    else:
        try:
            raw_value = data[key]
        except (KeyError, IndexError):
            raw_value = fallback
    if raw_value is None:
        return fallback
    text = str(raw_value).strip()
    return text or fallback


def build_planning_context(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        raise ValueError("学生不存在")

    return {
        "student": student,
        "student_questionnaire": row_to_dict(
            repositories.get_student_questionnaire(student_id)
        ),
        "parent_questionnaire": row_to_dict(
            repositories.get_parent_questionnaire(student_id)
        ),
        "materials": [
            row_to_dict(material) for material in repositories.list_materials(student_id)
        ],
        "disclaimers": [
            row_to_dict(disclaimer)
            for disclaimer in repositories.list_disclaimers(student_id)
        ],
        "teacher_notes": row_to_dict(repositories.get_teacher_notes(student_id)),
    }


def generate_information_basis(context):
    materials = context["materials"]
    disclaimers = context["disclaimers"]

    lines = [
        "本规划基于学生主档案、学生问卷、主要家长问卷、老师访谈记录以及当前已上传材料生成。",
    ]

    if materials:
        lines.append("当前已上传材料：")
        for material in materials:
            lines.append(f"- {value(material, 'original_filename')}")
    else:
        lines.append("当前未上传关键材料。")

    if disclaimers:
        lines.append("已确认免责。")
    else:
        lines.append("当前尚未完成免责确认。")

    lines.extend(
        [
            "规划内容用于阶段性路径建议与沟通参考，不构成保研、录取、转专业、就业或考试结果承诺。",
            "若后续成绩、政策、材料真实性、学生执行情况发生变化，应重新评估并更新规划。",
        ]
    )
    return "\n".join(lines)


def generate_initial_plan(context):
    student = context["student"]
    student_questionnaire = context["student_questionnaire"]
    parent_questionnaire = context["parent_questionnaire"]
    teacher_notes = context["teacher_notes"]

    title = f"{student.name}大学四年初步规划"
    body = "\n\n".join(
        [
            f"# {title}",
            _student_profile_section(student),
            "## 二、信息依据与免责声明\n"
            f"{generate_information_basis(context)}",
            _family_goals_section(parent_questionnaire, teacher_notes),
            _academic_support_section(student_questionnaire, teacher_notes),
            _major_transfer_section(student, student_questionnaire, teacher_notes),
            _four_year_goals_section(student_questionnaire, parent_questionnaire),
            _yearly_plan_section(student_questionnaire, parent_questionnaire),
            _risk_boundaries_section(
                student_questionnaire, parent_questionnaire, teacher_notes
            ),
            _follow_up_section(student, teacher_notes),
        ]
    )
    return {"title": title, "content_markdown": body}


def _student_profile_section(student):
    return "\n".join(
        [
            "## 一、学生基础画像",
            f"- 姓名：{student.name}",
            f"- 性别：{student.gender}",
            f"- 入学年份：{student.enrollment_year}",
            f"- 当前学期：{student.current_term}",
            f"- 学校：{student.school}",
            f"- 学院与专业：{student.college} / {student.major}",
            f"- 所在城市：{student.city or '未填写'}",
            f"- 当前服务阶段：{student.service_stage}",
            f"- 负责老师：{student.responsible_teacher}",
        ]
    )


def _family_goals_section(parent_questionnaire, teacher_notes):
    return "\n".join(
        [
            "## 三、家庭资源与升学目标分析",
            f"家庭资源：{value(parent_questionnaire, 'family_resources')}。",
            f"目标优先级：{value(parent_questionnaire, 'target_priorities')}。",
            f"家长观察：{value(parent_questionnaire, 'parent_observations')}。",
            f"当前顾虑：{value(parent_questionnaire, 'current_concerns')}。",
            f"资源匹配判断：{value(teacher_notes, 'resource_match_level')}。",
            "建议先统一家庭与学生对目标排序、投入节奏和复盘频率的共识，再把资源投向绩点、竞赛、科研和升学信息差补齐。",
        ]
    )


def _academic_support_section(student_questionnaire, teacher_notes):
    return "\n".join(
        [
            "## 四、学业基础与学科辅导建议",
            f"当前学业状态：{value(student_questionnaire, 'academic_status')}。",
            f"薄弱科目：{value(student_questionnaire, 'weak_subjects')}。",
            f"辅导需求：{value(student_questionnaire, 'tutoring_needs')}。",
            f"老师判断的学业风险：{value(teacher_notes, 'academic_risk')}。",
            "建议以绩点稳定为第一阶段抓手，对薄弱课程建立周计划、错题复盘和阶段测评机制；如存在高等数学等关键课程压力，应优先安排学科辅导。",
        ]
    )


def _major_transfer_section(student, student_questionnaire, teacher_notes):
    return "\n".join(
        [
            "## 五、专业适应与转专业目标建议",
            f"当前专业：{student.major}。",
            f"适应情况：{value(student_questionnaire, 'adaptation_status')}。",
            f"未来意向：{value(student_questionnaire, 'future_intentions')}。",
            f"转专业可行性：{value(teacher_notes, 'transfer_feasibility')}。",
            "建议在不牺牲当前专业绩点的前提下，尽早核对目标专业转入条件、课程门槛、时间窗口和名额规则，并准备可替代的辅修、双学位或跨专业项目路径。",
        ]
    )


def _four_year_goals_section(student_questionnaire, parent_questionnaire):
    return "\n".join(
        [
            "## 六、四年总体发展目标",
            f"目标排序以家庭确认的“{value(parent_questionnaire, 'target_priorities')}”为核心参考。",
            f"结合学生兴趣优势“{value(student_questionnaire, 'interests_strengths')}”，四年目标应围绕绩点、英语能力、竞赛科研、实习实践和升学材料逐步展开。",
            "大一重在适应与绩点基础，大二重在方向确认与能力补强，大三重在成果沉淀与升学准备，大四重在申请、考试、就业或备选路径落地。",
        ]
    )


def _yearly_plan_section(student_questionnaire, parent_questionnaire):
    return "\n".join(
        [
            "## 七、大一到大四年度规划",
            f"- 大一：围绕“{value(student_questionnaire, 'motivation_status')}”建立稳定作息、课程复盘和学习监督机制。",
            f"- 大二：结合目标优先级“{value(parent_questionnaire, 'target_priorities')}”，确认保研、考研、就业及转专业的关键条件。",
            "- 大三：集中产出竞赛、科研、实习或语言成绩，形成可用于升学与就业的证明材料。",
            "- 大四：根据前三年成绩排名、政策变化和个人执行结果，完成保研申请、考研冲刺、就业投递或其他备选方案。",
        ]
    )


def _risk_boundaries_section(
    student_questionnaire, parent_questionnaire, teacher_notes
):
    return "\n".join(
        [
            "## 八、目标风险、备选路径与责任边界",
            f"- 第一目标：以“{value(parent_questionnaire, 'target_priorities')}”中的最高优先级为阶段牵引，但需接受学校政策和竞争环境约束。",
            f"- 风险触发：当绩点排名、关键课程、执行稳定性或政策条件与目标要求明显偏离时，应触发复盘；当前执行风险为{value(teacher_notes, 'execution_risk')}，学业风险为{value(teacher_notes, 'academic_risk')}。",
            f"- 第二路径：若保研或转专业条件不足，应及时转入考研、校内项目、辅修双学位或目标专业相关实践积累。",
            "- 第三路径：若升学路径阶段性受阻，应同步建设实习、作品、证书和求职能力，保留高质量就业选择。",
            f"- 费用边界：参考家庭投入意愿“{value(parent_questionnaire, 'investment_willingness')}”，所有辅导、竞赛、科研、申请服务和考试投入均应提前确认预算、目标和退出条件。",
            "以上规划提供路径建议与沟通框架，学生执行、家庭投入、材料真实性、学校政策和外部录取结果均不由本规划单方面决定。",
        ]
    )


def _follow_up_section(student, teacher_notes):
    return "\n".join(
        [
            "## 九、后续跟进建议",
            f"建议由{student.responsible_teacher}每月跟进一次学习执行、课程风险和材料准备进度。",
            f"服务建议：{value(teacher_notes, 'service_suggestions')}。",
            f"后续生成重点：{value(teacher_notes, 'ai_generation_focus')}。",
            "每学期应结合成绩单、政策通知、家庭沟通记录和学生执行反馈更新一次规划版本。",
        ]
    )
