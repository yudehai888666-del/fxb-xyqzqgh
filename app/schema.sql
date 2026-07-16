PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'teacher', 'collaborator')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TEXT
);

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

CREATE TABLE IF NOT EXISTS student_access (
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    access_level TEXT NOT NULL DEFAULT '编辑' CHECK(access_level IN ('查看', '编辑')),
    assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(student_id, user_id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL DEFAULT '',
    target_id INTEGER,
    details TEXT NOT NULL DEFAULT '',
    ip_address TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at DESC);

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
    version INTEGER NOT NULL DEFAULT 1,
    visibility TEXT NOT NULL DEFAULT '老师内部',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    uploader_type TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '其他材料',
    visibility TEXT NOT NULL DEFAULT '老师内部',
    uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS student_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    storage_area TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    mime_type TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    visibility TEXT NOT NULL DEFAULT '老师内部',
    is_current INTEGER NOT NULL DEFAULT 1,
    deleted_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_type, source_id)
);

CREATE INDEX IF NOT EXISTS idx_student_files_student
ON student_files(student_id, deleted_at, created_at);

CREATE TABLE IF NOT EXISTS questionnaire_invitations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    questionnaire_type TEXT NOT NULL CHECK(questionnaire_type IN ('student', 'parent')),
    token TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT '有效',
    expires_at TEXT NOT NULL,
    opened_at TEXT,
    submitted_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_questionnaire_invitations_student
ON questionnaire_invitations(student_id, questionnaire_type, created_at);

CREATE TABLE IF NOT EXISTS questionnaire_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    invitation_id INTEGER REFERENCES questionnaire_invitations(id) ON DELETE SET NULL,
    questionnaire_type TEXT NOT NULL CHECK(questionnaire_type IN ('student', 'parent')),
    answers_json TEXT NOT NULL,
    submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_questionnaire_submissions_student
ON questionnaire_submissions(student_id, questionnaire_type, submitted_at);

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
    combined_notes TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS replanning_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    original_goal TEXT NOT NULL DEFAULT '',
    trigger_event TEXT NOT NULL DEFAULT '',
    trigger_reason TEXT NOT NULL DEFAULT '',
    responsibility_type TEXT NOT NULL DEFAULT '',
    new_primary_goal TEXT NOT NULL DEFAULT '',
    new_secondary_goal TEXT NOT NULL DEFAULT '',
    new_third_goal TEXT NOT NULL DEFAULT '',
    original_service_scope TEXT NOT NULL DEFAULT '',
    completed_work TEXT NOT NULL DEFAULT '',
    new_service_scope TEXT NOT NULL DEFAULT '',
    fee_adjustment_type TEXT NOT NULL DEFAULT '',
    additional_fee TEXT NOT NULL DEFAULT '',
    refund_or_credit TEXT NOT NULL DEFAULT '',
    fee_notes TEXT NOT NULL DEFAULT '',
    agreement_terms TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '草稿',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);

CREATE TABLE IF NOT EXISTS student_goal_profiles (
    student_id INTEGER PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
    primary_goal TEXT NOT NULL CHECK(primary_goal IN ('升学', '就业')),
    alternate_goal TEXT NOT NULL DEFAULT '' CHECK(alternate_goal IN ('', '升学', '就业')),
    decision_reason TEXT NOT NULL,
    confirmed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    confirmed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(alternate_goal = '' OR alternate_goal != primary_goal)
);

CREATE TABLE IF NOT EXISTS student_goal_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    change_type TEXT NOT NULL CHECK(change_type IN ('首次确认', '目标变更')),
    from_primary_goal TEXT NOT NULL DEFAULT '',
    to_primary_goal TEXT NOT NULL CHECK(to_primary_goal IN ('升学', '就业')),
    from_alternate_goal TEXT NOT NULL DEFAULT '',
    to_alternate_goal TEXT NOT NULL DEFAULT '',
    change_reason TEXT NOT NULL,
    replanning_id INTEGER REFERENCES replanning_cases(id) ON DELETE RESTRICT,
    changed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_student_goal_changes_student
