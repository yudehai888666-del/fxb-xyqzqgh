from app import repositories


def create_student():
    return repositories.create_student({"name":"版本同学","gender":"女","enrollment_year":2026,"current_term":"大一上","school":"示例大学","major":"法学"})


def test_edit_creates_new_version_without_overwriting(client, app):
    with app.app_context():
        sid=create_student(); first=repositories.create_planning_document(sid,{"title":"初步规划","content_markdown":"# V1\n原内容"})
    response=client.post(f"/students/{sid}/planning/documents/{first}/edit",data={"title":"初步规划","content_markdown":"# V2\n新内容"})
    assert response.status_code==302
    with app.app_context():
        docs=repositories.list_planning_documents(sid)
        assert len(docs)==2
        assert repositories.get_planning_document(first)["content_markdown"]=="# V1\n原内容"
        assert docs[0]["version"]==2


def test_confirm_and_export_word_pdf_to_archive(client, app):
    with app.app_context():
        sid=create_student(); doc_id=repositories.create_planning_document(sid,{"title":"规划书","content_markdown":"# 诊断\n\n学业基础良好。\n\n## 行动\n- 完成英语学习"})
    assert client.post(f"/students/{sid}/planning/documents/{doc_id}/confirm").status_code==302
    assert client.post(f"/students/{sid}/planning/documents/{doc_id}/export/docx").status_code==302
    assert client.post(f"/students/{sid}/planning/documents/{doc_id}/export/pdf").status_code==302
    with app.app_context():
        assert repositories.get_planning_document(doc_id)["status"]=="已确认"
        files=repositories.list_student_files(sid)
        assert {f["source_type"] for f in files}=={"planning_export_docx","planning_export_pdf"}
        for f in files:
            assert (app.config["GENERATED_DIR"] / f["storage_key"]).exists()
