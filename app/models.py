from dataclasses import dataclass


@dataclass(frozen=True)
class Student:
    id: int
    name: str
    gender: str
    enrollment_year: int
    current_term: str
    school: str
    college: str
    major: str
    city: str
    phone: str
    service_stage: str
    responsible_teacher: str


@dataclass(frozen=True)
class ParentContact:
    id: int
    student_id: int
    name: str
    relationship: str
    phone: str
    communication_method: str
    is_primary_decision_maker: bool
    questionnaire_status: str