ON student_goal_changes(student_id, changed_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS knowledge_majors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    discipline_category TEXT NOT NULL DEFAULT '',
    degree_level TEXT NOT NULL DEFAULT '本科',
    description TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    source_name TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '草稿' CHECK(status IN ('草稿', '待审核', '已发布', '已退回')),
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    industry_name TEXT NOT NULL DEFAULT '',
    job_family TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    development_direction TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    source_name TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '草稿' CHECK(status IN ('草稿', '待审核', '已发布', '已退回')),
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    skill_type TEXT NOT NULL DEFAULT '专业技能',
    description TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    source_name TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '草稿' CHECK(status IN ('草稿', '待审核', '已发布', '已退回')),
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS major_job_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    major_id INTEGER NOT NULL REFERENCES knowledge_majors(id) ON DELETE CASCADE,
    job_id INTEGER NOT NULL REFERENCES knowledge_jobs(id) ON DELETE CASCADE,
    relevance_level TEXT NOT NULL DEFAULT '相关',
    evidence_note TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(major_id, job_id)
);

CREATE TABLE IF NOT EXISTS job_skill_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES knowledge_jobs(id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES knowledge_skills(id) ON DELETE CASCADE,
    importance_level TEXT NOT NULL DEFAULT '核心',
    proficiency_level TEXT NOT NULL DEFAULT '掌握',
    evidence_note TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    source_id INTEGER REFERENCES intelligence_sources(id) ON DELETE SET NULL,
    confidence_level TEXT NOT NULL DEFAULT '' CHECK(confidence_level IN ('', '低', '中', '高')),
    sample_size INTEGER NOT NULL DEFAULT 0 CHECK(sample_size >= 0),
    last_verified_at TEXT NOT NULL DEFAULT '',
    next_check_at TEXT NOT NULL DEFAULT '',
    owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reviewer_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT '草稿' CHECK(status IN ('草稿', '待审核', '已发布', '已退回', '已过期')),
    limitation_note TEXT NOT NULL DEFAULT '',
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_id, skill_id)
);

CREATE TABLE IF NOT EXISTS exam_information (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    region TEXT NOT NULL DEFAULT '全国',
    official_url TEXT NOT NULL DEFAULT '',
    source_name TEXT NOT NULL DEFAULT '',
    registration_start TEXT NOT NULL DEFAULT '',
    registration_end TEXT NOT NULL DEFAULT '',
    exam_date TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    collector_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reviewer_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    execution_owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    next_check_at TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '草稿' CHECK(status IN ('草稿', '待审核', '已发布', '已退回', '已过期')),
    version INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_exam_information_status_check
ON exam_information(status, next_check_at);

CREATE TABLE IF NOT EXISTS exam_information_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_information_id INTEGER NOT NULL REFERENCES exam_information(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    change_summary TEXT NOT NULL DEFAULT '',
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exam_information_id, version)
);

CREATE TABLE IF NOT EXISTS industries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL DEFAULT '',
    scope TEXT NOT NULL DEFAULT '全国',
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '草稿' CHECK(status IN ('草稿', '待审核', '已发布', '已退回')),
    owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reviewer_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS intelligence_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    source_kind TEXT NOT NULL DEFAULT '政府与公共机构',
    collection_mode TEXT NOT NULL DEFAULT '公开网页',
    update_frequency TEXT NOT NULL DEFAULT '每月',
    owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reviewer_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    compliance_note TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    last_fetch_at TEXT,
    last_content_hash TEXT NOT NULL DEFAULT '',
    last_change_status TEXT NOT NULL DEFAULT '未采集',
    last_error TEXT NOT NULL DEFAULT '',
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS intelligence_source_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES intelligence_sources(id) ON DELETE CASCADE,
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    http_status INTEGER,
    content_hash TEXT NOT NULL DEFAULT '',
    page_title TEXT NOT NULL DEFAULT '',
    content_excerpt TEXT NOT NULL DEFAULT '',
    content_bytes INTEGER NOT NULL DEFAULT 0,
    is_changed INTEGER NOT NULL DEFAULT 0,
    error_message TEXT NOT NULL DEFAULT '',
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_source_snapshots_source
ON intelligence_source_snapshots(source_id, fetched_at DESC);

