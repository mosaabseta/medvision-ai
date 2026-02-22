"""
Video Conversion Routes - Backend FFmpeg Processing
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.responses import FileResponse

import subprocess
import tempfile
import os
from pathlib import Path
import shutil

router = APIRouter(prefix="/api/convert", tags=["conversion"])


@router.post("/to-mp4")
async def convert_to_mp4(file: UploadFile = File(...)):
    """
    Convert uploaded video to browser-compatible MP4 (H.264/AAC)
    """
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Create temp directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Save uploaded file
        input_path = os.path.join(temp_dir, f"input{Path(file.filename).suffix}")
        output_path = os.path.join(temp_dir, "output.mp4")
        
        with open(input_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        print(f"📹 Converting {file.filename} to MP4...")
        
        # FFmpeg command for web-compatible MP4
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-c:v', 'libx264',           # H.264 video codec
            '-preset', 'fast',            # Encoding speed
            '-crf', '23',                 # Quality (18-28, lower = better)
            '-c:a', 'aac',                # AAC audio codec
            '-b:a', '128k',               # Audio bitrate
            '-movflags', '+faststart',    # Enable streaming
            '-pix_fmt', 'yuv420p',        # Pixel format for compatibility
            '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',  # Ensure even dimensions
            '-y',                         # Overwrite output
            output_path
        ]
        
        # Run FFmpeg
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300  # 5 minute timeout
        )
        
        if process.returncode != 0:
            error_msg = process.stderr.decode('utf-8')
            print(f"❌ FFmpeg error: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Video conversion failed: {error_msg[:200]}"
            )
        
        # Check output file exists
        if not os.path.exists(output_path):
            raise HTTPException(status_code=500, detail="Conversion failed - no output file")
        
        file_size = os.path.getsize(output_path)
        print(f"✅ Conversion complete: {file_size / (1024*1024):.2f} MB")
        return FileResponse(
            output_path,
            media_type="video/mp4",
            filename=f"converted_{Path(file.filename).stem}.mp4"
        )

        # Stream the converted file
        # def iterfile():
        #     with open(output_path, 'rb') as f:
        #         yield from f
        
        # # Clean up temp directory after streaming
        # response = StreamingResponse(
        #     iterfile(),
        #     media_type="video/mp4",
        #     headers={
        #         "Content-Disposition": f"attachment; filename=converted_{Path(file.filename).stem}.mp4"
        #     }
        # )
        
        # Note: temp_dir cleanup happens in background
        # In production, use a cleanup task
        
        return response
    
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Conversion timeout - file too large")
    
    except Exception as e:
        print(f"❌ Conversion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    # finally:
    #     # Cleanup (delayed to allow streaming)
    #     # In production, use background task
    #     try:
    #         # Give time for response to stream
    #         import time
    #         time.sleep(1)
    #         shutil.rmtree(temp_dir, ignore_errors=True)
    #     except:
    #         pass


@router.post("/check-codec")
async def check_video_codec(file: UploadFile = File(...)):
    """
    Check if video needs conversion
    Returns codec info and whether conversion is needed
    """
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Save uploaded file
        input_path = os.path.join(temp_dir, file.filename)
        
        with open(input_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Use ffprobe to check codecs
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name,codec_long_name,width,height',
            '-of', 'json',
            input_path
        ]
        
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10
        )
        
        if process.returncode != 0:
            return JSONResponse({
                "needs_conversion": True,
                "reason": "Could not read video codec",
                "recommendation": "Convert to ensure compatibility"
            })
        
        import json
        probe_data = json.loads(process.stdout.decode('utf-8'))
        
        if not probe_data.get('streams'):
            return JSONResponse({
                "needs_conversion": True,
                "reason": "No video stream found"
            })
        
        video_stream = probe_data['streams'][0]
        codec_name = video_stream.get('codec_name', 'unknown')
        
        # Check if H.264
        needs_conversion = codec_name not in ['h264', 'avc1']
        
        return JSONResponse({
            "needs_conversion": needs_conversion,
            "current_codec": codec_name,
            "codec_long_name": video_stream.get('codec_long_name', ''),
            "resolution": f"{video_stream.get('width', 0)}x{video_stream.get('height', 0)}",
            "recommendation": "Convert to H.264" if needs_conversion else "Video should play in browser"
        })
    
    except Exception as e:
        return JSONResponse({
            "needs_conversion": True,
            "reason": f"Error checking codec: {str(e)}"
        })
    
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)