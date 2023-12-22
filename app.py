from fastapi import FastAPI, Request, Depends, Form, HTTPException, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy import create_engine, Column, Integer, String, Date, Boolean, func, DateTime, ForeignKey, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship, joinedload
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date, datetime
import uvicorn

# Database configuration
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://admin:shapementor@shapementor-rds.cuorsbapmndf.us-east-2.rds.amazonaws.com/Discussion"


engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Discussion(Base):
    __tablename__ = 'discussions'

    discussion_id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255))
    content = Column(Text)
    email = Column(String(255))
    timestamp = Column(DateTime, default=func.current_timestamp())

class DiscussionCreate(BaseModel):
    title: str
    content: str
    email: str

# Model for updating an existing discussion (UpdateModel)
class DiscussionUpdate(BaseModel):
    discussion_id: int
    title: Optional[str] = None
    content: Optional[str] = None
    email: Optional[str] = None
    timestamp: datetime

# Model for response (ResponseModel)
class DiscussionResponse(BaseModel):
    discussion_id: int
    title: str
    content: str
    email: int
    timestamp: datetime

    class Config:
        orm_mode = True
# SQLAlchemy User model
# class User(Base):
#     __tablename__ = 'users'
#     user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
#     hashed_password = Column(String(255), nullable=False)
#     activated = Column(Boolean, nullable=False)
#     user_name = Column(String(255))
#     dob = Column(Date)
#     gender = Column(String(50))
#     race = Column(String(50))
#     email = Column(String(255), nullable=False)
#     phone_number = Column(String(20))
#     body_metrics = relationship("BodyMetrics", back_populates="user")
#
# class UserCreateModel(BaseModel):
#     user_id: int
#     user_name: str
#     dob: Optional[date]
#     gender: Optional[str]
#     race: Optional[str]
#     email: str
#     phone_number: Optional[str]
#     class Config:
#         orm_mode = True
#
# class UserUpdateModel(BaseModel):
#     user_id: int
#     user_name: str
#     dob: Optional[date]
#     gender: Optional[str]
#     race: Optional[str]
#     email: str
#     phone_number: Optional[str]
#     class Config:
#         orm_mode = True
#
# class UserResponseModel(BaseModel):
#     user_id: int
#     user_name: str
#     dob: Optional[date]
#     gender: Optional[str]
#     race: Optional[str]
#     email: str
#     phone_number: Optional[str]
#     class Config:
#         orm_mode = True



app = FastAPI()
templates = Jinja2Templates(directory="templates")


@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    response = Response("Internal server error", status_code=500)
    try:
        request.state.db = SessionLocal()
        print("request middleware!")
        response = await call_next(request)
    finally:
        request.state.db.close()
        print("close middleware!")
    return response

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def hello():
    return "DISCUSSION BOARD"
@app.get("/discussions/all")
def get_all_discussions(db: Session = Depends(get_db)):
    all_discussions = db.query(Discussion).all()
    return all_discussions

@app.get("/discussions/{email}/mydiscussions")
def get_my_discussions(email:str, db: Session = Depends(get_db)):
    my_discussions = db.query(Discussion).filter(Discussion.email == email).all()
    return my_discussions

@app.get("/discussions/{email}")
def get_email(email: str):
    global current_email
    current_email = email
    return RedirectResponse(url=f"/discussions", status_code=303)
@app.get("/discussions")
def get_discussions(request: Request, db: Session = Depends(get_db)):
    all_discussions = db.query(Discussion).all()
    discussions = []
    for discussion in all_discussions:
        discussions.append({
            "discussion_id": discussion.discussion_id,
            "title": discussion.title,
            "content": discussion.content,
            "email": discussion.email,
            "timestamp": discussion.timestamp
        })
    email = current_email
    return templates.TemplateResponse("discussion_board.html", {
        "request": request,
        "discussions": discussions,
        "email": email
    })

@app.post("/discussions/{email}/post")
def post_disscussion(email: str,
                     title: str = Form(...),
                     content: str = Form(...),
                     db: Session = Depends(get_db)):
    max_id = db.query(func.max(Discussion.discussion_id)).scalar()
    next_id = (max_id or 0) + 1
    new_discussion = Discussion(
        discussion_id = next_id,
        title=title,
        content=content,
        email=current_email
    )
    db.add(new_discussion)
    db.commit()
    db.refresh(new_discussion)
    print("added")
    return RedirectResponse(url=f"/discussions/{email}", status_code=303)

@app.post("/discussions/{email}/request_delete")
def request_delete(email:str, discussion_id:int = Form(...), db: Session = Depends(get_db)):
    delete_discussion(discussion_id, db)
    return RedirectResponse(url=f"/discussions/{email}", status_code=303)


@app.delete("/discussions/{email}/delete/{discussion_id}")
def delete_discussion(discussion_id:int, db: Session = Depends(get_db)):
    delete_record = db.query(Discussion).filter(
        Discussion.discussion_id == discussion_id
    ).first()

    if not delete_record:
        raise HTTPException(status_code=404, detail="Discussion not found, fail to delete.")

    db.delete(delete_record)
    db.commit()
    print("deleted")
    return "deleted"

@app.post("/discussions/{email}/request_edit")
def request_edit(email:str,
                 discussion_id:int = Form(...),
                 new_title: str = Form(...),
                 new_content:str = Form(...),
                 db: Session = Depends(get_db)):
    goal = DiscussionUpdate(
        discussion_id = discussion_id,
        title = new_title,
        content = new_content,
        email = email,
        timestamp = datetime.now()
    )
    edit_discussion(goal, db)

    return RedirectResponse(url=f"/discussions/{email}", status_code=303)


@app.put("/discussions/{email}/edit/{discussion_id}")
def edit_discussion(edit_discussion:DiscussionUpdate, db: Session = Depends(get_db)):
    target_discussion = db.query(Discussion).filter(
        Discussion.discussion_id == edit_discussion.discussion_id
    ).first()

    if not target_discussion:
        raise HTTPException(status_code=404, detail="Target discussion not found")
    for key, value in edit_discussion.dict(exclude_unset=True).items():
        setattr(target_discussion, key, value)
    db.commit()
    db.refresh(target_discussion)
    print("updated!")

    return "updated"


if __name__ == "__main__":
    # uvicorn.run(app, host="localhost", port=8013)
    uvicorn.run(app, host="0.0.0.0", port=8013)