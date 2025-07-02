
from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydub import AudioSegment, effects
import uuid, shutil, os, json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
PROCESSED_DIR = "processed"
METADATA_FILE = "submissions.json"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

if os.path.exists(METADATA_FILE):
    with open(METADATA_FILE, "r") as f:
        submissions = json.load(f)
else:
    submissions = {}

def save_metadata():
    with open(METADATA_FILE, "w") as f:
        json.dump(submissions, f, indent=2)

def enhance_audio(input_path, output_path, preset):
    sound = AudioSegment.from_file(input_path)
    if preset == "clean":
        sound = effects.normalize(sound)
    elif preset == "bass":
        sound = sound.low_pass_filter(120)
    elif preset == "lofi":
        sound = sound.low_pass_filter(6000).high_pass_filter(200)
    elif preset == "fx":
        sound = effects.normalize(sound).reverse()
    else:
        sound = effects.normalize(sound)
    sound.export(output_path, format="wav")

@app.post("/upload/")
async def upload_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...), preset: str = Form(...)):
    uid = str(uuid.uuid4())
    original_filename = file.filename
    input_path = os.path.join(UPLOAD_DIR, f"{uid}_{original_filename}")
    output_filename = f"enhanced_{uid}.wav"
    output_path = os.path.join(PROCESSED_DIR, output_filename)

    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    submissions[uid] = {
        "original_filename": original_filename,
        "status": "processing",
        "preset": preset,
        "download_link": f"/download/{output_filename}"
    }
    save_metadata()

    def background_process():
        enhance_audio(input_path, output_path, preset)
        submissions[uid]["status"] = "complete"
        save_metadata()

    background_tasks.add_task(background_process)

    return {
        "message": "Upload received. Enhancement started.",
        "track_id": uid,
        "download_url": f"/download/{output_filename}"
    }

@app.get("/submissions/")
def list_submissions():
    return submissions

@app.get("/download/{filename}")
def download_file(filename: str):
    path = os.path.join(PROCESSED_DIR, filename)
    return FileResponse(path) if os.path.exists(path) else JSONResponse({"error": "Not found"}, status_code=404)
