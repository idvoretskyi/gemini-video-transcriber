# Gemini Video Transcriber

A simple CLI tool to transcribe videos into pure text using Google's Gemini 3 Pro model via Vertex AI. Optimized for Ukrainian language support.

## Feature Highlights
- **Gemini 3 Pro Power**: Uses the latest multimodal capabilities for high-accuracy transcription.
- **Pure Text Output**: Delivers clean text directly to your console (standard output).
- **Ukrainian Native**: Prompts are tuned to recognize and handle Ukrainian speech fluently.
- **Cross-Platform**: Runs on macOS (Apple Silicon optimized) and Linux (Ubuntu).

## Prerequisites

1.  **Python 3.9+** installed.
2.  **Google Cloud Project** with Vertex AI API enabled.
3.  **Authentication**:
    *   **Option A (Recommended for Local)**: `gcloud` CLI installed and authenticated (`gcloud auth application-default login`).
    *   **Option B (API Key)**: A valid Google AI Studio or Vertex AI API Key (passed via `--api-key`).

### Authentication (Option A)

Run the following command to authenticate your local environment:
```bash
gcloud auth application-default login
```
*Ensure your authenticated user has permissions to write to the GCS bucket and use Vertex AI user permissions.*

## Installation

1.  Clone this repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  Place your video files in `workspace/input`.
2.  Run the script:

```bash
python3 src/transcribe.py workspace/input/video.mp4
```

### Output
The transcribed text will be saved in two locations:
1.  **Local**: `workspace/output/` with a sanitized filename.
2.  **GCS**: Uploaded to a bucket named `{project_id}-gemini-video-transcribe`.

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `file_path` | (Positional) Local path to the video file. | N/A |
| `--bucket` | Name of your GCS bucket. If omitted, a temporary bucket is created automatically. | Auto-generated (`gemini-transcriber-{project}-{region}`) |
| `--project` | GCP Project ID. Optional if set in gcloud config. | Auto-detected |
| `--location` | Vertex AI Region. | Auto-detected from `gcloud config` (default fallback: `us-central1`) |
| `--model` | Gemini Model version. | `gemini-2.5-pro` |
| `--preview` | Shorthand to use Gemini 3 Pro Preview model. | False |
| `--api-key` | Google AI Studio / Vertex AI API Key. Overrides `gcloud` auth. | None |
| `--keep-gcs` | Skip deleting the staging file from GCS. | False |

### Examples

**Standard (GCS auto-created, gcloud auth):**
```bash
python3 src/transcribe.py workspace/input/video.mp4
```

**Using an API Key:**
```bash
python3 src/transcribe.py workspace/input/video.mp4 --api-key "YOUR_API_KEY"
```

## Troubleshooting

- **"Model not found"**: Ensure the model (default `gemini-2.5-pro`) is available in your selected region. Try `us-central1`.
- **"403 Permission Denied"**: Check that your `gcloud auth application-default login` credential works and has `Storage Object Admin` and `Vertex AI User` roles.

## Roadmap / Next Steps

-   **Direct Uploads**: Support for direct file uploads (skipping GCS) for smaller files.
-   **Audio Support**: Add native support for `.mp3`, `.wav`, and other audio formats.
-   **Output Formats**: Generate `.srt` or `.vtt` subtitles with timestamps.
-   **Batch Processing**: Support transcribing all files in a directory.
-   **Retry Logic**: Automated handling of API quotas and failures.

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

