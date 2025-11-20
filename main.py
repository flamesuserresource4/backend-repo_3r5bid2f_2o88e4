import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Utilities
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

def serialize_doc(doc: dict):
    if not doc:
        return doc
    doc = dict(doc)
    if doc.get("_id"):
        doc["id"] = str(doc.pop("_id"))
    # Convert any nested ObjectIds just in case
    for k, v in list(doc.items()):
        if isinstance(v, ObjectId):
            doc[k] = str(v)
    return doc


# Schemas
class ProductIn(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    image: Optional[str] = Field(None, description="Image URL")
    in_stock: bool = Field(True, description="Whether product is in stock")

class Product(ProductIn):
    id: str


@app.get("/")
def read_root():
    return {"message": "Clothing Store Backend Running"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

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
            response["database_url"] = "✅ Configured"
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


# Product Endpoints
@app.get("/api/products", response_model=List[Product])
def list_products(category: Optional[str] = None, q: Optional[str] = None):
    """List products with optional category and search query"""
    filter_dict = {}
    if category:
        filter_dict["category"] = category
    if q:
        filter_dict["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"category": {"$regex": q, "$options": "i"}},
        ]
    docs = get_documents("product", filter_dict)
    return [Product(**serialize_doc(d)) for d in docs]

@app.get("/api/products/{product_id}", response_model=Product)
def get_product(product_id: str):
    try:
        _id = ObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product id")
    doc = db["product"].find_one({"_id": _id})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return Product(**serialize_doc(doc))

@app.post("/api/products", response_model=str)
def create_product(product: ProductIn):
    new_id = create_document("product", product.dict())
    return new_id

@app.get("/api/categories", response_model=List[str])
def list_categories():
    categories = db["product"].distinct("category") if db else []
    return sorted([c for c in categories if c])


# Seed sample products on first run
@app.on_event("startup")
def seed_products():
    if db is None:
        return
    count = db["product"].count_documents({})
    if count > 0:
        return
    samples = [
        {
            "title": "Classic White Tee",
            "description": "Soft cotton crew neck tee. A wardrobe essential.",
            "price": 19.99,
            "category": "Tops",
            "image": "https://images.unsplash.com/photo-1523381294911-8d3cead13475?q=80&w=1200&auto=format&fit=crop",
            "in_stock": True,
        },
        {
            "title": "Slim Fit Jeans",
            "description": "Mid-wash denim with a tapered leg.",
            "price": 49.0,
            "category": "Bottoms",
            "image": "https://images.unsplash.com/photo-1516826957135-700dedea698c?q=80&w=1200&auto=format&fit=crop",
            "in_stock": True,
        },
        {
            "title": "Oversized Hoodie",
            "description": "Cozy fleece-lined hoodie for everyday comfort.",
            "price": 59.0,
            "category": "Outerwear",
            "image": "https://images.unsplash.com/photo-1520975916090-3105956dac38?q=80&w=1200&auto=format&fit=crop",
            "in_stock": True,
        },
        {
            "title": "Linen Shirt",
            "description": "Breathable linen for warmer days.",
            "price": 39.0,
            "category": "Tops",
            "image": "https://images.unsplash.com/photo-1520975916090-95f9db8b27a9?q=80&w=1200&auto=format&fit=crop",
            "in_stock": True,
        },
        {
            "title": "Chino Shorts",
            "description": "Tailored fit shorts with stretch.",
            "price": 29.0,
            "category": "Bottoms",
            "image": "https://images.unsplash.com/photo-1520975916090-1a49f6b0b9d9?q=80&w=1200&auto=format&fit=crop",
            "in_stock": True,
        },
    ]
    for p in samples:
        try:
            create_document("product", p)
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
