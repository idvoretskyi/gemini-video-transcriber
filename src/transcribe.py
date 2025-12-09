
import argparse
import sys
import os
import time
from typing import Optional

from google.cloud import storage
import vertexai
from vertexai.generative_models import GenerativeModel, Part, SafetySetting
from transliterate import translit

def upload_to_gcs(bucket_name: str, source_file_path: str, destination_blob_name: str) -> str:
    """Uploads a file to the bucket."""
    print(f"Uploading {source_file_path} to gs://{bucket_name}/{destination_blob_name} ...")
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_path)
    print(f"File uploaded to gs://{bucket_name}/{destination_blob_name}")
    return f"gs://{bucket_name}/{destination_blob_name}"

def ensure_bucket(bucket_name: str, location: str) -> None:
    """
    Ensures a bucket exists. Creates it if not.
    """
    storage_client = storage.Client()
    try:
        bucket = storage_client.bucket(bucket_name)
        if not bucket.exists():
            print(f"Bucket {bucket_name} not found. Creating in {location}...")
            # Location is important for data residence
            bucket.create(location=location)
            print(f"Created bucket: {bucket_name}")
        else:
            print(f"Using existing bucket: {bucket_name}")
    except Exception as e:
        print(f"Warning: Issue checking/creating bucket {bucket_name}: {e}")
        print("Falling back to attempt straightforward usage...")

def get_staging_bucket_name(project_id: str, location: str) -> str:
    # Sanitize location and project_id for bucket naming (lowercase, only alphanum and dashes)
    # Buckets prompt global uniqueness, so including project_id helps.
    
    # Simple sanitization
    safe_project = project_id.replace(':', '-').replace('.', '-').lower()
    safe_location = location.lower()
    return f"gemini-transcriber-{safe_project}-{safe_location}"

def get_output_bucket_name(project_id: str) -> str:
    # {project_id}-gemini-video-transcribe
    safe_project = project_id.replace(':', '-').replace('.', '-').lower()
    return f"{safe_project}-gemini-video-transcribe"

def upload_text_to_gcs(bucket_name: str, destination_blob_name: str, text_content: str) -> str:
    """Uploads text content to GCS."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_string(text_content)
    return f"gs://{bucket_name}/{destination_blob_name}"

def delete_blob(bucket_name: str, blob_name: str):
    """Deletes a blob from the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.delete()
    print(f"Blob {blob_name} deleted.")

def transcribe_video(
    project_id: str,
    location: str,
    model_name: str,
    gcs_uri: str,
    prompt_text: str = "Transcribe the audio from this video, paying special attention to Ukrainian speech. Provide the output as pure text."
) -> str:
    """Transcribes video using Gemini."""
    print(f"Initializing Vertex AI with project={project_id}, location={location}")
    vertexai.init(project=project_id, location=location)

    print(f"Loading model {model_name}...")
    model = GenerativeModel(model_name)

    print("Generating content...")
    video_part = Part.from_uri(
        uri=gcs_uri,
        mime_type="video/mp4", # Assuming MP4 for simplicity, or we could detect
    )

    responses = model.generate_content(
        [video_part, prompt_text],
        stream=True,
    )

    full_text = ""
    for response in responses:
        text_chunk = response.text
        print(text_chunk, end="", flush=True)
        full_text += text_chunk
    
    print("\n")
    return full_text


def get_gcloud_region() -> Optional[str]:
    """Attempts to get the region from gcloud config."""
    try:
        import subprocess
        result = subprocess.run(
            ["gcloud", "config", "get-value", "compute/region"],
            capture_output=True,
            text=True,
            check=False # Don't crash if gcloud fails
        )
        region = result.stdout.strip()
        if region and region != "(unset)":
            return region
    except Exception:
        pass
    return None

def sanitize_filename(filename: str) -> str:
    """
    Sanitizes the filename:
    1. Transliterates Cyrillic to Latin.
    2. Lowercases.
    3. Replaces spaces with underscores.
    """
    # Basename without extension
    name, ext = os.path.splitext(filename)
    
    # Transliterate (Ukrainian/Russian to Latin)
    try:
        from transliterate import translit
        name = translit(name, 'uk', reversed=True)
    except Exception:
        pass # Fallback if language not detected or other issue

    # Lowercase
    name = name.lower()
    
    # Replace spaces with underscores
    name = name.replace(" ", "_")
    
    return f"{name}.txt"

def transcribe_video_genai(
    api_key: str,
    project_id: str,
    location: str,
    gcs_uri: str,
    model_name: str,
    prompt_text: str
) -> str:
    """Transcribes video using the new Google GenAI SDK (Vertex AI backend)."""
    # Import here to avoid global dependency if not installed yet (though we enforce it now)
    from google import genai
    from google.genai import types

    print(f"Initializing GenAI Client for Vertex AI (Project: {project_id}, Location: {location})...")
    # Note: Vertex AI usually relies on ADC credentials, but user provided an API Key.
    # The user's sample uses api_key=... and vertexai=True.
    
    # SDK ValueErr: Project/location and API key are mutually exclusive
    client = genai.Client(
        vertexai=True,
        api_key=api_key
    )

    print(f"Loading model {model_name}...")
    
    # Create the video part from GCS URI
    # The new SDK might have a specific way, but Part.from_uri is standard for Vertex
    # In google-genai, it's types.Part.from_uri(...)
    
    video_part = types.Part.from_uri(
        file_uri=gcs_uri,
        mime_type="video/mp4"
    )
    
    text_part = types.Part.from_text(text=prompt_text)
    
    contents = [
        types.Content(
            role="user",
            parts=[video_part, text_part]
        )
    ]
    
    print("Generating content...")
    
    # Config similar to user sample, though strictly we just need standard generation
    generate_content_config = types.GenerateContentConfig(
        temperature=0.0, # Low temp for transcription accuracy
        max_output_tokens=8192,
    )

    responses = client.models.generate_content_stream(
        model=model_name,
        contents=contents,
        config=generate_content_config,
    )

    full_text = ""
    for chunk in responses:
        if chunk.text:
            print(chunk.text, end="", flush=True)
            full_text += chunk.text
    print("\n")
    return full_text

