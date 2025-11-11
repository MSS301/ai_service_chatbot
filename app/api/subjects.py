from fastapi import APIRouter, HTTPException, Path, Depends
from typing import List
from app.models.crud_model import (
    SubjectCreateRequest, SubjectUpdateRequest, SubjectResponse, GradeSubjectLinkRequest
)
from app.repositories.subject_repository import SubjectRepository, GradeSubjectRepository
from app.repositories.grade_repository import GradeRepository
from app.core.auth import get_current_user, UserInfo
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

@router.post("", response_model=SubjectResponse, status_code=201)
def create_subject(req: SubjectCreateRequest, user: UserInfo = Depends(get_current_user)):
    repo = SubjectRepository()
    repo.create_indexes()
    subject_id = repo.compute_subject_id(req.subject_code)
    existing = repo.get_subject_by_id(subject_id)
    if existing:
        raise HTTPException(status_code=400, detail=f"Subject '{req.subject_code}' already exists")
    repo.upsert_subject(subject_id, req.subject_code, req.subject_name)
    subj = repo.get_subject_by_id(subject_id)
    subj["created_at"] = str(subj.get("created_at")) if subj.get("created_at") else None
    subj["updated_at"] = str(subj.get("updated_at")) if subj.get("updated_at") else None
    return subj

@router.get("", response_model=List[SubjectResponse])
def list_subjects(user: UserInfo = Depends(get_current_user)):
    repo = SubjectRepository()
    return repo.get_all_subjects()

@router.get("/{subject_id}", response_model=SubjectResponse)
def get_subject(subject_id: str = Path(..., description="Subject ID"), user: UserInfo = Depends(get_current_user)):
    repo = SubjectRepository()
    subj = repo.get_subject_by_id(subject_id)
    if not subj:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")
    subj["created_at"] = str(subj.get("created_at")) if subj.get("created_at") else None
    subj["updated_at"] = str(subj.get("updated_at")) if subj.get("updated_at") else None
    return subj

@router.patch("/{subject_id}", response_model=SubjectResponse)
def update_subject(subject_id: str, req: SubjectUpdateRequest, user: UserInfo = Depends(get_current_user)):
    repo = SubjectRepository()
    if not repo.get_subject_by_id(subject_id):
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")
    updated = repo.update_subject(subject_id, req.subject_code, req.subject_name)
    if not updated:
        raise HTTPException(status_code=400, detail="No fields to update or update failed")
    subj = repo.get_subject_by_id(subject_id)
    subj["created_at"] = str(subj.get("created_at")) if subj.get("created_at") else None
    subj["updated_at"] = str(subj.get("updated_at")) if subj.get("updated_at") else None
    return subj

@router.delete("/{subject_id}")
def delete_subject(subject_id: str, user: UserInfo = Depends(get_current_user)):
    repo = SubjectRepository()
    if not repo.delete_subject(subject_id):
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found or not deleted")
    # Also unlink from grade-subject mapping
    gs = GradeSubjectRepository()
    gs.collection.delete_many({"subject_id": subject_id})
    return {"success": True}

# Grade-Subject linkage
@router.post("/link", status_code=204)
def link_grade_subject(req: GradeSubjectLinkRequest, user: UserInfo = Depends(get_current_user)):
    gs = GradeSubjectRepository()
    gs.create_indexes()
    # Validate grade and subject exist
    grade_repo = GradeRepository()
    if not grade_repo.get_grade_by_id(req.grade_id):
        raise HTTPException(status_code=404, detail=f"Grade '{req.grade_id}' not found")
    subj_repo = SubjectRepository()
    if not subj_repo.get_subject_by_id(req.subject_id):
        raise HTTPException(status_code=404, detail=f"Subject '{req.subject_id}' not found")
    if not gs.link(req.grade_id, req.subject_id):
        raise HTTPException(status_code=500, detail="Failed to link grade and subject")

@router.post("/unlink", status_code=204)
def unlink_grade_subject(req: GradeSubjectLinkRequest, user: UserInfo = Depends(get_current_user)):
    gs = GradeSubjectRepository()
    if not gs.unlink(req.grade_id, req.subject_id):
        raise HTTPException(status_code=404, detail="Link not found")

@router.get("/by-grade/{grade_id}")
def get_subjects_by_grade(grade_id: str, user: UserInfo = Depends(get_current_user)):
    gs = GradeSubjectRepository()
    subj_ids = gs.get_subjects_by_grade(grade_id)
    subj_repo = SubjectRepository()
    subjects = [subj_repo.get_subject_by_id(sid) for sid in subj_ids]
    return {"grade_id": grade_id, "subjects": [s for s in subjects if s]}

@router.get("/by-subject/{subject_id}")
def get_grades_by_subject(subject_id: str, user: UserInfo = Depends(get_current_user)):
    gs = GradeSubjectRepository()
    grade_ids = gs.get_grades_by_subject(subject_id)
    from app.repositories.grade_repository import GradeRepository
    grade_repo = GradeRepository()
    grades = [grade_repo.get_grade_by_id(gid) for gid in grade_ids]
    return {"subject_id": subject_id, "grades": [g for g in grades if g]}


