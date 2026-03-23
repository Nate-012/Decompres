import pyvips
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://decompres.vercel.app"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
    expose_headers=[
        "X-Original-Size",
        "X-Compressed-Size",
        "X-Reduction-Percent",
        "X-Output-Format"
    ]
)

MAX_FILE_SIZE = 20 * 1024 * 1024

SUPPORTED_TYPES = {
    "image/jpeg", "image/png", "image/webp",
    "image/gif", "image/bmp", "image/tiff",
    "image/heic", "image/heif"
}

CONVERT_FORMATS = {
    "jpeg": {"ext": ".jpg", "media_type": "image/jpeg", "filename": "converted.jpg"},
    "png":  {"ext": ".png", "media_type": "image/png",  "filename": "converted.png"},
    "webp": {"ext": ".webp","media_type": "image/webp", "filename": "converted.webp"},
}

@app.get("/")
def root():
    return {"status": "compressor is running"}

@app.post("/compress")
async def compress_image(
    file: UploadFile = File(...),
    quality: int = Query(default=80, ge=1, le=100)
):
    if file.content_type not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}. Supported: JPEG, PNG, WebP, GIF, BMP, TIFF, HEIC"
        )

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum size is 20MB."
        )

    try:
        image = pyvips.Image.new_from_buffer(data, "", access="sequential")
        if image.hasalpha():
            image = image.flatten(background=255)
        output = image.write_to_buffer(".webp", Q=quality, effort=4)
    except pyvips.Error as e:
        raise HTTPException(
            status_code=422,
            detail=f"Could not process image: {str(e)}"
        )

    if len(output) >= len(data):
        return JSONResponse(
            status_code=200,
            content={
                "compressed": False,
                "message": "Hey! We noticed that this file is already compressed to the maximum of our ability! If you want to convert this file from one format to another though, head over to the Convert tab for that!",
                "original_size": len(data),
                "hint": "already_optimised"
            }
        )

    return Response(
        content=output,
        media_type="image/webp",
        headers={
            "Content-Disposition": "attachment; filename=compressed.webp",
            "X-Original-Size": str(len(data)),
            "X-Compressed-Size": str(len(output)),
            "X-Reduction-Percent": str(round((1 - len(output) / len(data)) * 100, 1))
        }
    )

@app.post("/convert")
async def convert_image(
    file: UploadFile = File(...),
    target_format: str = Query(default="jpeg")
):
    # Validate target format
    if target_format not in CONVERT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported target format: {target_format}. Supported: jpeg, png, webp"
        )

    # Validate input type
    if file.content_type not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}."
        )

    # Read and check size
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum size is 20MB."
        )

    # Convert
    try:
        image = pyvips.Image.new_from_buffer(data, "", access="sequential")

        fmt = CONVERT_FORMATS[target_format]

        # JPEG doesn't support transparency — flatten alpha if present
        if target_format == "jpeg" and image.hasalpha():
            image = image.flatten(background=255)

        output = image.write_to_buffer(fmt["ext"])

    except pyvips.Error as e:
        raise HTTPException(
            status_code=422,
            detail=f"Could not convert image: {str(e)}"
        )

    return Response(
        content=output,
        media_type=fmt["media_type"],
        headers={
            "Content-Disposition": f"attachment; filename={fmt['filename']}",
            "X-Original-Size": str(len(data)),
            "X-Output-Size": str(len(output)),
            "X-Output-Format": target_format
        }
    )