CREATE TABLE IF NOT EXISTS employment_market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES knowledge_jobs(id) ON DELETE CASCADE,
    region TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    observed_posting_count INTEGER NOT NULL CHECK(observed_posting_count >= 0),
    sample_size INTEGER NOT NULL CHECK(sample_size >= 0),
    salary_min INTEGER,
    salary_median INTEGER,
    salary_max INTEGER,
    currency TEXT NOT NULL DEFAULT 'CNY',
    salary_period TEXT NOT NULL DEFAULT '月',
    source_id INTEGER NOT NULL REFERENCES intelligence_sources(id) ON DELETE RESTRICT,
    source_snapshot_id INTEGER REFERENCES intelligence_source_snapshots(id) ON DELETE SET NULL,
    evidence_summary TEXT NOT NULL,
    limitation_note TEXT NOT NULL,
    data_classification TEXT NOT NULL DEFAULT '测试数据' CHECK(data_classification IN ('测试数据', '真实数据')),
    owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    reviewer_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT '草稿' CHECK(status IN ('草稿', '待审核', '已发布', '已退回', '已过期')),
    next_check_at TEXT NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS employment_market_breakdowns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES employment_market_snapshots(id) ON DELETE CASCADE,
    dimension_type TEXT NOT NULL CHECK(dimension_type IN ('学历', '经验', '热门技能', '地区')),
    label TEXT NOT NULL,
    value REAL NOT NULL CHECK(value >= 0),
    unit TEXT NOT NULL DEFAULT '%',
    sample_size INTEGER NOT NULL DEFAULT 0 CHECK(sample_size >= 0),
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(snapshot_id, dimension_type, label)
);

CREATE INDEX IF NOT EXISTS idx_market_snapshot_job_status
ON employment_market_snapshots(job_id, status, period_end DESC);

CREATE TABLE IF NOT EXISTS industry_trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    industry_id INTEGER NOT NULL REFERENCES industries(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    trend_type TEXT NOT NULL DEFAULT '产业方向',
    region TEXT NOT NULL DEFAULT '全国',
    direction_summary TEXT NOT NULL DEFAULT '',
    employment_impact TEXT NOT NULL DEFAULT '',
    affected_jobs TEXT NOT NULL DEFAULT '',
    affected_majors TEXT NOT NULL DEFAULT '',
    evidence_summary TEXT NOT NULL DEFAULT '',
    source_id INTEGER REFERENCES intelligence_sources(id) ON DELETE SET NULL,
    source_url TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL DEFAULT '',
    next_check_at TEXT NOT NULL DEFAULT '',
    owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reviewer_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT '草稿' CHECK(status IN ('草稿', '待审核', '已发布', '已退回', '已过期')),
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_industry_trends_status_check
ON industry_trends(status, next_check_at);

CREATE TABLE IF NOT EXISTS student_job_targets (
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    job_id INTEGER NOT NULL REFERENCES knowledge_jobs(id) ON DELETE CASCADE,
    priority INTEGER NOT NULL DEFAULT 1 CHECK(priority BETWEEN 1 AND 3),
    target_note TEXT NOT NULL DEFAULT '',
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(student_id, job_id)
);

CREATE TABLE IF NOT EXISTS student_skill_assessments (
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES knowledge_skills(id) ON DELETE CASCADE,
    current_level INTEGER NOT NULL DEFAULT 0 CHECK(current_level BETWEEN 0 AND 4),
    evidence_note TEXT NOT NULL DEFAULT '',
    assessed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    assessed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(student_id, skill_id)
);

CREATE TABLE IF NOT EXISTS student_exam_plans (
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    exam_id INTEGER NOT NULL REFERENCES exam_information(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL DEFAULT '',
    priority INTEGER NOT NULL DEFAULT 1 CHECK(priority BETWEEN 1 AND 3),
    preparation_status TEXT NOT NULL DEFAULT '未开始',
    personal_deadline TEXT NOT NULL DEFAULT '',
    next_action TEXT NOT NULL DEFAULT '',
    owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(student_id, exam_id)
);
