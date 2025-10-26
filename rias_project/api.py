import uvicorn
import shutil
import os
from pathlib import Path

# --- FastAPI Imports ---
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles # Import this

# --- Your Pipeline Import ---
try:
    import main as pipeline_logic
except ImportError as e:
    print(f"Error: Could not import 'main.py'. Make sure 'api.py' is in the same directory.")
    print(f"Details: {e}")
    exit(1)

# ----------------------------------------------------------------------
#  API CONFIGURATION
# ----------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_ROOT = PROJECT_ROOT / "results"
RAW_PDF_DIR = PROJECT_ROOT / "data" / "raw_pdfs"
RAW_PDF_DIR.mkdir(parents=True, exist_ok=True) 

app = FastAPI(title="Rias Research Assistant API")

# --- Mount static directory for results ---
# This is key. It makes files in your 'results' folder
# accessible at URLs like http://localhost:8000/static-results/sZ9ipF7G/...
app.mount("/static-results", StaticFiles(directory=RESULTS_ROOT), name="static_results")

# --- CORS Middleware (Unchanged) ---
origins = [
    "http://localhost:3000", # Changed to 3000 to match your dev server
    "http://localhost:5173",
    "http://localhost",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------
#  HELPER FUNCTION TO BUILD FILE TREE
# ----------------------------------------------------------------------
def build_file_tree(dir_path: Path):
    """
    Recursively scans a directory and builds a JSON tree.
    Filters out unwanted 'logs' and 'raw' folders.
    """
    tree = []
    if not dir_path.is_dir():
        return []

    for item in sorted(dir_path.iterdir()):
        # Filter out folders we don't want to see
        if item.name in ['logs', 'raw', '__pycache__'] or item.name.startswith('.'):
            continue

        if item.is_dir():
            # Recurse into subdirectories
            children = build_file_tree(item)
            if children: # Only add folders that aren't empty
                tree.append({
                    "name": item.name,
                    "type": "folder",
                    "children": children
                })
        elif item.is_file():
            # Only include files we can view/download
            if item.suffix.lower() in ['.docx', '.xlsx', '.pptx', '.pdf', '.txt', '.json', '.png', '.jpg']:
                # Get the relative path from the 'results' folder
                relative_path = item.relative_to(RESULTS_ROOT)
                # Build the static URL path
                url_path = str(relative_path).replace(os.path.sep, '/')
                
                tree.append({
                    "name": item.name,
                    "type": "file",
                    "path": url_path # This path is key for the frontend
                })
    return tree

# ----------------------------------------------------------------------
#  API ENDPOINTS
# ----------------------------------------------------------------------

@app.get("/")
def read_root():
    return {"hello": "Rias Research Assistant Backend is running!"}

@app.post("/upload-and-process/")
async def upload_and_process_file(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...)
):
    # (This function is unchanged)
    try:
        save_path = RAW_PDF_DIR / file.filename
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    finally:
        file.file.close() 

    pdf_paths_list = [save_path]
    try:
        pipeline = pipeline_logic.PDFPipeline(pdf_paths_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize pipeline: {e}")

    session_id = pipeline.session_id
    background_tasks.add_task(pipeline.run)

    return {
        "message": "File upload successful. Processing started.",
        "session_id": session_id,
        "filename": file.filename
    }


@app.get("/status/{session_id}")
def get_process_status(session_id: str):
    # (This function is MODIFIED)
    if not session_id or not session_id.isalnum():
        raise HTTPException(status_code=400, detail="Invalid session ID format.")
        
    session_dir = RESULTS_ROOT / session_id
    if not session_dir.exists() or not session_dir.is_dir():
        raise HTTPException(status_code=404, detail="Session ID not found.")

    final_output_file = session_dir / "03_comparison_merged.xlsx"

    if final_output_file.exists():
        # --- MODIFICATION ---
        # The job is done! Send back the main download URL
        # AND the new URL to fetch the file tree.
        return {
            "status": "complete",
            "session_id": session_id,
            "result_url": f"/download-result/{session_id}",
            "tree_url": f"/results-tree/{session_id}" # <-- NEW
        }
    else:
        return {"status": "processing", "session_id": session_id}


# --- NEW ENDPOINT ---
@app.get("/results-tree/{session_id}")
def get_results_tree(session_id: str):
    """
    Scans the session directory and returns a JSON file tree
    of the processed outputs.
    """
    if not session_id or not session_id.isalnum():
        raise HTTPException(status_code=400, detail="Invalid session ID format.")
    
    session_dir = RESULTS_ROOT / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Session ID not found.")

    # Build the tree, starting from the session directory
    tree = build_file_tree(session_dir)
    
    # Manually add the top-level merged file (if it exists)
    merged_file = session_dir / "03_comparison_merged.xlsx"
    if merged_file.exists():
        relative_path = merged_file.relative_to(RESULTS_ROOT)
        url_path = str(relative_path).replace(os.path.sep, '/')
        tree.insert(0, { # Add to the top of the list
            "name": "03_comparison_merged.xlsx",
            "type": "file",
            "path": url_path
        })
        
    return JSONResponse(content=tree)


@app.get("/download-result/{session_id}")
def download_result(session_id: str):
    # (This function is unchanged)
    if not session_id or not session_id.isalnum():
        raise HTTPException(status_code=400, detail="Invalid session ID format.")

    session_dir = RESULTS_ROOT / session_id
    final_file_path = session_dir / "03_comparison_merged.xlsx"

    if not final_file_path.exists():
        raise HTTPException(status_code=404, detail="Result file not found or not yet ready.")

    return FileResponse(
        path=final_file_path,
        filename=f"{session_id}_comparison_merged.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# --- (Main run block is unchanged) ---
if __name__ == "__main__":
    print(f"--- Starting Rias Research Assistant API Server ---")
    print(f"Serving results from: {RESULTS_ROOT}")
    print(f"Static files mapped: http://localhost:8000/static-results/")
    print(f"Go to http://localhost:8000")
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )