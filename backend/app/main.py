from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import db

# Create FastAPI app instance
app = FastAPI()

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/pairs")
def get_pairs():
    """
    GET endpoint that returns all documents from the MongoDB collection 'pair_stats'.
    Excludes MongoDB's _id field and returns data in the expected format.
    """
    # Fetch all documents from pair_stats collection
    pairs_cursor = db.pair_stats.find({})
    
    # Convert to list and exclude _id field
    pairs_list = []
    for doc in pairs_cursor:
        # Create a new dict without _id
        pair_doc = {
            "A": doc.get("A"),
            "B": doc.get("B"),
            "lift": doc.get("lift"),
            "phi": doc.get("phi"),
            "n": doc.get("n"),
        }
        pairs_list.append(pair_doc)
    
    return {"pairs": pairs_list}
