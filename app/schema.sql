PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    gender TEXT NOT NULL,
    enrollment_year INTEGER NOT NULL,
    current_term TEXT NOT NULL,
    school TEXT NOT NULL,
    college TEXT NOT NULL DEFAULT '',
    major TEXT NOT NULL,
    city TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    service_stage TEXT NOT NULL DEFAULT '信息收集',
    responsible_teacher TEXT NOT NULL DEFAULT '本人',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parent_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    relationship TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    communication_method TEXT NOT NULL DEFAULT '',
    is_primary_decision_maker INTEGER NOT NULL DEFAULT 1,
    questionnaire_status TEXT NOT NULL DEFAULT '未填写',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, id)
);

CREATE TABLE IF NOT EXISTS student_questionnaires (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL UNIQUE REFERENCES students(id) ON DELETE CASCADE,
    adaptation_status TEXT NOT NULL DEFAULT '',
    academic_status TEXT NOT NULL DEFAULT '',
    weak_subjects TEXT NOT NULL DEFAULT '',
    tutoring_needs TEXT NOT NULL DEFAULT '',
    interests_strengths TEXT NOT NULL DEFAULT '',
    future_intentions TEXT NOT NULL DEFAULT '',
    motivation_status TEXT NOT NULL DEFAULT '',
    submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parent_questionnaires (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    parent_contact_id INTEGER NOT NULL UNIQUE REFERENCES parent_contacts(id) ON DELETE CASCADE,
    family_resources TEXT NOT NULL DEFAULT '',
    target_priorities TEXT NOT NULL DEFAULT '',
    parent_observations TEXT NOT NULL DEFAULT '',
    current_concerns TEXT NOT NULL DEFAULT '',
    investment_willingness TEXT NOT NULL DEFAULT '',
    submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id, parent_contact_id)
        REFERENCES parent_contacts(student_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS planning_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT '草稿',
    content_markdown TEXT NOT NULL,
    file_path TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    uploader_type TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '其他材料',
    uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS disclaimers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    signer_type TEXT NOT NULL,
    signer_name TEXT NOT NULL,
    reason TEXT NOT NULL,
    confirmed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS teacher_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL UNIQUE REFERENCES students(id) ON DELETE CASCADE,
    source_channel TEXT NOT NULL DEFAULT '',
    consultation_stage TEXT NOT NULL DEFAULT '',
    core_request TEXT NOT NULL DEFAULT '',
    family_student_conflict TEXT NOT NULL DEFAULT '',
    resource_match_level TEXT NOT NULL DEFAULT '',
    goal_feasibility TEXT NOT NULL DEFAULT '',
    execution_risk TEXT NOT NULL DEFAULT '',
    academic_risk TEXT NOT NULL DEFAULT '',
    transfer_feasibility TEXT NOT NULL DEFAULT '',
    service_suggestions TEXT NOT NULL DEFAULT '',
    ai_generation_focus TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