def main():
    # Detect default region
    default_region = get_gcloud_region() or "us-central1"
    
    parser = argparse.ArgumentParser(description="Transcribe video using Gemini 3 Pro via Vertex AI.")
    parser.add_argument("file_path", help="Path to the local video file. Recommended to be in workspace/input/")
    parser.add_argument("--bucket", help="Google Cloud Storage bucket name for temporary file staging. If not provided, one will be auto-created.")
    parser.add_argument("--project", help="Google Cloud Project ID. Optional if configured in gcloud.")
    parser.add_argument("--location", default=default_region, help=f"Google Cloud Region (default: {default_region}).")
    parser.add_argument("--model", default="gemini-2.5-pro", help="Gemini model version (default: gemini-2.5-pro).")
    parser.add_argument("--preview", action="store_true", help="Use Gemini 3 Pro Preview model (shorthand for --model gemini-3-pro-preview).")
    parser.add_argument("--keep-gcs", action="store_true", help="If set, skip deleting the file from GCS after processing.")
    parser.add_argument("--api-key", help="API Key for Vertex AI / Gemini. Required for Gemini 3 Preview if using API Key auth.")

    args = parser.parse_args()
    
    if args.preview:
        args.model = "gemini-3-pro-preview"

    if not os.path.exists(args.file_path):
        print(f"Error: File '{args.file_path}' not found.")
        sys.exit(1)

    # Infer project ID
    project_id = args.project
    if not project_id:
        try:
            import google.auth
            _, project_id = google.auth.default()
        except:
            pass
    
    if not project_id:
         try:
             import subprocess
             result = subprocess.run(["gcloud", "config", "get-value", "project"], capture_output=True, text=True)
             project_id = result.stdout.strip()
         except:
            pass

    if not project_id or project_id == "(unset)":
        print("Error: Google Cloud Project ID needed. Use --project or set up application default credentials.")
        sys.exit(1)

    print(f"Using Project: {project_id}, Region: {args.location}")
    
    # Handle Staging Bucket
    staging_bucket_name = args.bucket
    if not staging_bucket_name:
        staging_bucket_name = get_staging_bucket_name(project_id, args.location)
        ensure_bucket(staging_bucket_name, args.location)
    
    # Handle Output Bucket
    output_bucket_name = get_output_bucket_name(project_id)
    ensure_bucket(output_bucket_name, args.location)
    
    file_name = os.path.basename(args.file_path)
    blob_name = f"gemini-transcriber-staging/{int(time.time())}_{file_name}"
    
    # Upload first (required for Vertex AI, even with new SDK for large files)
    try:
        gcs_uri = upload_to_gcs(staging_bucket_name, args.file_path, blob_name)
    except Exception as e:
         print(f"Error uploading to GCS: {e}")
         sys.exit(1)

    # Transcribe
    try:
        if args.api_key:
             # Use new SDK path
             transcription_text = transcribe_video_genai(
                api_key=args.api_key,
                project_id=project_id,
                location=args.location,
                gcs_uri=gcs_uri,
                model_name=args.model,
                prompt_text="Transcribe the audio from this video, paying special attention to Ukrainian speech. Provide the output as pure text."
             )
        else:
             # Standard Vertex Path
             transcription_text = transcribe_video(
                project_id=project_id,
                location=args.location,
                model_name=args.model,
                gcs_uri=gcs_uri
            )
        
        output_filename = sanitize_filename(file_name)
        
        # 1. Save to Local Output
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        local_output_dir = os.path.join(project_root, "workspace", "output")
        if not os.path.exists(local_output_dir):
            os.makedirs(local_output_dir, exist_ok=True)
            
        local_output_path = os.path.join(local_output_dir, output_filename)
        with open(local_output_path, "w", encoding="utf-8") as f:
            f.write(transcription_text)
        print(f"\n[Local] Output saved to: {local_output_path}")
        
        # 2. Save to GCS Output
        try:
             gcs_output_uri = upload_text_to_gcs(output_bucket_name, output_filename, transcription_text)
             print(f"[GCS] Output uploaded to: {gcs_output_uri}")
        except Exception as e:
             print(f"Warning: Failed to upload output to GCS: {e}")

    except Exception as e:
        print(f"\nAn error occurred during transcription: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if not args.keep_gcs:
            try:
                delete_blob(staging_bucket_name, blob_name)
            except Exception as e:
                print(f"Warning: Failed to cleanup GCS blob: {e}")

if __name__ == "__main__":
    main()
