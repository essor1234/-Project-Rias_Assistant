import uvicorn
import shutil
import os
import io
import zipfile
from pathlib import Path
from fastapi.responses import StreamingResponse

# --- FastAPI Imports ---
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles

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
app.mount("/static-results", StaticFiles(directory=RESULTS_ROOT), name="static_results")

# --- CORS Middleware ---
origins = [
    "*"  # Allow all origins (for development)
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------
#  HELPER FUNCTIONS
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
        if item.name in ['logs', 'raw', '__pycache__'] or item.name.startswith('.'):
            continue

        if item.is_dir():
            children = build_file_tree(item)
            if children:
                tree.append({
                    "name": item.name,
                    "type": "folder",
                    "children": children
                })
        elif item.is_file():
            if item.suffix.lower() in ['.docx', '.xlsx', '.pptx', '.pdf', '.txt', '.json', '.png', '.jpg']:
                relative_path = item.relative_to(RESULTS_ROOT)
                url_path = str(relative_path).replace(os.path.sep, '/')
                tree.append({
                    "name": item.name,
                    "type": "file",
                    "path": url_path
                })
    return tree

def zip_directory(directory: Path):
    """Creates an in-memory zip file of the session directory, skipping logs/raw."""
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED, False) as zip_file:
        for item in directory.rglob('*'):
            if item.is_file():
                parts = item.relative_to(directory).parts
                if 'logs' not in parts and 'raw' not in parts:
                    arcname = item.relative_to(directory)
                    zip_file.write(item, arcname=arcname)

    zip_buffer.seek(0)
    return zip_buffer

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
    """
    Receives a file, saves it, and starts the processing pipeline.
    """
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
    """
    Checks the status of a processing job by looking for the final file.
    """
    if not session_id or not session_id.isalnum():
        raise HTTPException(status_code=400, detail="Invalid session ID format.")
        
    session_dir = RESULTS_ROOT / session_id
    if not session_dir.exists() or not session_dir.is_dir():
        raise HTTPException(status_code=404, detail="Session ID not found.")

    # Define the file we're looking for to confirm completion
    final_output_file = session_dir / "03_comparison_merged.xlsx"

    if final_output_file.exists():
        # Job is complete!
        return {
            "status": "complete",
            "session_id": session_id,
            "tree_url": f"/results-tree/{session_id}" # URL to fetch the file tree
        }
    else:
        # Job is still running
        return {"status": "processing", "session_id": session_id}


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

    tree = build_file_tree(session_dir)
    
    # Manually add the top-level merged file (if it exists)
    merged_file = session_dir / "03_comparison_merged.xlsx"
    if merged_file.exists():
        relative_path = merged_file.relative_to(RESULTS_ROOT)
        url_path = str(relative_path).replace(os.path.sep, '/')
        tree.insert(0, {
            "name": "03_comparison_merged.xlsx",
            "type": "file",
            "path": url_path
        })
        
    return JSONResponse(content=tree)


@app.get("/download-zip/{session_id}")
def download_zip(session_id: str):
    """
    Creates a zip file of the entire session's results and returns it.
    """
    if not session_id or not session_id.isalnum():
        raise HTTPException(status_code=400, detail="Invalid session ID format.")

    session_dir = RESULTS_ROOT / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Session ID not found.")

    zip_buffer = zip_directory(session_dir)
    
    headers = {
        'Content-Disposition': f'attachment; filename="{session_id}_results.zip"'
    }
    
    return StreamingResponse(
        zip_buffer, 
        media_type="application/zip",
        headers=headers
    )


# --- (Main run block) ---
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