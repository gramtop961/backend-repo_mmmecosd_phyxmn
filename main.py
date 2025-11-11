import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId
from datetime import datetime

from database import db, create_document, get_documents
from schemas import Task

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Todo API running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response

# Helpers
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[str] = None
    completed: Optional[bool] = None

# CRUD Endpoints
@app.post("/api/tasks", response_model=dict)
def create_task(payload: TaskCreate):
    try:
        task = Task(**payload.model_dump(), completed=False)
        inserted_id = create_document("task", task)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks", response_model=List[dict])
def list_tasks(category: Optional[str] = None, q: Optional[str] = None):
    try:
        filter_dict = {}
        if category:
            filter_dict["category"] = category
        if q:
            filter_dict["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"description": {"$regex": q, "$options": "i"}},
            ]
        docs = get_documents("task", filter_dict)
        # Convert ObjectId to string
        for d in docs:
            d["id"] = str(d.pop("_id"))
            if "created_at" in d and isinstance(d["created_at"], datetime):
                d["created_at"] = d["created_at"].isoformat()
            if "updated_at" in d and isinstance(d["updated_at"], datetime):
                d["updated_at"] = d["updated_at"].isoformat()
            if "due_date" in d and isinstance(d["due_date"], datetime):
                d["due_date"] = d["due_date"].isoformat()
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/tasks/{task_id}", response_model=dict)
def update_task(task_id: str, payload: TaskUpdate):
    try:
        if db is None:
            raise Exception("Database not available")
        data = {k: v for k, v in payload.model_dump().items() if v is not None}
        data["updated_at"] = datetime.utcnow()
        result = db["task"].find_one_and_update(
            {"_id": ObjectId(task_id)},
            {"$set": data},
            return_document=True
        )
        if not result:
            raise HTTPException(status_code=404, detail="Task not found")
        result["id"] = str(result.pop("_id"))
        if "created_at" in result and isinstance(result["created_at"], datetime):
            result["created_at"] = result["created_at"].isoformat()
        if "updated_at" in result and isinstance(result["updated_at"], datetime):
            result["updated_at"] = result["updated_at"].isoformat()
        if "due_date" in result and isinstance(result["due_date"], datetime):
            result["due_date"] = result["due_date"].isoformat()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/tasks/{task_id}", response_model=dict)
def delete_task(task_id: str):
    try:
        if db is None:
            raise Exception("Database not available")
        res = db["task"].delete_one({"_id": ObjectId(task_id)})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
