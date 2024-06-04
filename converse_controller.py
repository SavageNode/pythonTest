from fastapi import APIRouter, Form, UploadFile, File, Query

from services import freestyle_service, transcribe_voice_service, text_to_voice_service, get_audio_file_service, \
    image_generation_service, file_to_text, image_to_text_service, history_management_service, get_all_files, \
    file_semantic_search, reset_rag_data, delete_file_from_rag

router = APIRouter(
    prefix="/Inference",
    responses={
        200: {"description": "Successful Summarization"},
        400: {"description": "Bad Request, check request configuration"},
        500: {"description": "Internal Server Error"}
    },
    tags=["Inference"]
)


@router.post("/freestyle", description="Instructions and files")
async def free_form(
        prompt: str = Form(description="Instruction to follow or Question"),
        history: str = Form(default="[]", description="Log History"),
        file: UploadFile = File(default=None, description="The file attached"),
        notes: str = Form(default=None, description="Any notes"),
        temp: float = Form(default=0.05, description="temp"),
        pres: float = Form(default=0.00, description="Presence Penalty"),
        freq: float = Form(default=0.0, description="Frequency penalty"),
        api_key: str = Form(description="OPENAI Key")
):
    return await freestyle_service(prompt, history, notes, file, temp, pres, freq, api_key)


@router.post("/transcribeVoice", description="Transcribes voice")
async def transcribe_voice(
        file: UploadFile = File(default=None, description="voice file only"),
        api_key: str = Form(description="OPENAI Key")
):
    print(file)
    file_location = f"audio/{file.filename}"
    with open(file_location, "wb+") as file_object:
        file_object.write(file.file.read())
        file_object.close()
    return await transcribe_voice_service(file_location, api_key)


@router.post("/textToVoice", description="Text to Voice")
def text_to_voice(
        text: str = Form(description="Text to turn to voice"),
        api_key: str = Form(description="OPENAI Key")
):
    return text_to_voice_service(text, api_key)


@router.post("/getAudioFile", description="gets voice file of returned response")
async def get_audio_file(
        file_name: str = Form(description="number of voice file"),
):
    return await get_audio_file_service(file_name)


@router.post("/imageGeneration", description="Text to Voice")
def text_to_image(
        prompt: str = Form(description="Text to turn to image"),
        api_key: str = Form(description="OPENAI Key")
):
    return image_generation_service(prompt, api_key)


@router.post("/file_text_extraction", description="Returns text from file")
async def file_to_text_extraction(
        file: UploadFile = File(description="The file attached"),
        api_key: str = Form(default=None, description="OpenAI key"),
        rag: str = Form(default="n", description="Permanent save? Y or N")
):
    return await file_to_text(file, rag, api_key)


@router.post("/image_text_extraction", description="Returns text from image")
def file_to_text_extraction(
        prompt: str = Form(description="Prompt for the image"),
        file: UploadFile = File(description="The file attached"),
        api_key: str = Form(description="OPENAI Key")
):
    return image_to_text_service(prompt, file, api_key)


@router.post("/history_management", description="compresses history")
def history_management(
        history: str = Form(description="History"),
        api_key: str = Form(description="OPENAI Key")
):
    return history_management_service(history, api_key)


@router.get("/get_all_files", description="Get all files from files.pickle")
def get_files():
    return get_all_files()


@router.post("/semantic_search", description="Find file based on prompt")
def semantic_search(
        query: str = Form(description="Query"),
):
    return file_semantic_search(query)


@router.get("/reset_rag_data", description="reset all files from RAG pickle")
def reset_data():
    return reset_rag_data()


@router.get("/delete_file", description="delete_file")
def delete_file(
        file_id: str = Query(description="Query"),
):
    return delete_file_from_rag(file_id)
