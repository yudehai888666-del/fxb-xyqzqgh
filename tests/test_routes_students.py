def test_student_list_loads(client):
    response = client.get("/students")

    assert response.status_code == 200
    assert "学生档案".encode("utf-8") in response.data


def test_create_student_redirects_to_detail(client):
    response = client.post(
        "/students/new",
        data={
            "name": "李明",
            "gender": "男",
            "enrollment_year": "2024",
            "current_term": "大一上",
            "school": "第一中学",
            "college": "工学院",
            "major": "计算机科学",
            "city": "上海",
            "phone": "13800000000",
            "responsible_teacher": "张老师",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "李明".encode("utf-8") in response.data
    assert "家长联系人".encode("utf-8") in response.data


def test_create_student_rejects_invalid_enrollment_year(client):
    response = client.post(
        "/students/new",
        data={
            "name": "王芳",
            "gender": "女",
            "enrollment_year": "abc",
            "current_term": "大二下",
            "school": "第二中学",
            "college": "商学院",
            "major": "工商管理",
            "city": "北京",
            "phone": "13900000000",
            "responsible_teacher": "刘老师",
        },
    )

    assert response.status_code == 400
    assert "入学年份必须是有效年份".encode("utf-8") in response.data
    assert "王芳".encode("utf-8") in response.data
