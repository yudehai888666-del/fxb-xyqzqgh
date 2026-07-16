from app import repositories


def create_student():
    return repositories.create_student(
        {
            "name": "李明",
            "gender": "男",
            "enrollment_year": 2024,
            "current_term": "大一下",
            "school": "测试大学",
            "college": "工学院",
            "major": "计算机科学",
            "city": "上海",
            "phone": "13800000000",
            "responsible_teacher": "张老师",
        }
    )


def replanning_data():
    return {
        "original_goal": "保研",
        "trigger_event": "排名不足",
        "trigger_reason": "本学期成绩未达到预期",
        "responsibility_type": "学生执行原因",
        "new_primary_goal": "考研",
        "new_secondary_goal": "就业",
        "new_third_goal": "留学",
        "original_service_scope": "保研路径规划",
        "completed_work": "已完成学业诊断",
        "new_service_scope": "考研院校和备考规划",
        "fee_adjustment_type": "新增专项费用",
        "additional_fee": "3000元",
        "refund_or_credit": "原费用抵扣1000元",
        "fee_notes": "启动前确认",
        "agreement_terms": "30天后复盘",
    }


def test_replanning_repository_create_list_and_status(app):
    with app.app_context():
        student_id = create_student()
        case_id = repositories.create_replanning_case(student_id, replanning_data())

        case = repositories.get_replanning_case(case_id)
        assert case["student_id"] == student_id
        assert case["new_primary_goal"] == "考研"
        assert case["status"] == "草稿"
        assert [row["id"] for row in repositories.list_replanning_cases(student_id)] == [case_id]

        repositories.update_replanning_status(case_id, "执行中")
        assert repositories.get_replanning_case(case_id)["status"] == "执行中"


def test_replanning_routes_create_render_and_update_status(client, app):
    with app.app_context():
        student_id = create_student()

    response = client.get(f"/students/{student_id}/replanning/new")
    assert response.status_code == 200
    assert "新增重规划与补充协议".encode() in response.data

    response = client.post(
        f"/students/{student_id}/replanning/new",
        data=replanning_data(),
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "李明执行变更与重规划补充协议草稿".encode() in response.data
    assert "新第一目标：考研".encode() in response.data
    assert "30天后复盘".encode() in response.data

    with app.app_context():
        case = repositories.list_replanning_cases(student_id)[0]
        case_id = case["id"]

    response = client.post(
        f"/students/{student_id}/replanning/{case_id}/status",
        data={"status": "已确认"},
    )
    assert response.status_code == 302
    with app.app_context():
        assert repositories.get_replanning_case(case_id)["status"] == "已确认"


def test_replanning_rejects_cross_student_case_and_invalid_status(client, app):
    with app.app_context():
        owner_id = create_student()
        other_id = repositories.create_student(
            {
                "name": "王芳",
                "gender": "女",
                "enrollment_year": 2024,
                "current_term": "大一下",
                "school": "测试大学",
                "college": "商学院",
                "major": "工商管理",
                "city": "北京",
                "phone": "13900000000",
                "responsible_teacher": "刘老师",
            }
        )
        case_id = repositories.create_replanning_case(owner_id, replanning_data())

    assert client.get(f"/students/{other_id}/replanning/{case_id}").status_code == 404
    response = client.post(
        f"/students/{owner_id}/replanning/{case_id}/status",
        data={"status": "非法状态"},
    )
    assert response.status_code == 400
