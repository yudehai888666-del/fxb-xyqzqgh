from io import BytesIO

from app import repositories


def create_sample_student():
    return repositories.create_student(
        {
            "name": "李同学",
            "gender": "男",
            "enrollment_year": "2026",
            "current_term": "大一上",
            "school": "示例大学",
            "college": "计算机学院",
            "major": "软件工程",
            "city": "杭州",
            "phone": "13800000006",
        }
    )


def test_material_upload_records_file(client, app):
    with app.app_context():
        student_id = create_sample_student()

    response = client.post(
        f"/students/{student_id}/materials",
        data={
            "action": "upload",
            "uploader_type": "老师",
            "category": "成绩单",
            "material": (BytesIO(b"score details"), "score.txt"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        materials = repositories.list_materials(student_id)

    assert len(materials) == 1
    assert materials[0]["original_filename"] == "score.txt"


def test_material_upload_accepts_chinese_filename(client, app):
    with app.app_context():
        student_id = create_sample_student()

    response = client.post(
        f"/students/{student_id}/materials",
        data={
            "action": "upload",
            "uploader_type": "学生",
            "category": "成绩单",
            "material": (BytesIO(b"pdf details"), "成绩单.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        materials = repositories.list_materials(student_id)

    assert len(materials) == 1
    assert materials[0]["original_filename"] == "成绩单.pdf"
    assert materials[0]["stored_filename"].endswith(".pdf")


def test_successful_material_upload_redirects_to_materials_page(client, app):
    with app.app_context():
        student_id = create_sample_student()

    response = client.post(
        f"/students/{student_id}/materials",
        data={
            "action": "upload",
            "uploader_type": "老师",
            "category": "成绩单",
            "material": (BytesIO(b"score details"), "score.txt"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"] == f"/students/{student_id}/materials"


def test_disclaimer_confirmation_records_reason(client, app):
    with app.app_context():
        student_id = create_sample_student()

    client.post(
        f"/students/{student_id}/materials",
        data={
            "action": "disclaimer",
            "signer_type": "家长",
            "signer_name": "李女士",
            "reason": "当前材料暂缺，先基于已填写信息生成规划。",
        },
    )

    with app.app_context():
        disclaimers = repositories.list_disclaimers(student_id)

    assert len(disclaimers) == 1
    assert disclaimers[0]["signer_name"] == "李女士"


def test_blank_disclaimer_returns_error_without_record(client, app):
    with app.app_context():
        student_id = create_sample_student()

    response = client.post(
        f"/students/{student_id}/materials",
        data={
            "action": "disclaimer",
            "signer_type": "   ",
            "signer_name": " \t ",
            "reason": "",
        },
    )

    assert response.status_code == 400
    assert "免责确认信息不能为空" in response.get_data(as_text=True)
    with app.app_context():
        disclaimers = repositories.list_disclaimers(student_id)

    assert disclaimers == []


def test_unsupported_material_suffix_returns_error_without_record(client, app):
    with app.app_context():
        student_id = create_sample_student()

    response = client.post(
        f"/students/{student_id}/materials",
        data={
            "action": "upload",
            "uploader_type": "老师",
            "category": "成绩单",
            "material": (BytesIO(b"bad"), "score.exe"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert "不支持的文件类型" in response.get_data(as_text=True)
    with app.app_context():
        materials = repositories.list_materials(student_id)

    assert materials == []
